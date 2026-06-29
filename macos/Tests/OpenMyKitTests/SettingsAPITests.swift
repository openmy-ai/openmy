import XCTest
@testable import OpenMyKit

final class SettingsAPITests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeClient() -> APIClient {
        APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked())
    }

    // 行为：screenContextSettings() 命中 GET /api/settings/screen-context，全字段解码
    func test_screenContext_decodes_all_fields() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/settings/screen-context")
            XCTAssertEqual(req.httpMethod, "GET")
            let json = """
            {"enabled":true,"participation_mode":"full","capture_interval_seconds":30,
             "screenshot_retention_hours":48,"exclude_apps":["微信"],"exclude_domains":["bank.com"],
             "exclude_window_keywords":["密码"],"summary_only_apps":["飞书"],"retention_days":7}
            """
            return (200, Data(json.utf8))
        }
        let s = try await makeClient().screenContextSettings()
        XCTAssertTrue(s.enabled)
        XCTAssertEqual(s.mode, .full)
        XCTAssertEqual(s.captureIntervalSeconds, 30)
        XCTAssertEqual(s.screenshotRetentionHours, 48)
        XCTAssertEqual(s.excludeApps, ["微信"])
        XCTAssertEqual(s.excludeDomains, ["bank.com"])
        XCTAssertEqual(s.excludeWindowKeywords, ["密码"])
        XCTAssertEqual(s.summaryOnlyApps, ["飞书"])
        XCTAssertEqual(s.retentionDays, 7)
    }

    // 行为：mode==off 时 enabled 强制 false（对齐后端 from_dict）
    func test_screenContext_mode_off_forces_disabled() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"enabled":true,"participation_mode":"off"}"#.utf8))
        }
        let s = try await makeClient().screenContextSettings()
        XCTAssertEqual(s.mode, .off)
        XCTAssertFalse(s.enabled)
    }

    // 行为：非法 mode 归一到 summary_only
    func test_screenContext_illegal_mode_defaults_summaryOnly() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"participation_mode":"weird"}"#.utf8))
        }
        let s = try await makeClient().screenContextSettings()
        XCTAssertEqual(s.mode, .summaryOnly)
    }

    // 行为：缺字段安全降级（空 dict → 默认值）
    func test_screenContext_tolerates_missing_fields() async throws {
        MockURLProtocol.handler = { _ in (200, Data("{}".utf8)) }
        let s = try await makeClient().screenContextSettings()
        XCTAssertTrue(s.enabled)
        XCTAssertEqual(s.mode, .summaryOnly)
        XCTAssertEqual(s.excludeApps, [])
        XCTAssertEqual(s.captureIntervalSeconds, 0)
    }

    // 行为：rawDictionary 保留未建模字段
    func test_screenContext_preserves_unmodeled_fields() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"enabled":true,"extra_flag":true,"some_count":9}"#.utf8))
        }
        let s = try await makeClient().screenContextSettings()
        XCTAssertEqual(s.rawDictionary["extra_flag"], .bool(true))
        XCTAssertEqual(s.rawDictionary["some_count"], .int(9))
    }

    // 行为：updateScreenContextSettings 发 POST，body 为部分字段，解码合并后结果
    func test_updateScreenContext_posts_partial_body() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/settings/screen-context")
            XCTAssertEqual(req.httpMethod, "POST")
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["participation_mode"] as? String, "full")
            XCTAssertNil(obj["enabled"]) // 部分字段：只传 mode
            return (200, Data(#"{"enabled":true,"participation_mode":"full"}"#.utf8))
        }
        let s = try await makeClient().updateScreenContextSettings(["participation_mode": "full"])
        XCTAssertEqual(s.mode, .full)
    }

    // 行为：更新排除项数组通过 POST 提交
    func test_updateScreenContext_posts_array_body() async throws {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["exclude_apps"] as? [String], ["微信", "钉钉"])
            return (200, Data(#"{"exclude_apps":["微信","钉钉"]}"#.utf8))
        }
        let s = try await makeClient().updateScreenContextSettings(["exclude_apps": ["微信", "钉钉"]])
        XCTAssertEqual(s.excludeApps, ["微信", "钉钉"])
    }
}
