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

    // 行为：暂停后 resume 调用动作并把任务切回 running
    func test_resume_updates_job() async {
        MockURLProtocol.handler = { _ in (200, self.jobJSON(id: "j1", status: "paused")) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        XCTAssertEqual(vm.job?.status, "paused")

        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/pipeline/jobs/j1/resume")
            return (200, self.jobJSON(id: "j1", status: "running"))
        }
        await vm.resume()
        XCTAssertEqual(vm.job?.status, "running")
        XCTAssertTrue(vm.isActive)
    }

    // 行为：请求失败时记录错误信息，不崩
    func test_start_records_error_on_failure() async {
        MockURLProtocol.handler = { _ in (500, Data("{}".utf8)) }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        XCTAssertNil(vm.job)
        XCTAssertNotNil(vm.errorMessage)
    }

    /// 写一个临时音频文件，返回 URL；调用方负责清理。
    func makeTempAudio() -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("om_vm_\(UUID().uuidString).wav")
        try? Data("audio".utf8).write(to: url)
        return url
    }

    // 行为：start(uploading:) 先上传拿 file_path，再用它建任务
    func test_start_uploading_then_creates_job() async {
        let url = makeTempAudio()
        defer { try? FileManager.default.removeItem(at: url) }

        MockURLProtocol.handler = { req in
            switch req.url?.path {
            case "/api/upload":
                return (200, Data(#"{"file_path":"/data/inbox/r.wav","filename":"r.wav","size_bytes":5}"#.utf8))
            case "/api/pipeline/jobs":
                // 确认建任务用的是上传返回的 file_path，并带上 source 字段
                let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
                XCTAssertEqual(obj["audio_files"] as? [String], ["/data/inbox/r.wav"])
                XCTAssertEqual(obj["source_file"] as? String, "r.wav")
                return (200, self.jobJSON(id: "up1", status: "queued"))
            default:
                XCTFail("意外路径 \(req.url?.path ?? "")")
                return (500, Data())
            }
        }
        let vm = makeVM()
        await vm.start(uploading: [url])
        XCTAssertEqual(vm.job?.jobId, "up1")
        XCTAssertFalse(vm.isUploading)
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：上传失败时记录错误且不建任务
    func test_start_uploading_records_error_on_upload_failure() async {
        let url = makeTempAudio()
        defer { try? FileManager.default.removeItem(at: url) }

        MockURLProtocol.handler = { req in
            if req.url?.path == "/api/pipeline/jobs" { XCTFail("上传失败不应建任务") }
            return (400, Data(#"{"error":"unsupported file type"}"#.utf8))
        }
        let vm = makeVM()
        await vm.start(uploading: [url])
        XCTAssertNil(vm.job)
        XCTAssertNotNil(vm.errorMessage)
        XCTAssertFalse(vm.isUploading)
    }

    // 行为：空文件列表不发请求、不报错
    func test_start_uploading_noop_on_empty() async {
        MockURLProtocol.handler = { _ in XCTFail("不应发请求"); return (200, Data()) }
        let vm = makeVM()
        await vm.start(uploading: [])
        XCTAssertNil(vm.job)
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：retry 用上次同样的输入重建任务
    func test_retry_recreates_with_same_input() async {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["audio_files"] as? [String], ["/tmp/a.wav"])
            return (200, self.jobJSON(id: "r1", status: "queued"))
        }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        vm.clear()
        await vm.retry()
        XCTAssertEqual(vm.job?.jobId, "r1")
    }

    // 行为：上传式启动后 retry 复用已上传路径，不再重复上传到 inbox
    func test_retry_reuses_uploaded_paths() async {
        let url = makeTempAudio()
        defer { try? FileManager.default.removeItem(at: url) }

        final class Counter: @unchecked Sendable { var uploads = 0; var creates = 0 }
        let counter = Counter()
        MockURLProtocol.handler = { req in
            switch req.url?.path {
            case "/api/upload":
                counter.uploads += 1
                return (200, Data(#"{"file_path":"/data/inbox/r.wav","filename":"r.wav","size_bytes":5}"#.utf8))
            case "/api/pipeline/jobs":
                counter.creates += 1
                let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
                // 重建仍用已上传的 file_path，不是原始本地路径
                XCTAssertEqual(obj["audio_files"] as? [String], ["/data/inbox/r.wav"])
                return (200, self.jobJSON(id: "up1", status: "failed"))
            default:
                return (500, Data())
            }
        }
        let vm = makeVM()
        await vm.start(uploading: [url])
        await vm.retry()
        XCTAssertEqual(counter.uploads, 1, "retry 不应再次上传")
        XCTAssertEqual(counter.creates, 2, "retry 应重新建任务")
    }

    // 行为：未启动过时 retry 不发请求
    func test_retry_noop_without_prior_start() async {
        MockURLProtocol.handler = { _ in XCTFail("不应发请求"); return (200, Data()) }
        let vm = makeVM()
        await vm.retry()
        XCTAssertNil(vm.job)
    }

    // 行为：暴露 target_date / source_file / eta / log_lines 给视图
    func test_exposes_job_metadata() async {
        MockURLProtocol.handler = { _ in
            (200, Data("""
            {"job_id":"m1","kind":"run","status":"running","current_step":"transcribe",
             "error":"","can_pause":true,"can_skip":false,"eta_seconds":90,
             "source_file":"会议.m4a","target_date":"2026-06-25","log_lines":["L1","L2"],"steps":[]}
            """.utf8))
        }
        let vm = makeVM()
        await vm.start(audioFiles: ["/tmp/a.wav"])
        XCTAssertEqual(vm.targetDate, "2026-06-25")
        XCTAssertEqual(vm.sourceFile, "会议.m4a")
        XCTAssertEqual(vm.etaSeconds, 90)
        XCTAssertEqual(vm.logLines, ["L1", "L2"])
    }
}
