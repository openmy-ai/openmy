import Foundation

/// 健康检查响应：GET /api/health → {"status": "ok"}
public struct HealthStatus: Decodable, Equatable, Sendable {
    public let status: String
}

/// 时间线条目：GET /api/dates 列表项的 timeline 元素 {time, preview}。缺字段降级空串。
public struct TimelineEntry: Decodable, Equatable, Sendable {
    public let time: String
    public let preview: String

    enum CodingKeys: String, CodingKey {
        case time, preview
    }

    public init(time: String, preview: String) {
        self.time = time
        self.preview = preview
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        time = try c.decodeIfPresent(String.self, forKey: .time) ?? ""
        preview = try c.decodeIfPresent(String.self, forKey: .preview) ?? ""
    }
}

/// 已处理日期条目：GET /api/dates 列表项。未用字段忽略。
/// meta 来源的 events/decisions/todos 实测常为空，按 lenient 处理（缺失/异型降级空）。
public struct DayEntry: Decodable, Equatable, Sendable, Identifiable {
    public let date: String
    public let segments: Int
    public let wordCount: Int
    public let summary: String
    /// 决策文本列表。后端项是对象（含 decision/what 等异型键），这里抽成可显示文本。缺失降级空。
    public let decisions: [String]
    /// 待办文本列表。后端项是对象（含 task/what 等异型键），抽成可显示文本。缺失降级空。
    public let todos: [String]
    /// 发生事件文本列表。抽成可显示文本，缺失降级空。
    public let events: [String]
    /// 逐段时间线 {time, preview}，用于摘要兜底。缺失降级空。
    public let timeline: [TimelineEntry]

    public var id: String { date }

    enum CodingKeys: String, CodingKey {
        case date, segments, summary, decisions, todos, events, timeline
        case wordCount = "word_count"
    }

    public init(
        date: String, segments: Int, wordCount: Int, summary: String,
        decisions: [String] = [], todos: [String] = [], events: [String] = [],
        timeline: [TimelineEntry] = []
    ) {
        self.date = date
        self.segments = segments
        self.wordCount = wordCount
        self.summary = summary
        self.decisions = decisions
        self.todos = todos
        self.events = events
        self.timeline = timeline
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        segments = try c.decodeIfPresent(Int.self, forKey: .segments) ?? 0
        wordCount = try c.decodeIfPresent(Int.self, forKey: .wordCount) ?? 0
        summary = try c.decodeIfPresent(String.self, forKey: .summary) ?? ""
        // decisions 项取 decision/what，对齐 reports.js item.decisions[].decision || .what
        decisions = MetaText.extractList(c, key: .decisions, keys: ["decision", "what"])
        // todos 项取 task/what，对齐 reports.js item.todos[].task || .what
        todos = MetaText.extractList(c, key: .todos, keys: ["task", "what"])
        // events 项取 summary/what/content 等通用键
        events = MetaText.extractList(c, key: .events, keys: ["summary", "what", "content", "event"])
        timeline = ((try? c.decodeIfPresent([TimelineEntry].self, forKey: .timeline)) ?? []) ?? []
    }
}

/// meta 异型条目的文本抽取工具：项可能是字符串，也可能是对象（候选键里取第一个非空）。
enum MetaText {
    /// 从某个 key 下解码一个异型条目列表，每项抽成可显示文本，空文本丢弃。
    /// 兼容三种形态：字符串数组、对象数组（按 candidateKeys 取文本）、缺失（返回空）。
    static func extractList(
        _ container: KeyedDecodingContainer<DayEntry.CodingKeys>,
        key: DayEntry.CodingKeys,
        keys candidateKeys: [String]
    ) -> [String] {
        guard let items = try? container.decodeIfPresent([MetaItem].self, forKey: key) else {
            return []
        }
        return items.compactMap { $0.text(preferring: candidateKeys) }
    }

    /// 从任意可显示字段抽文本，供 DateMeta 等复用（候选键顺序固定，对齐 daily.js）。
    static let displayKeys = [
        "summary", "what", "task", "content", "decision", "fact", "intent",
    ]
}

/// 单个 meta 条目：可能是裸字符串或对象。对象按候选键取第一个非空文本。
struct MetaItem: Decodable, Equatable, Sendable {
    private let raw: String
    private let fields: [String: String]

    init(from decoder: Decoder) throws {
        if let single = try? decoder.singleValueContainer(),
           let s = try? single.decode(String.self) {
            raw = s
            fields = [:]
            return
        }
        raw = ""
        var collected: [String: String] = [:]
        if let c = try? decoder.container(keyedBy: DynamicKey.self) {
            for k in c.allKeys {
                if let v = try? c.decode(String.self, forKey: k) {
                    collected[k.stringValue] = v
                }
            }
        }
        fields = collected
    }

    /// 按候选键顺序取第一个非空文本；都没有时回退到通用展示键；再没有回退裸字符串。
    func text(preferring candidateKeys: [String]) -> String? {
        if !raw.isEmpty { return raw }
        for key in candidateKeys {
            if let v = fields[key], !v.isEmpty { return v }
        }
        for key in MetaText.displayKeys {
            if let v = fields[key], !v.isEmpty { return v }
        }
        return nil
    }

    /// 任意字符串键（动态解码用）。
    struct DynamicKey: CodingKey {
        var stringValue: String
        var intValue: Int? { nil }
        init?(stringValue: String) { self.stringValue = stringValue }
        init?(intValue: Int) { nil }
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
