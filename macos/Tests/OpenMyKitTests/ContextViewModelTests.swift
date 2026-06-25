import XCTest
@testable import OpenMyKit

@MainActor
final class ContextViewModelTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeVM() -> ContextViewModel {
        ContextViewModel(client: APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked()))
    }

    // 行为：load 并发拉三类条目并填充
    func test_load_fills_three_lists() async {
        MockURLProtocol.handler = { req in
            switch req.url?.path {
            case "/api/context/loops":
                return (200, Data(#"[{"loop_id":"L1","title":"待办A"}]"#.utf8))
            case "/api/context/projects":
                return (200, Data(#"[{"project_id":"P1","title":"项目A"},{"project_id":"P2","title":"项目B"}]"#.utf8))
            case "/api/context/decisions":
                return (200, Data(#"[{"decision_id":"D1","decision":"决策A"}]"#.utf8))
            default:
                return (404, Data())
            }
        }
        let vm = makeVM()
        await vm.load()
        XCTAssertEqual(vm.loops.count, 1)
        XCTAssertEqual(vm.projects.count, 2)
        XCTAssertEqual(vm.decisions.count, 1)
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：load 任一失败置 errorMessage
    func test_load_failure_sets_error() async {
        MockURLProtocol.handler = { req in
            if req.url?.path == "/api/context/decisions" { return (500, Data("{}".utf8)) }
            return (200, Data("[]".utf8))
        }
        let vm = makeVM()
        await vm.load()
        XCTAssertNotNil(vm.errorMessage)
    }

    // 行为：closeLoop 成功后 reload（POST 成功 → 重新拉三类列表）
    func test_closeLoop_success_reloads() async {
        MockURLProtocol.handler = { req in
            switch req.url?.path {
            case "/api/context/loops/close":
                return (200, Data(#"{"success":true,"target_id":"L1"}"#.utf8))
            case "/api/context/loops":
                return (200, Data("[]".utf8)) // 关闭后待办清空
            case "/api/context/projects", "/api/context/decisions":
                return (200, Data("[]".utf8))
            default:
                return (404, Data())
            }
        }
        let vm = makeVM()
        let ok = await vm.closeLoop(query: "待办A", reason: "完成")
        XCTAssertTrue(ok)
        XCTAssertEqual(vm.loops, [])
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：修整后端报错（400）→ errorMessage 置位，返回 false
    func test_action_failure_sets_error() async {
        MockURLProtocol.handler = { _ in (400, Data(#"{"success":false,"error":"没找到"}"#.utf8)) }
        let vm = makeVM()
        let ok = await vm.rejectLoop(query: "xx")
        XCTAssertFalse(ok)
        XCTAssertNotNil(vm.errorMessage)
    }

    // 行为：mergeProject 成功后 reload
    func test_mergeProject_success_reloads() async {
        MockURLProtocol.handler = { req in
            if req.url?.path == "/api/context/projects/merge" {
                return (200, Data(#"{"success":true,"target_id":"P1"}"#.utf8))
            }
            return (200, Data("[]".utf8))
        }
        let vm = makeVM()
        let ok = await vm.mergeProject(source: "项目A", target: "项目B")
        XCTAssertTrue(ok)
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：runQuery 覆盖 kind/query 并填充结果
    func test_runQuery_fills_result() async {
        MockURLProtocol.handler = { _ in
            let json = """
            {"summary":"命中 1 条",
             "temporal_buckets":{"current":[{"type":"project","id":"P1","title":"OpenMy"}],"future":[],"past":[],"closed":[]},
             "evidence":[{"date":"2026-06-05","scene_id":"s1","quote":"引文","time_range":"00:05-00:12"}]}
            """
            return (200, Data(json.utf8))
        }
        let vm = makeVM()
        await vm.runQuery(kind: .project, query: "OpenMy")
        XCTAssertEqual(vm.queryKind, .project)
        XCTAssertEqual(vm.queryText, "OpenMy")
        XCTAssertEqual(vm.queryResult?.summary, "命中 1 条")
        XCTAssertEqual(vm.queryResult?.temporalBuckets.current.count, 1)
        XCTAssertFalse(vm.isQuerying)
    }

    // 行为：query 失败清空结果并置 error
    func test_runQuery_failure_clears_result() async {
        MockURLProtocol.handler = { _ in (500, Data("{}".utf8)) }
        let vm = makeVM()
        await vm.runQuery(kind: .open, query: "")
        XCTAssertNil(vm.queryResult)
        XCTAssertNotNil(vm.errorMessage)
    }

    // 行为：证据回链解析成 SearchFocus，time_range 取起点
    func test_focus_for_evidence_parses_time() async {
        let vm = makeVM()
        vm.queryText = "OpenMy"
        let ev = ContextEvidence(date: "2026-06-05", sceneId: "s1", quote: "引文", timeRange: "00:05-00:12")
        let focus = vm.focus(for: ev)
        XCTAssertEqual(focus.date, "2026-06-05")
        XCTAssertEqual(focus.time, "00:05")
        XCTAssertEqual(focus.query, "OpenMy")
    }
}
