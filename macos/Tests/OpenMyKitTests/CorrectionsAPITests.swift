import XCTest
@testable import OpenMyKit

final class CorrectionsAPITests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeClient() -> APIClient {
        APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked())
    }

    // 行为：corrections() 命中 /api/corrections，解包 {corrections:[…]} 取数组
    func test_corrections_decodes_list() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/corrections")
            let json = """
            {"corrections":[
              {"wrong":"新建","right":"新疆","context":"去新疆自驾","count":3,
               "first_seen":"2026-06-01","last_updated":"2026-06-05"}]}
            """
            return (200, Data(json.utf8))
        }
        let list = try await makeClient().corrections()
        XCTAssertEqual(list.count, 1)
        XCTAssertEqual(list[0].wrong, "新建")
        XCTAssertEqual(list[0].right, "新疆")
        XCTAssertEqual(list[0].context, "去新疆自驾")
        XCTAssertEqual(list[0].count, 3)
        XCTAssertEqual(list[0].firstSeen, "2026-06-01")
        XCTAssertEqual(list[0].lastUpdated, "2026-06-05")
    }

    // 行为：文件不存在时后端返回 {corrections:[]}，解码为空列表
    func test_corrections_empty() async throws {
        MockURLProtocol.handler = { _ in (200, Data(#"{"corrections":[]}"#.utf8)) }
        let list = try await makeClient().corrections()
        XCTAssertEqual(list, [])
    }

    // 行为：缺字段安全降级（count/时间缺省）
    func test_corrections_tolerates_missing_fields() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"corrections":[{"wrong":"a","right":"b"}]}"#.utf8))
        }
        let list = try await makeClient().corrections()
        XCTAssertEqual(list[0].count, 0)
        XCTAssertEqual(list[0].firstSeen, "")
        XCTAssertEqual(list[0].context, "")
    }

    // 行为：submitCorrection 发 POST 到 /api/correct/typo，body 全字段
    func test_submitCorrection_posts_body() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/correct/typo")
            XCTAssertEqual(req.httpMethod, "POST")
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["wrong"] as? String, "新建")
            XCTAssertEqual(obj["right"] as? String, "新疆")
            XCTAssertEqual(obj["context"] as? String, "去新疆")
            XCTAssertEqual(obj["date"] as? String, "2026-06-05")
            XCTAssertEqual(obj["sync_vocab"] as? Bool, true)
            return (200, Data(#"{"success":true,"correction":{"wrong":"新建","right":"新疆"},"replaced_in_file":2,"total_corrections":7}"#.utf8))
        }
        let result = try await makeClient().submitCorrection(
            wrong: "新建", right: "新疆", context: "去新疆", date: "2026-06-05"
        )
        XCTAssertTrue(result.success)
        XCTAssertEqual(result.replacedInFile, 2)
        XCTAssertEqual(result.totalCorrections, 7)
    }

    // 行为：无 date 时 body 不带 date 字段
    func test_submitCorrection_omits_date_when_nil() async throws {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertNil(obj["date"])
            return (200, Data(#"{"success":true,"replaced_in_file":0,"total_corrections":1}"#.utf8))
        }
        let result = try await makeClient().submitCorrection(wrong: "a", right: "b")
        XCTAssertTrue(result.success)
    }

    // 行为：后端拒绝（wrong/right 相等）返回 success=false + error，不抛错
    func test_submitCorrection_decodes_failure() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"success":false,"error":"wrong and right must differ"}"#.utf8))
        }
        let result = try await makeClient().submitCorrection(wrong: "x", right: "x")
        XCTAssertFalse(result.success)
        XCTAssertEqual(result.error, "wrong and right must differ")
    }
}
