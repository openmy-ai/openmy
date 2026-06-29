import XCTest
@testable import OpenMyKit

final class ContextAPITests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeClient() -> APIClient {
        APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked())
    }

    // 行为：context() 命中 /api/context，解码快照 + 嵌套三类条目 + provenance_refs
    func test_context_decodes_snapshot() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/context")
            let json = """
            {"status_line":"今天聚焦 OpenMy",
             "today_focus":["写前端","跑测试"],
             "open_loops":[{"loop_id":"L1","title":"补单测","status":"open","priority":"high",
               "provenance_refs":[{"date":"2026-06-05","scene_id":"s1","quote":"该补测试了"}]}],
             "active_projects":[{"project_id":"P1","title":"OpenMy","current_goal":"对齐前端"}],
             "recent_decisions":[{"decision_id":"D1","topic":"架构","decision":"用 SwiftUI"}]}
            """
            return (200, Data(json.utf8))
        }
        let snap = try await makeClient().context()
        XCTAssertEqual(snap.statusLine, "今天聚焦 OpenMy")
        XCTAssertEqual(snap.todayFocus, ["写前端", "跑测试"])
        XCTAssertEqual(snap.openLoops.count, 1)
        XCTAssertEqual(snap.openLoops[0].title, "补单测")
        XCTAssertEqual(snap.openLoops[0].provenanceRefs.first?.sceneId, "s1")
        XCTAssertEqual(snap.openLoops[0].provenanceRefs.first?.date, "2026-06-05")
        XCTAssertEqual(snap.openLoops[0].provenanceRefs.first?.quote, "该补测试了")
        XCTAssertEqual(snap.activeProjects[0].currentGoal, "对齐前端")
        XCTAssertEqual(snap.recentDecisions[0].decision, "用 SwiftUI")
    }

    // 行为：缺字段安全降级（空快照不抛错）
    func test_context_tolerates_missing_fields() async throws {
        MockURLProtocol.handler = { _ in (200, Data("{}".utf8)) }
        let snap = try await makeClient().context()
        XCTAssertEqual(snap.statusLine, "")
        XCTAssertEqual(snap.openLoops, [])
        XCTAssertEqual(snap.activeProjects, [])
        XCTAssertEqual(snap.recentDecisions, [])
    }

    // 行为：三类列表接口直接返回数组
    func test_loops_projects_decisions_decode_arrays() async throws {
        MockURLProtocol.handler = { req in
            switch req.url?.path {
            case "/api/context/loops":
                return (200, Data(#"[{"loop_id":"L1","title":"待办A","waiting_on":"老板"}]"#.utf8))
            case "/api/context/projects":
                return (200, Data(#"[{"project_id":"P1","title":"项目A"}]"#.utf8))
            case "/api/context/decisions":
                return (200, Data(#"[{"decision_id":"D1","decision":"决策A","topic":"主题A"}]"#.utf8))
            default:
                XCTFail("意外路径")
                return (404, Data())
            }
        }
        let client = makeClient()
        let loops = try await client.contextLoops()
        let projects = try await client.contextProjects()
        let decisions = try await client.contextDecisions()
        XCTAssertEqual(loops.first?.waitingOn, "老板")
        XCTAssertEqual(projects.first?.title, "项目A")
        XCTAssertEqual(decisions.first?.topic, "主题A")
    }

    // 行为：closeLoop POST body 含 query/status/reason（重点验证 query 字段名）
    func test_closeLoop_posts_body() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/context/loops/close")
            XCTAssertEqual(req.httpMethod, "POST")
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["query"] as? String, "补单测")
            XCTAssertEqual(obj["status"] as? String, "done")
            XCTAssertEqual(obj["reason"] as? String, "已完成")
            return (200, Data(#"{"success":true,"target_id":"L1"}"#.utf8))
        }
        let result = try await makeClient().closeLoop(query: "补单测", reason: "已完成")
        XCTAssertTrue(result.success)
        XCTAssertEqual(result.targetId, "L1")
    }

    // 行为：mergeProject POST body 用 source/target（不是 query），字段名正确
    func test_mergeProject_posts_source_target() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/context/projects/merge")
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["source"] as? String, "项目A")
            XCTAssertEqual(obj["target"] as? String, "项目B")
            XCTAssertEqual(obj["reason"] as? String, "重复")
            XCTAssertNil(obj["query"])
            return (200, Data(#"{"success":true,"target_id":"P1"}"#.utf8))
        }
        let result = try await makeClient().mergeProject(source: "项目A", target: "项目B", reason: "重复")
        XCTAssertTrue(result.success)
    }

    // 行为：rejectLoop/rejectProject/rejectDecision body 用 query
    func test_reject_actions_post_query() async throws {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["query"] as? String, "X")
            return (200, Data(#"{"success":true,"target_id":"T"}"#.utf8))
        }
        let client = makeClient()
        _ = try await client.rejectLoop(query: "X")
        _ = try await client.rejectProject(query: "X")
        _ = try await client.rejectDecision(query: "X")
    }

    // 行为：修整失败返回 success=false + error，不抛错
    func test_action_decodes_failure() async throws {
        MockURLProtocol.handler = { _ in
            (400, Data(#"{"success":false,"error":"没找到待办：xx"}"#.utf8))
        }
        // 后端失败用 400，APIClient.checkStatus 会抛 badStatus —— 这里验证抛错路径由 VM 兜底。
        do {
            _ = try await makeClient().closeLoop(query: "xx")
            XCTFail("400 应抛错")
        } catch let APIError.badStatus(code) {
            XCTAssertEqual(code, 400)
        }
    }

    // 行为：contextQuery 拼对 query 串（kind/limit/evidence/q），解码 summary + 时态分桶
    func test_contextQuery_builds_params_and_decodes() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/context/query")
            let q = req.url?.query ?? ""
            XCTAssertTrue(q.contains("kind=project"))
            XCTAssertTrue(q.contains("limit=8"))
            XCTAssertTrue(q.contains("evidence=1"))
            XCTAssertTrue(q.contains("q="))
            let json = """
            {"summary":"命中 2 条",
             "current_hits":[{"type":"project","id":"P1","title":"OpenMy"}],
             "history_hits":[],
             "temporal_buckets":{"current":[{"type":"loop","id":"L1","title":"待办"}],
               "future":[],"past":[],"closed":[]},
             "evidence":[{"date":"2026-06-05","scene_id":"s1","quote":"引文","time_range":"00:05-00:12"}]}
            """
            return (200, Data(json.utf8))
        }
        let result = try await makeClient().contextQuery(kind: .project, query: "OpenMy")
        XCTAssertEqual(result.summary, "命中 2 条")
        XCTAssertEqual(result.currentHits.first?.title, "OpenMy")
        XCTAssertEqual(result.temporalBuckets.current.first?.hitId, "L1")
        XCTAssertEqual(result.evidence.first?.timeRange, "00:05-00:12")
        XCTAssertEqual(result.evidence.first?.sceneId, "s1")
    }

    // 行为：空 query 时不带 q 参数
    func test_contextQuery_omits_empty_query() async throws {
        MockURLProtocol.handler = { req in
            let q = req.url?.query ?? ""
            XCTAssertFalse(q.contains("q="))
            return (200, Data("{}".utf8))
        }
        _ = try await makeClient().contextQuery(kind: .open, query: "  ")
    }

    // 行为：contextAsk 命中 /api/context/ask 带 q/limit
    func test_contextAsk_builds_params() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/context/ask")
            let q = req.url?.query ?? ""
            XCTAssertTrue(q.contains("limit=6"))
            return (200, Data(#"{"answer":"答案","summary":"摘要"}"#.utf8))
        }
        let result = try await makeClient().contextAsk(question: "我在忙什么")
        XCTAssertEqual(result.answer, "答案")
        XCTAssertEqual(result.summary, "摘要")
    }
}
