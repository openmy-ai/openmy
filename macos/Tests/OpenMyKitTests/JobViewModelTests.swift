import XCTest
@testable import OpenMyKit

@MainActor
final class JobViewModelTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeVM() -> JobViewModel {
        JobViewModel(client: APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked()))
    }

    func jobJSON(id: String, status: String, currentStep: String = "", canSkip: Bool = false) -> Data {
        Data("""
        {"job_id":"\(id)","kind":"run","status":"\(status)","current_step":"\(currentStep)",
         "error":"","can_pause":true,"can_skip":\(canSkip),"steps":[]}
        """.utf8)
    }

    // 行为：start 创建任务并存入
    func test_start_stores_created_job() async {
        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "new1", status: "queued")) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        XCTAssertEqual(vm.job?.jobId, "new1")
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：refresh 用当前任务 id 拉最新状态
    func test_refresh_updates_status() async {
        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "j1", status: "queued")) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])

        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/pipeline/jobs/j1")
            return (200, self.jobJSON(id: "j1", status: "running", currentStep: "distill", canSkip: true))
        }
        await vm.refresh()
        XCTAssertEqual(vm.job?.status, "running")
        XCTAssertTrue(vm.canSkip)
    }

    // 行为：无任务时 refresh 不崩、不发请求
    func test_refresh_noop_without_job() async {
        MockURLProtocol.handler = { _ in XCTFail("不应发请求"); return (200, Data("{}".utf8)) }
        let vm = makeVM()
        await vm.refresh()
        XCTAssertNil(vm.job)
    }

    // 行为：pause 调用动作并更新任务
    func test_pause_updates_job() async {
        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "j1", status: "queued")) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])

        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/pipeline/jobs/j1/pause")
            return (200, self.jobJSON(id: "j1", status: "paused"))
        }
        await vm.pause()
        XCTAssertEqual(vm.job?.status, "paused")
    }

    // 行为：isActive 在终态为 false
    func test_isActive_reflects_terminal() async {
        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "j1", status: "running")) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        XCTAssertTrue(vm.isActive)

        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "j1", status: "succeeded")) }
        await vm.refresh()
        XCTAssertFalse(vm.isActive)
    }

    // 行为：interrupted 也是终态（后端重启恢复用），轮询应停止
    func test_interrupted_is_terminal() async {
        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "j1", status: "running")) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "j1", status: "interrupted")) }
        await vm.refresh()
        XCTAssertFalse(vm.isActive)
    }

    // 行为：clear 清空当前任务，让界面回到日报浏览
    func test_clear_resets_job() async {
        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "j1", status: "succeeded")) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        XCTAssertNotNil(vm.job)
        vm.clear()
        XCTAssertNil(vm.job)
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：请求失败时记录错误信息，不崩
    func test_start_records_error_on_failure() async {
        MockURLProtocol.handler = { _ in (500, Data("{}".utf8)) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        XCTAssertNil(vm.job)
        XCTAssertNotNil(vm.errorMessage)
    }
}
