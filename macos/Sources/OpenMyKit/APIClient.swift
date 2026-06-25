import Foundation

/// 健康检查响应：GET /api/health → {"status": "ok"}
public struct HealthStatus: Decodable, Equatable, Sendable {
    public let status: String
}

/// 已处理日期条目：GET /api/dates 列表项。未用字段忽略。
public struct DayEntry: Decodable, Equatable, Sendable, Identifiable {
    public let date: String
    public let segments: Int
    public let wordCount: Int
    public let summary: String

    public var id: String { date }

    enum CodingKeys: String, CodingKey {
        case date, segments, summary
        case wordCount = "word_count"
    }
}

/// 上传结果：POST /api/upload 的成功返回。后端把文件复制到 inbox 后回传落地路径。
/// 外置盘 copy-first 的关键：先上传拿到本地 file_path，再用它建任务。
public struct UploadResult: Decodable, Equatable, Sendable {
    /// 后端落地后的本地绝对路径，用于建任务。
    public let filePath: String
    /// 原始文件名，用于卡片展示。
    public let filename: String
    /// 落地后字节数。
    public let sizeBytes: Int

    enum CodingKeys: String, CodingKey {
        case filePath = "file_path"
        case filename
        case sizeBytes = "size_bytes"
    }
}

/// 全局搜索命中：GET /api/search?q={query} 列表项。
/// context 把命中词用 <mark>词</mark> 包裹（HTML 标记），rawContext 是不带标记的原文。
public struct SearchResult: Decodable, Equatable, Sendable, Identifiable {
    /// 命中所在日期，如 "2026-06-05"。
    public let date: String
    /// 命中所在段落的时间标记，如 "00:05"，可能为空。
    public let time: String
    /// 带 <mark> 标记的上下文片段，用于高亮渲染。
    public let context: String
    /// 不带标记的原文，用于无标记场景兜底。
    public let rawContext: String

    /// date+time+context 组合保证同一日期多命中项的稳定标识。
    public var id: String { "\(date)|\(time)|\(context)" }

    enum CodingKeys: String, CodingKey {
        case date, time, context
        case rawContext = "raw_context"
    }

    public init(date: String, time: String, context: String, rawContext: String) {
        self.date = date
        self.time = time
        self.context = context
        self.rawContext = rawContext
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decodeIfPresent(String.self, forKey: .date) ?? ""
        time = try c.decodeIfPresent(String.self, forKey: .time) ?? ""
        context = try c.decodeIfPresent(String.self, forKey: .context) ?? ""
        rawContext = try c.decodeIfPresent(String.self, forKey: .rawContext) ?? ""
    }
}

/// 全局统计：GET /api/stats。供侧栏顶部展示天/条/字与角色分布。
public struct Stats: Decodable, Equatable, Sendable {
    public let totalDates: Int
    public let totalWords: Int
    public let totalSegments: Int
    public let roleDistribution: [String: Int]

    enum CodingKeys: String, CodingKey {
        case totalDates = "total_dates"
        case totalWords = "total_words"
        case totalSegments = "total_segments"
        case roleDistribution = "role_distribution"
    }

    public init(totalDates: Int, totalWords: Int, totalSegments: Int, roleDistribution: [String: Int]) {
        self.totalDates = totalDates
        self.totalWords = totalWords
        self.totalSegments = totalSegments
        self.roleDistribution = roleDistribution
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        totalDates = try c.decodeIfPresent(Int.self, forKey: .totalDates) ?? 0
        totalWords = try c.decodeIfPresent(Int.self, forKey: .totalWords) ?? 0
        totalSegments = try c.decodeIfPresent(Int.self, forKey: .totalSegments) ?? 0
        roleDistribution = try c.decodeIfPresent([String: Int].self, forKey: .roleDistribution) ?? [:]
    }
}

/// OpenMy 后端 HTTP 客户端。对接 localhost:8420 的现有 Python 服务。
public struct APIClient: Sendable {
    let baseURL: URL
    let session: URLSession

    public init(
        baseURL: URL = URL(string: "http://localhost:8420")!,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
    }

    /// 健康检查。
    public func health() async throws -> HealthStatus {
        try await get("/api/health")
    }

    /// 已处理日期列表。
    public func dates() async throws -> [DayEntry] {
        try await get("/api/dates")
    }

    /// 某天日报。
    public func briefing(date: String) async throws -> Briefing {
        try await get("/api/briefing/\(date)")
    }

    /// 某天原始记录（逐段转写），用于从日报下钻。
    public func dateDetail(date: String) async throws -> DateDetail {
        try await get("/api/date/\(date)")
    }

    /// 拼出某天某 chunk 的音频流地址 /api/audio/{date}/{chunk_id}，供 AVPlayer 直接播放。
    /// 后端支持 HTTP Range(206)，AVPlayer 可按需 seek。
    public func audioURL(date: String, chunkId: String) -> URL {
        // 对 path 段做百分号编码，避免 chunkId/date 含特殊字符时拼出非法 URL（对齐 Web encodeURIComponent）。
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-._~"))
        let d = date.addingPercentEncoding(withAllowedCharacters: allowed) ?? date
        let c = chunkId.addingPercentEncoding(withAllowedCharacters: allowed) ?? chunkId
        return makeURL("/api/audio/\(d)/\(c)")
    }

    /// 全局搜索。空 query 后端返回 []，最多 20 条。
    /// 这里对空 query 直接短路返回 []，省掉一次必为空的请求。
    public func search(query: String) async throws -> [SearchResult] {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return [] }
        let encoded = trimmed.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? trimmed
        return try await get("/api/search?q=\(encoded)")
    }

    /// 全局统计（侧栏顶部天/条/字与角色分布）。
    public func stats() async throws -> Stats {
        try await get("/api/stats")
    }

    /// onboarding 状态。
    public func onboarding() async throws -> OnboardingState {
        try await get("/api/onboarding")
    }

    /// 选择 STT 引擎。返回是否成功。
    @discardableResult
    public func selectProvider(_ provider: String) async throws -> Bool {
        struct Resp: Decodable { let success: Bool }
        let resp: Resp = try await post("/api/onboarding/select", body: ["provider": provider])
        return resp.success
    }

    /// 任务列表。
    public func jobs() async throws -> [PipelineJob] {
        try await get("/api/pipeline/jobs")
    }

    /// 单个任务状态（轮询用）。
    public func job(id: String) async throws -> PipelineJob {
        try await get("/api/pipeline/jobs/\(id)")
    }

    /// 上传单个音频文件到后端 inbox。返回落地路径，供建任务用。
    /// multipart/form-data，字段名固定为 `file`，对齐 Web 的 fetch('/api/upload')。
    public func upload(fileURL: URL) async throws -> UploadResult {
        let fileData = try Data(contentsOf: fileURL)
        let filename = fileURL.lastPathComponent
        let boundary = "Boundary-\(UUID().uuidString)"

        var body = Data()
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        body.append("Content-Type: application/octet-stream\r\n\r\n")
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n")

        var request = URLRequest(url: makeURL("/api/upload"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body

        let (data, response) = try await session.data(for: request)
        try Self.checkStatus(response)
        return try JSONDecoder().decode(UploadResult.self, from: data)
    }

    /// 创建转写任务。sourceFile/sourceSizeBytes 来自上传结果，供首页卡片展示。
    public func createJob(
        audioFiles: [String],
        targetDate: String? = nil,
        sourceFile: String? = nil,
        sourceSizeBytes: Int? = nil
    ) async throws -> PipelineJob {
        var body: [String: Any] = ["audio_files": audioFiles, "kind": "run"]
        if let targetDate { body["target_date"] = targetDate }
        if let sourceFile { body["source_file"] = sourceFile }
        if let sourceSizeBytes { body["source_size_bytes"] = sourceSizeBytes }
        return try await post("/api/pipeline/jobs", body: body)
    }

    /// 对任务执行控制动作（暂停/继续/取消/跳过）。
    public func jobAction(id: String, action: JobAction) async throws -> PipelineJob {
        try await post("/api/pipeline/jobs/\(id)/\(action.rawValue)", body: [:])
    }

    // MARK: - 内部

    /// 发 GET 请求并解码 JSON。
    func get<T: Decodable>(_ path: String) async throws -> T {
        let (data, response) = try await session.data(from: makeURL(path))
        try Self.checkStatus(response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    /// 发 POST 请求（JSON body）并解码 JSON 响应。
    @discardableResult
    func post<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await session.data(for: request)
        try Self.checkStatus(response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    /// 拼接 baseURL 与路径，避免 appendingPathComponent 对前导斜杠的转义问题。
    func makeURL(_ path: String) -> URL {
        let base = baseURL.absoluteString
        let trimmed = base.hasSuffix("/") ? String(base.dropLast()) : base
        return URL(string: trimmed + path)!
    }

    static func checkStatus(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.badStatus(http.statusCode)
        }
    }
}

public enum APIError: Error, Equatable, Sendable {
    case badStatus(Int)
}

private extension Data {
    /// 追加 UTF-8 字符串，构造 multipart body 用。
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) { append(data) }
    }
}
