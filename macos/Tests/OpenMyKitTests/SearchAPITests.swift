import XCTest
@testable import OpenMyKit

final class SearchAPITests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeClient() -> APIClient {
        APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked())
    }

    // 行为：search 命中 /api/search，带 q，解码命中列表
    func test_search_decodes_results() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/search")
            XCTAssertEqual(req.url?.query, "q=%E6%96%B0%E7%96%86")  // "新疆" URL 编码
            let json = #"[{"date":"2026-06-05","time":"00:05","context":"去<mark>新疆</mark>自驾","raw_context":"去新疆自驾"}]"#
            return (200, Data(json.utf8))
        }
        let results = try await makeClient().search(query: "新疆")
        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].date, "2026-06-05")
        XCTAssertEqual(results[0].time, "00:05")
        XCTAssertEqual(results[0].context, "去<mark>新疆</mark>自驾")
        XCTAssertEqual(results[0].rawContext, "去新疆自驾")
    }

    // 行为：空 query 短路返回 []，不发请求
    func test_search_empty_query_short_circuits() async throws {
        MockURLProtocol.handler = { _ in
            XCTFail("空 query 不应发请求")
            return (200, Data("[]".utf8))
        }
        let results = try await makeClient().search(query: "   ")
        XCTAssertEqual(results, [])
    }

    // 行为：search 缺字段时安全降级
    func test_search_tolerates_missing_fields() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"[{"date":"2026-06-05","context":"x"}]"#.utf8))
        }
        let results = try await makeClient().search(query: "x")
        XCTAssertEqual(results[0].time, "")
        XCTAssertEqual(results[0].rawContext, "")
    }

    // 行为：stats 命中 /api/stats，解码总数与角色分布
    func test_stats_decodes() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/stats")
            let json = #"{"total_dates":3,"total_words":12000,"total_segments":48,"role_distribution":{"我":30,"对方":18}}"#
            return (200, Data(json.utf8))
        }
        let s = try await makeClient().stats()
        XCTAssertEqual(s.totalDates, 3)
        XCTAssertEqual(s.totalWords, 12000)
        XCTAssertEqual(s.totalSegments, 48)
        XCTAssertEqual(s.roleDistribution, ["我": 30, "对方": 18])
    }

    // 行为：stats 缺字段降级为 0 / 空
    func test_stats_tolerates_missing_fields() async throws {
        MockURLProtocol.handler = { _ in (200, Data("{}".utf8)) }
        let s = try await makeClient().stats()
        XCTAssertEqual(s.totalDates, 0)
        XCTAssertEqual(s.roleDistribution, [:])
    }
}
