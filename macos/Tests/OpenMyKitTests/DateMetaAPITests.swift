import XCTest
@testable import OpenMyKit

final class DateMetaAPITests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeClient() -> APIClient {
        APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked())
    }

    // 行为：dateMeta 命中 /api/date/{date}/meta，解码四分区对象项
    func test_dateMeta_decodes_four_groups() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/date/2026-06-25/meta")
            let json = """
            {"events":[{"time":"09:00","summary":"开了个会","project":"OpenMy"}],
             "intents":[{"time":"10:00","intent":"打算重构"}],
             "facts":[{"fact":"记住要带钥匙"}],
             "decisions":[{"time":"11:00","decision":"用本地引擎","topic":"STT"}]}
            """
            return (200, Data(json.utf8))
        }
        let m = try await makeClient().dateMeta(date: "2026-06-25")
        XCTAssertEqual(m.events.count, 1)
        XCTAssertEqual(m.events.first?.text, "开了个会")
        XCTAssertEqual(m.events.first?.time, "09:00")
        XCTAssertEqual(m.events.first?.project, "OpenMy")
        XCTAssertEqual(m.intents.first?.text, "打算重构")
        XCTAssertEqual(m.facts.first?.text, "记住要带钥匙")
        XCTAssertEqual(m.decisions.first?.text, "用本地引擎")
        XCTAssertEqual(m.decisions.first?.project, "STT") // project 缺则回退 topic
    }

    // 行为：裸字符串项也能解码成文本
    func test_dateMeta_decodes_string_items() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"facts":["纯字符串事实"]}"#.utf8))
        }
        let m = try await makeClient().dateMeta(date: "2026-06-25")
        XCTAssertEqual(m.facts.first?.text, "纯字符串事实")
    }

    // 行为：meta 为空对象时四类全空
    func test_dateMeta_empty_object() async throws {
        MockURLProtocol.handler = { _ in (200, Data("{}".utf8)) }
        let m = try await makeClient().dateMeta(date: "2026-06-25")
        XCTAssertEqual(m, DateMeta())
    }

    // 行为：空壳项（既无文本又无时间）被丢弃
    func test_dateMeta_drops_empty_entries() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"events":[{"unknown_key":"x"},{"summary":"有效"}]}"#.utf8))
        }
        let m = try await makeClient().dateMeta(date: "2026-06-25")
        XCTAssertEqual(m.events.count, 1)
        XCTAssertEqual(m.events.first?.text, "有效")
    }

    // 行为：meta 整体是 null/非字典时降级空（后端 load_json 可能回 null）
    func test_dateMeta_tolerates_null() async throws {
        MockURLProtocol.handler = { _ in (200, Data("null".utf8)) }
        let m = try await makeClient().dateMeta(date: "2026-06-25")
        XCTAssertEqual(m, DateMeta())
    }
}
