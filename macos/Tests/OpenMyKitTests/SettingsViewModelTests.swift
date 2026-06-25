import XCTest
@testable import OpenMyKit

@MainActor
final class SettingsViewModelTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeVM() -> SettingsViewModel {
        SettingsViewModel(client: APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked()))
    }

    // 行为：load() 拉取并填充 settings
    func test_load_populates_settings() async {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"enabled":true,"participation_mode":"summary_only","exclude_apps":["微信"]}"#.utf8))
        }
        let vm = makeVM()
        await vm.load()
        XCTAssertEqual(vm.settings?.mode, .summaryOnly)
        XCTAssertEqual(vm.settings?.excludeApps, ["微信"])
        XCTAssertNil(vm.errorMessage)
        XCTAssertFalse(vm.isLoading)
    }

    // 行为：load 失败时 errorMessage 置位，settings 保持原值
    func test_load_failure_sets_error() async {
        MockURLProtocol.handler = { _ in (500, Data()) }
        let vm = makeVM()
        await vm.load()
        XCTAssertNil(vm.settings)
        XCTAssertNotNil(vm.errorMessage)
    }

    // 行为：setMode 同时联动 enabled（非 off→true），避免后端合并卡在旧 enabled=false
    func test_setMode_updates_settings() async {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["participation_mode"] as? String, "full")
            XCTAssertEqual(obj["enabled"] as? Bool, true)  // 关键：切到非 off 必须同发 enabled=true
            return (200, Data(#"{"enabled":true,"participation_mode":"full"}"#.utf8))
        }
        let vm = makeVM()
        let ok = await vm.setMode(.full)
        XCTAssertTrue(ok)
        XCTAssertEqual(vm.settings?.mode, .full)
    }

    // 行为：setMode(.off) 同发 enabled=false
    func test_setMode_off_disables() async {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["participation_mode"] as? String, "off")
            XCTAssertEqual(obj["enabled"] as? Bool, false)
            return (200, Data(#"{"enabled":false,"participation_mode":"off"}"#.utf8))
        }
        let vm = makeVM()
        _ = await vm.setMode(.off)
        XCTAssertFalse(vm.settings?.enabled ?? true)
    }

    // 行为：setEnabled 提交 enabled 部分字段
    func test_setEnabled_posts_enabled() async {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["enabled"] as? Bool, false)
            return (200, Data(#"{"enabled":false,"participation_mode":"summary_only"}"#.utf8))
        }
        let vm = makeVM()
        let ok = await vm.setEnabled(false)
        XCTAssertTrue(ok)
        XCTAssertFalse(vm.settings?.enabled ?? true)
    }

    // 行为：saveExclusions 只传非 nil 字段
    func test_saveExclusions_posts_only_nonNil() async {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["exclude_apps"] as? [String], ["微信"])
            XCTAssertNil(obj["exclude_domains"])
            return (200, Data(#"{"exclude_apps":["微信"]}"#.utf8))
        }
        let vm = makeVM()
        let ok = await vm.saveExclusions(apps: ["微信"])
        XCTAssertTrue(ok)
        XCTAssertEqual(vm.settings?.excludeApps, ["微信"])
    }

    // 行为：saveExclusions 全 nil 时不发请求、直接成功
    func test_saveExclusions_noop_when_all_nil() async {
        MockURLProtocol.handler = { _ in
            XCTFail("不应发请求")
            return (200, Data("{}".utf8))
        }
        let vm = makeVM()
        let ok = await vm.saveExclusions()
        XCTAssertTrue(ok)
    }

    // 行为：update 失败时 errorMessage 置位、返回 false、settings 不变
    func test_update_failure_keeps_settings() async {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"enabled":true,"participation_mode":"summary_only"}"#.utf8))
        }
        let vm = makeVM()
        await vm.load()
        MockURLProtocol.handler = { _ in (500, Data()) }
        let ok = await vm.update(["participation_mode": "full"])
        XCTAssertFalse(ok)
        XCTAssertNotNil(vm.errorMessage)
        XCTAssertEqual(vm.settings?.mode, .summaryOnly)
    }
}
