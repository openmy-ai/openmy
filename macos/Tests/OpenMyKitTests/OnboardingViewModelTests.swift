import XCTest
@testable import OpenMyKit

@MainActor
final class OnboardingViewModelTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeVM() -> OnboardingViewModel {
        OnboardingViewModel(client: APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked()))
    }

    func stateJSON(stage: String, current: String) -> Data {
        Data("""
        {"stage":"\(stage)","completed":\(stage == "ready"),
         "recommended_provider":"funasr","current_provider":"\(current)",
         "headline":"标题","next_step":"下一步",
         "choices":{"local":[{"name":"funasr","label":"FunASR","description":"本地",
            "type":"local","ready":true,"is_active":false,"is_recommended":true,"needs_api_key":false}],
            "cloud":[]}}
        """.utf8)
    }

    // 行为：load 拉取状态与可选引擎
    func test_load_populates_state() async {
        MockURLProtocol.handler = { _ in (200, self.stateJSON(stage: "choose_provider", current: "")) }
        let vm = makeVM()
        await vm.load()
        XCTAssertEqual(vm.state?.stage, "choose_provider")
        XCTAssertEqual(vm.providers.count, 1)
        XCTAssertFalse(vm.completed)
    }

    // 行为：select 选引擎后重新拉状态，completed 翻转
    func test_select_then_reloads() async {
        MockURLProtocol.handler = { _ in (200, self.stateJSON(stage: "choose_provider", current: "")) }
        let vm = makeVM()
        await vm.load()

        MockURLProtocol.handler = { req in
            if req.url?.path == "/api/onboarding/select" {
                return (200, Data(#"{"success":true,"provider":"funasr"}"#.utf8))
            }
            return (200, self.stateJSON(stage: "ready", current: "funasr"))
        }
        await vm.select("funasr")
        XCTAssertTrue(vm.completed)
        XCTAssertEqual(vm.state?.currentProvider, "funasr")
    }

    // 行为：load 失败记录错误
    func test_load_error() async {
        MockURLProtocol.handler = { _ in (500, Data("{}".utf8)) }
        let vm = makeVM()
        await vm.load()
        XCTAssertNil(vm.state)
        XCTAssertNotNil(vm.errorMessage)
    }
}
