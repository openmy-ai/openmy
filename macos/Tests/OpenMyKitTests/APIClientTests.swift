import XCTest
@testable import OpenMyKit

final class APIClientTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeClient() -> APIClient {
        APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked())
    }

    // 行为：health() 命中 /api/health 并解码 status
    func test_health_decodes_status() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/health")
            return (200, Data(#"{"status":"ok"}"#.utf8))
        }
        let result = try await makeClient().health()
        XCTAssertEqual(result, HealthStatus(status: "ok"))
    }

    // 行为：dates() 解码日期列表，忽略未用字段
    func test_dates_decodes_list() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/dates")
            let json = #"[{"date":"2026-06-05","segments":12,"word_count":3400,"summary":"忙碌的一天","extra":"忽略"}]"#
            return (200, Data(json.utf8))
        }
        let result = try await makeClient().dates()
        XCTAssertEqual(result.count, 1)
        XCTAssertEqual(result[0].date, "2026-06-05")
        XCTAssertEqual(result[0].segments, 12)
        XCTAssertEqual(result[0].wordCount, 3400)
        XCTAssertEqual(result[0].summary, "忙碌的一天")
    }

    // 行为：briefing(date) 解码日报，含对象列表
    func test_briefing_decodes() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/briefing/2026-06-05")
            let json = """
            {"date":"2026-06-05","summary":"忙碌",
             "key_events":["事件A","事件B"],"todos_open":["待办X"],
             "insights":[{"topic":"自驾游","content":"去新疆"}],
             "time_blocks":[{"period":"下午","summary":"测试模板"}],
             "total_words":38925,"total_scenes":32,"voice_hours":5.0}
            """
            return (200, Data(json.utf8))
        }
        let b = try await makeClient().briefing(date: "2026-06-05")
        XCTAssertEqual(b.date, "2026-06-05")
        XCTAssertEqual(b.summary, "忙碌")
        XCTAssertEqual(b.keyEvents, ["事件A", "事件B"])
        XCTAssertEqual(b.todosOpen, ["待办X"])
        XCTAssertEqual(b.insights.first?.topic, "自驾游")
        XCTAssertEqual(b.timeBlocks.first?.period, "下午")
        XCTAssertEqual(b.totalWords, 38925)
    }

    // 行为：dateDetail 解码逐段转写
    func test_dateDetail_decodes_segments() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/date/2026-06-05")
            let json = #"{"date":"2026-06-05","segments":[{"time":"00:01","text":"你好世界","preview":"你好"},{"time":"00:05","text":"第二段","preview":"第二"}],"word_count":4}"#
            return (200, Data(json.utf8))
        }
        let d = try await makeClient().dateDetail(date: "2026-06-05")
        XCTAssertEqual(d.date, "2026-06-05")
        XCTAssertEqual(d.segments.count, 2)
        XCTAssertEqual(d.segments.first?.time, "00:01")
        XCTAssertEqual(d.segments.first?.text, "你好世界")
    }

    // 行为：briefing 缺省列表字段不报错
    func test_briefing_tolerates_missing_lists() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"date":"2026-06-06","summary":"空"}"#.utf8))
        }
        let b = try await makeClient().briefing(date: "2026-06-06")
        XCTAssertEqual(b.keyEvents, [])
        XCTAssertEqual(b.insights, [])
    }

    // 行为：onboarding() 解码阶段与可选引擎
    func test_onboarding_decodes() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/onboarding")
            let json = """
            {"stage":"choose_provider","completed":false,
             "recommended_provider":"funasr","current_provider":"",
             "headline":"先选引擎","next_step":"选一个",
             "choices":{"local":[{"name":"funasr","label":"FunASR","description":"本地中文",
                "type":"local","ready":true,"is_active":false,"is_recommended":true,"needs_api_key":false}],
                "cloud":[{"name":"gemini","label":"Gemini","description":"云端",
                "type":"api","ready":false,"is_active":false,"is_recommended":false,"needs_api_key":true}]}}
            """
            return (200, Data(json.utf8))
        }
        let o = try await makeClient().onboarding()
        XCTAssertEqual(o.stage, "choose_provider")
        XCTAssertFalse(o.completed)
        XCTAssertEqual(o.recommendedProvider, "funasr")
        XCTAssertEqual(o.allProviders.count, 2)
        XCTAssertEqual(o.allProviders.first { $0.isRecommended }?.name, "funasr")
        XCTAssertTrue(o.allProviders.first { $0.name == "gemini" }!.needsApiKey)
    }

    // 行为：selectProvider 发 POST 到 /api/onboarding/select，body 带 provider
    func test_selectProvider_posts() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/onboarding/select")
            XCTAssertEqual(req.httpMethod, "POST")
            let body = req.bodyData ?? Data()
            let obj = try JSONSerialization.jsonObject(with: body) as! [String: Any]
            XCTAssertEqual(obj["provider"] as? String, "funasr")
            return (200, Data(#"{"success":true,"provider":"funasr"}"#.utf8))
        }
        let ok = try await makeClient().selectProvider("funasr")
        XCTAssertTrue(ok)
    }

    // 行为：job(id) 解码四阶段任务
    func test_job_decodes_steps() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/pipeline/jobs/abc123")
            let json = """
            {"job_id":"abc123","kind":"run","status":"running","current_step":"distill",
             "error":"","can_pause":true,"can_skip":true,"progress_pct":75,
             "steps":[
               {"name":"transcribe","label":"转写","status":"done","result_summary":"完成"},
               {"name":"clean","label":"清洗","status":"done","result_summary":"完成"},
               {"name":"segment","label":"场景切分","status":"done","result_summary":"完成"},
               {"name":"distill","label":"蒸馏","status":"running","result_summary":"进行中"}]}
            """
            return (200, Data(json.utf8))
        }
        let job = try await makeClient().job(id: "abc123")
        XCTAssertEqual(job.jobId, "abc123")
        XCTAssertEqual(job.status, "running")
        XCTAssertEqual(job.steps.count, 4)
        XCTAssertEqual(job.currentStep, "distill")
        XCTAssertTrue(job.canSkip)
        XCTAssertEqual(job.steps.last?.label, "蒸馏")
        XCTAssertEqual(job.steps.last?.status, "running")
    }

    // 行为：jobs() 解码列表
    func test_jobs_decodes_list() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/pipeline/jobs")
            return (200, Data(#"[{"job_id":"j1","kind":"run","status":"succeeded","current_step":"","error":"","can_pause":false,"can_skip":false,"steps":[]}]"#.utf8))
        }
        let jobs = try await makeClient().jobs()
        XCTAssertEqual(jobs.count, 1)
        XCTAssertEqual(jobs[0].jobId, "j1")
    }

    // 行为：createJob 发 POST，body 带 audio_files
    func test_createJob_posts_audio_files() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/pipeline/jobs")
            XCTAssertEqual(req.httpMethod, "POST")
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["audio_files"] as? [String], ["/tmp/a.wav"])
            return (200, Data(#"{"job_id":"new1","kind":"run","status":"queued","current_step":"","error":"","can_pause":false,"can_skip":true,"steps":[]}"#.utf8))
        }
        let job = try await makeClient().createJob(audioFiles: ["/tmp/a.wav"], targetDate: nil)
        XCTAssertEqual(job.jobId, "new1")
    }

    // 行为：jobAction 发 POST 到 /api/pipeline/jobs/{id}/{action}
    func test_jobAction_posts() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/pipeline/jobs/abc/pause")
            XCTAssertEqual(req.httpMethod, "POST")
            return (200, Data(#"{"job_id":"abc","kind":"run","status":"paused","current_step":"distill","error":"","can_pause":false,"can_skip":false,"steps":[]}"#.utf8))
        }
        let job = try await makeClient().jobAction(id: "abc", action: .pause)
        XCTAssertEqual(job.status, "paused")
    }

    // 行为：upload 发 multipart POST 到 /api/upload，解码落地路径
    func test_upload_posts_multipart_and_decodes() async throws {
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("om_upload_\(UUID().uuidString).wav")
        try Data("fake-audio".utf8).write(to: tmp)
        defer { try? FileManager.default.removeItem(at: tmp) }

        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/upload")
            XCTAssertEqual(req.httpMethod, "POST")
            let contentType = req.value(forHTTPHeaderField: "Content-Type") ?? ""
            XCTAssertTrue(contentType.hasPrefix("multipart/form-data; boundary="))
            let body = String(data: req.bodyData ?? Data(), encoding: .utf8) ?? ""
            XCTAssertTrue(body.contains("name=\"file\""))
            XCTAssertTrue(body.contains("fake-audio"))
            return (200, Data(#"{"file_path":"/data/inbox/20260625T101010_x.wav","filename":"x.wav","size_bytes":10}"#.utf8))
        }
        let result = try await makeClient().upload(fileURL: tmp)
        XCTAssertEqual(result.filePath, "/data/inbox/20260625T101010_x.wav")
        XCTAssertEqual(result.filename, "x.wav")
        XCTAssertEqual(result.sizeBytes, 10)
    }

    // 行为：upload 失败（后端报错）抛 badStatus
    func test_upload_throws_on_error() async throws {
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("om_upload_\(UUID().uuidString).wav")
        try Data("x".utf8).write(to: tmp)
        defer { try? FileManager.default.removeItem(at: tmp) }

        MockURLProtocol.handler = { _ in (400, Data(#"{"error":"unsupported file type"}"#.utf8)) }
        do {
            _ = try await makeClient().upload(fileURL: tmp)
            XCTFail("应抛错")
        } catch {
            XCTAssertEqual(error as? APIError, .badStatus(400))
        }
    }

    // 行为：createJob 带 source_file / source_size_bytes 时一并发出
    func test_createJob_posts_source_fields() async throws {
        MockURLProtocol.handler = { req in
            let obj = try JSONSerialization.jsonObject(with: req.bodyData ?? Data()) as! [String: Any]
            XCTAssertEqual(obj["source_file"] as? String, "rec.m4a")
            XCTAssertEqual(obj["source_size_bytes"] as? Int, 2048)
            return (200, Data(#"{"job_id":"j2","kind":"run","status":"queued","steps":[]}"#.utf8))
        }
        let job = try await makeClient().createJob(
            audioFiles: ["/data/inbox/rec.m4a"], targetDate: nil,
            sourceFile: "rec.m4a", sourceSizeBytes: 2048
        )
        XCTAssertEqual(job.jobId, "j2")
    }

    // 行为：PipelineJob 解码 eta_seconds / source_file / target_date / log_lines
    func test_job_decodes_extended_fields() async throws {
        MockURLProtocol.handler = { _ in
            let json = """
            {"job_id":"abc","kind":"run","status":"running","current_step":"transcribe",
             "error":"","can_pause":true,"can_skip":false,"progress_pct":40,
             "eta_seconds":125,"source_file":"晨会.m4a","target_date":"2026-06-25",
             "log_lines":["开始转写","进度 40%"],"steps":[]}
            """
            return (200, Data(json.utf8))
        }
        let job = try await makeClient().job(id: "abc")
        XCTAssertEqual(job.etaSeconds, 125)
        XCTAssertEqual(job.sourceFile, "晨会.m4a")
        XCTAssertEqual(job.targetDate, "2026-06-25")
        XCTAssertEqual(job.logLines, ["开始转写", "进度 40%"])
    }

    // 行为：扩展字段缺省时安全降级（eta=nil，target_date 空串归一为 nil，列表为空）
    func test_job_tolerates_missing_extended_fields() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"job_id":"abc","kind":"run","status":"queued","target_date":"","steps":[]}"#.utf8))
        }
        let job = try await makeClient().job(id: "abc")
        XCTAssertNil(job.etaSeconds)
        XCTAssertNil(job.targetDate)
        XCTAssertEqual(job.sourceFile, "")
        XCTAssertEqual(job.logLines, [])
    }

    // 行为：非 2xx 状态码抛 badStatus
    func test_get_throws_on_non2xx() async {
        MockURLProtocol.handler = { _ in (500, Data("{}".utf8)) }
        do {
            _ = try await makeClient().health()
            XCTFail("应抛错")
        } catch {
            XCTAssertEqual(error as? APIError, .badStatus(500))
        }
    }
}
