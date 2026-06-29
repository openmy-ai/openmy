import Foundation

// MARK: - 证据回链引用

/// 证据回链引用：条目 provenance_refs 的一项。
/// 后端从 _build_provenance 落 date/scene_id/quote 三个核心字段（见 consolidation.py）。
/// date+scene_id 用于跳到对应日期段落，quote 是引文摘要。
public struct ProvenanceRef: Decodable, Equatable, Sendable {
    /// 证据所在日期，如 "2026-06-05"。
    public let date: String
    /// 场景 id，配合 date 定位段落。
    public let sceneId: String
    /// 引文/摘要文本。
    public let quote: String

    enum CodingKeys: String, CodingKey {
        case date, quote
        case sceneId = "scene_id"
    }

    public init(date: String, sceneId: String, quote: String) {
        self.date = date
        self.sceneId = sceneId
        self.quote = quote
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decodeIfPresent(String.self, forKey: .date) ?? ""
        sceneId = try c.decodeIfPresent(String.self, forKey: .sceneId) ?? ""
        quote = try c.decodeIfPresent(String.self, forKey: .quote) ?? ""
    }
}

// MARK: - 三类记忆条目

/// 未关闭待办：GET /api/context/loops 列表项（对应后端 OpenLoop）。
/// 修整定位用 title（后端 _resolve_item 优先 loop_id/id/title，前端只持 title 即可）。
public struct Loop: Decodable, Equatable, Sendable, Identifiable {
    public let loopId: String
    public let title: String
    public let status: String
    public let priority: String
    /// 等待对象（waiting_on），可空。
    public let waitingOn: String
    /// 关闭条件，可空。
    public let closeCondition: String
    public let provenanceRefs: [ProvenanceRef]

    /// loop_id 缺省时用 title 兜底，保证列表稳定标识。
    public var id: String { loopId.isEmpty ? title : loopId }

    enum CodingKeys: String, CodingKey {
        case title, status, priority
        case loopId = "loop_id"
        case waitingOn = "waiting_on"
        case closeCondition = "close_condition"
        case provenanceRefs = "provenance_refs"
    }

    public init(
        loopId: String, title: String, status: String = "open", priority: String = "medium",
        waitingOn: String = "", closeCondition: String = "", provenanceRefs: [ProvenanceRef] = []
    ) {
        self.loopId = loopId
        self.title = title
        self.status = status
        self.priority = priority
        self.waitingOn = waitingOn
        self.closeCondition = closeCondition
        self.provenanceRefs = provenanceRefs
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        loopId = try c.decodeIfPresent(String.self, forKey: .loopId) ?? ""
        title = try c.decodeIfPresent(String.self, forKey: .title) ?? ""
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? ""
        priority = try c.decodeIfPresent(String.self, forKey: .priority) ?? ""
        waitingOn = try c.decodeIfPresent(String.self, forKey: .waitingOn) ?? ""
        closeCondition = try c.decodeIfPresent(String.self, forKey: .closeCondition) ?? ""
        provenanceRefs = try c.decodeIfPresent([ProvenanceRef].self, forKey: .provenanceRefs) ?? []
    }
}

/// 活跃项目：GET /api/context/projects 列表项（对应后端 ProjectCard）。
public struct Project: Decodable, Equatable, Sendable, Identifiable {
    public let projectId: String
    public let title: String
    public let status: String
    public let priority: String
    /// 当前目标（current_goal），作为摘要展示。
    public let currentGoal: String
    public let provenanceRefs: [ProvenanceRef]

    public var id: String { projectId.isEmpty ? title : projectId }

    enum CodingKeys: String, CodingKey {
        case title, status, priority
        case projectId = "project_id"
        case currentGoal = "current_goal"
        case provenanceRefs = "provenance_refs"
    }

    public init(
        projectId: String, title: String, status: String = "active", priority: String = "medium",
        currentGoal: String = "", provenanceRefs: [ProvenanceRef] = []
    ) {
        self.projectId = projectId
        self.title = title
        self.status = status
        self.priority = priority
        self.currentGoal = currentGoal
        self.provenanceRefs = provenanceRefs
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        projectId = try c.decodeIfPresent(String.self, forKey: .projectId) ?? ""
        title = try c.decodeIfPresent(String.self, forKey: .title) ?? ""
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? ""
        priority = try c.decodeIfPresent(String.self, forKey: .priority) ?? ""
        currentGoal = try c.decodeIfPresent(String.self, forKey: .currentGoal) ?? ""
        provenanceRefs = try c.decodeIfPresent([ProvenanceRef].self, forKey: .provenanceRefs) ?? []
    }
}

/// 近期决策：GET /api/context/decisions 列表项（对应后端 DecisionItem）。
/// 修整定位优先用 decision 文本（后端 _resolve_item 顺序 decision_id/id/decision/topic）。
public struct Decision: Decodable, Equatable, Sendable, Identifiable {
    public let decisionId: String
    /// 决策主题（topic）。
    public let topic: String
    /// 决策内容（decision），作为主标题展示。
    public let decision: String
    /// 生效时间（effective_from）。
    public let effectiveFrom: String
    public let provenanceRefs: [ProvenanceRef]

    public var id: String { decisionId.isEmpty ? decision : decisionId }

    enum CodingKeys: String, CodingKey {
        case topic, decision
        case decisionId = "decision_id"
        case effectiveFrom = "effective_from"
        case provenanceRefs = "provenance_refs"
    }

    public init(
        decisionId: String, topic: String, decision: String, effectiveFrom: String = "",
        provenanceRefs: [ProvenanceRef] = []
    ) {
        self.decisionId = decisionId
        self.topic = topic
        self.decision = decision
        self.effectiveFrom = effectiveFrom
        self.provenanceRefs = provenanceRefs
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        decisionId = try c.decodeIfPresent(String.self, forKey: .decisionId) ?? ""
        topic = try c.decodeIfPresent(String.self, forKey: .topic) ?? ""
        decision = try c.decodeIfPresent(String.self, forKey: .decision) ?? ""
        effectiveFrom = try c.decodeIfPresent(String.self, forKey: .effectiveFrom) ?? ""
        provenanceRefs = try c.decodeIfPresent([ProvenanceRef].self, forKey: .provenanceRefs) ?? []
    }
}

// MARK: - 上下文快照

/// 上下文快照：GET /api/context（对应后端 get_context_payload）。
/// 缺字段全部降级为空，UI 直接读用不到的字段忽略。
public struct ContextSnapshot: Decodable, Equatable, Sendable {
    /// 一句话状态行（status_line）。
    public let statusLine: String
    /// 今日焦点（today_focus）字符串列表。
    public let todayFocus: [String]
    public let openLoops: [Loop]
    public let activeProjects: [Project]
    public let recentDecisions: [Decision]

    enum CodingKeys: String, CodingKey {
        case statusLine = "status_line"
        case todayFocus = "today_focus"
        case openLoops = "open_loops"
        case activeProjects = "active_projects"
        case recentDecisions = "recent_decisions"
    }

    public init(
        statusLine: String = "", todayFocus: [String] = [], openLoops: [Loop] = [],
        activeProjects: [Project] = [], recentDecisions: [Decision] = []
    ) {
        self.statusLine = statusLine
        self.todayFocus = todayFocus
        self.openLoops = openLoops
        self.activeProjects = activeProjects
        self.recentDecisions = recentDecisions
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        statusLine = try c.decodeIfPresent(String.self, forKey: .statusLine) ?? ""
        todayFocus = try c.decodeIfPresent([String].self, forKey: .todayFocus) ?? []
        openLoops = try c.decodeIfPresent([Loop].self, forKey: .openLoops) ?? []
        activeProjects = try c.decodeIfPresent([Project].self, forKey: .activeProjects) ?? []
        recentDecisions = try c.decodeIfPresent([Decision].self, forKey: .recentDecisions) ?? []
    }
}

// MARK: - 查询工作台结果

/// 查询命中项：GET /api/context/query 的 current_hits / temporal_buckets 各桶元素（对应后端 _make_hit）。
public struct ContextHit: Decodable, Equatable, Sendable, Identifiable {
    public let type: String
    public let hitId: String
    public let title: String
    public let summary: String
    public let date: String
    public let time: String
    public let status: String
    public let currentState: String
    public let provenanceRefs: [ProvenanceRef]

    public var id: String { "\(type)|\(hitId)|\(date)" }

    enum CodingKeys: String, CodingKey {
        case type, title, summary, date, time, status
        case hitId = "id"
        case currentState = "current_state"
        case provenanceRefs = "provenance_refs"
    }

    public init(
        type: String, hitId: String, title: String, summary: String = "", date: String = "",
        time: String = "", status: String = "", currentState: String = "",
        provenanceRefs: [ProvenanceRef] = []
    ) {
        self.type = type
        self.hitId = hitId
        self.title = title
        self.summary = summary
        self.date = date
        self.time = time
        self.status = status
        self.currentState = currentState
        self.provenanceRefs = provenanceRefs
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        type = try c.decodeIfPresent(String.self, forKey: .type) ?? ""
        hitId = try c.decodeIfPresent(String.self, forKey: .hitId) ?? ""
        title = try c.decodeIfPresent(String.self, forKey: .title) ?? ""
        summary = try c.decodeIfPresent(String.self, forKey: .summary) ?? ""
        date = try c.decodeIfPresent(String.self, forKey: .date) ?? ""
        time = try c.decodeIfPresent(String.self, forKey: .time) ?? ""
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? ""
        currentState = try c.decodeIfPresent(String.self, forKey: .currentState) ?? ""
        provenanceRefs = try c.decodeIfPresent([ProvenanceRef].self, forKey: .provenanceRefs) ?? []
    }
}

/// 时态分桶：query 结果的 temporal_buckets，每桶是命中数组。
public struct TemporalBuckets: Decodable, Equatable, Sendable {
    public let current: [ContextHit]
    public let future: [ContextHit]
    public let past: [ContextHit]
    public let closed: [ContextHit]

    public init(
        current: [ContextHit] = [], future: [ContextHit] = [],
        past: [ContextHit] = [], closed: [ContextHit] = []
    ) {
        self.current = current
        self.future = future
        self.past = past
        self.closed = closed
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        current = try c.decodeIfPresent([ContextHit].self, forKey: .current) ?? []
        future = try c.decodeIfPresent([ContextHit].self, forKey: .future) ?? []
        past = try c.decodeIfPresent([ContextHit].self, forKey: .past) ?? []
        closed = try c.decodeIfPresent([ContextHit].self, forKey: .closed) ?? []
    }

    enum CodingKeys: String, CodingKey {
        case current, future, past, closed
    }
}

/// 查询工作台结果：GET /api/context/query（对应后端 query_context 返回）。
/// evidence 用于证据回链：每项含 date/scene_id/quote/time_range。
public struct ContextQueryResult: Decodable, Equatable, Sendable {
    public let summary: String
    public let temporalBuckets: TemporalBuckets
    public let currentHits: [ContextHit]
    public let historyHits: [ContextHit]
    public let evidence: [ContextEvidence]

    enum CodingKeys: String, CodingKey {
        case summary, evidence
        case temporalBuckets = "temporal_buckets"
        case currentHits = "current_hits"
        case historyHits = "history_hits"
    }

    public init(
        summary: String = "", temporalBuckets: TemporalBuckets = TemporalBuckets(),
        currentHits: [ContextHit] = [], historyHits: [ContextHit] = [],
        evidence: [ContextEvidence] = []
    ) {
        self.summary = summary
        self.temporalBuckets = temporalBuckets
        self.currentHits = currentHits
        self.historyHits = historyHits
        self.evidence = evidence
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        summary = try c.decodeIfPresent(String.self, forKey: .summary) ?? ""
        temporalBuckets = try c.decodeIfPresent(TemporalBuckets.self, forKey: .temporalBuckets) ?? TemporalBuckets()
        currentHits = try c.decodeIfPresent([ContextHit].self, forKey: .currentHits) ?? []
        historyHits = try c.decodeIfPresent([ContextHit].self, forKey: .historyHits) ?? []
        evidence = try c.decodeIfPresent([ContextEvidence].self, forKey: .evidence) ?? []
    }
}

/// 查询证据项：query 结果的 evidence（对应后端 _resolve_evidence）。
/// date + time_range 用于证据回链跳到对应日期段落（对齐 Web jumpToEvidence）。
public struct ContextEvidence: Decodable, Equatable, Sendable, Identifiable {
    public let date: String
    public let sceneId: String
    public let quote: String
    /// 场景时间区间，如 "00:05-00:12"，跳转取起点。
    public let timeRange: String
    /// 场景摘要，quote 为空时兜底展示。
    public let sceneSummary: String

    public var id: String { "\(date)|\(sceneId)|\(quote.isEmpty ? sceneSummary : quote)" }

    enum CodingKeys: String, CodingKey {
        case date, quote
        case sceneId = "scene_id"
        case timeRange = "time_range"
        case sceneSummary = "scene_summary"
    }

    public init(
        date: String, sceneId: String, quote: String, timeRange: String = "", sceneSummary: String = ""
    ) {
        self.date = date
        self.sceneId = sceneId
        self.quote = quote
        self.timeRange = timeRange
        self.sceneSummary = sceneSummary
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decodeIfPresent(String.self, forKey: .date) ?? ""
        sceneId = try c.decodeIfPresent(String.self, forKey: .sceneId) ?? ""
        quote = try c.decodeIfPresent(String.self, forKey: .quote) ?? ""
        timeRange = try c.decodeIfPresent(String.self, forKey: .timeRange) ?? ""
        sceneSummary = try c.decodeIfPresent(String.self, forKey: .sceneSummary) ?? ""
    }
}

/// 修整操作结果：POST /api/context/loops/close 等（对应后端 handle_* 返回 {success, target_id, context} 或 {success:false,error}）。
/// context 字段是刷新后的快照，但 VM 端用 reload 三类列表保证一致，这里不强依赖它。
public struct ContextActionResult: Decodable, Equatable, Sendable {
    public let success: Bool
    public let targetId: String
    public let error: String?

    enum CodingKeys: String, CodingKey {
        case success, error
        case targetId = "target_id"
    }

    public init(success: Bool, targetId: String = "", error: String? = nil) {
        self.success = success
        self.targetId = targetId
        self.error = error
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        success = try c.decodeIfPresent(Bool.self, forKey: .success) ?? false
        targetId = try c.decodeIfPresent(String.self, forKey: .targetId) ?? ""
        error = try c.decodeIfPresent(String.self, forKey: .error)
    }
}

/// 问答结果：GET /api/context/ask（对应后端 answer_with_synthesis）。
/// 后端字段随实现变化，这里只取通用展示字段，缺则降级；error 非空表示失败。
public struct ContextAskResult: Decodable, Equatable, Sendable {
    public let answer: String
    public let summary: String
    public let evidence: [ContextEvidence]
    public let error: String?

    enum CodingKeys: String, CodingKey {
        case answer, summary, evidence, error
    }

    public init(answer: String = "", summary: String = "", evidence: [ContextEvidence] = [], error: String? = nil) {
        self.answer = answer
        self.summary = summary
        self.evidence = evidence
        self.error = error
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        answer = try c.decodeIfPresent(String.self, forKey: .answer) ?? ""
        summary = try c.decodeIfPresent(String.self, forKey: .summary) ?? ""
        evidence = try c.decodeIfPresent([ContextEvidence].self, forKey: .evidence) ?? []
        error = try c.decodeIfPresent(String.self, forKey: .error)
    }
}

// MARK: - 查询预设种类

/// 查询工作台预设 kind，对齐后端 QUERY_KINDS（project/person/open/closed/evidence）。
public enum ContextQueryKind: String, CaseIterable, Sendable {
    case project
    case person
    case open
    case closed
    case evidence
}

// MARK: - APIClient 上下文接口

extension APIClient {
    /// 上下文快照：GET /api/context。
    public func context() async throws -> ContextSnapshot {
        try await get("/api/context")
    }

    /// 未关闭待办列表：GET /api/context/loops（后端直接返回数组）。
    public func contextLoops() async throws -> [Loop] {
        try await get("/api/context/loops")
    }

    /// 活跃项目列表：GET /api/context/projects。
    public func contextProjects() async throws -> [Project] {
        try await get("/api/context/projects")
    }

    /// 近期决策列表：GET /api/context/decisions。
    public func contextDecisions() async throws -> [Decision] {
        try await get("/api/context/decisions")
    }

    /// 关闭待办：POST /api/context/loops/close。body {query, status, reason}。
    /// status 默认 "done"，对齐后端 handle_close_loop 缺省。
    public func closeLoop(query: String, status: String = "done", reason: String = "") async throws -> ContextActionResult {
        try await post("/api/context/loops/close", body: ["query": query, "status": status, "reason": reason])
    }

    /// 拒绝待办：POST /api/context/loops/reject。body {query, reason}。
    public func rejectLoop(query: String, reason: String = "") async throws -> ContextActionResult {
        try await post("/api/context/loops/reject", body: ["query": query, "reason": reason])
    }

    /// 合并项目：POST /api/context/projects/merge。body {source, target, reason}。
    /// source 合并进 target，字段名严格对齐后端 handle_merge_project。
    public func mergeProject(source: String, target: String, reason: String = "") async throws -> ContextActionResult {
        try await post("/api/context/projects/merge", body: ["source": source, "target": target, "reason": reason])
    }

    /// 拒绝项目：POST /api/context/projects/reject。body {query, reason}。
    public func rejectProject(query: String, reason: String = "") async throws -> ContextActionResult {
        try await post("/api/context/projects/reject", body: ["query": query, "reason": reason])
    }

    /// 拒绝决策：POST /api/context/decisions/reject。body {query, reason}。
    public func rejectDecision(query: String, reason: String = "") async throws -> ContextActionResult {
        try await post("/api/context/decisions/reject", body: ["query": query, "reason": reason])
    }

    /// 查询工作台：GET /api/context/query?kind=&q=&limit=&evidence=。
    /// 后端用 evidence=1 表示带证据（见 http_handlers），这里把 includeEvidence 映射成该参数。
    public func contextQuery(
        kind: ContextQueryKind,
        query: String = "",
        limit: Int = 8,
        includeEvidence: Bool = true
    ) async throws -> ContextQueryResult {
        var items = [
            URLQueryItem(name: "kind", value: kind.rawValue),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "evidence", value: includeEvidence ? "1" : "0"),
        ]
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty {
            items.append(URLQueryItem(name: "q", value: trimmed))
        }
        return try await get("/api/context/query?\(Self.encodeQuery(items))")
    }

    /// 上下文问答：GET /api/context/ask?q=&limit=。
    public func contextAsk(question: String, limit: Int = 6) async throws -> ContextAskResult {
        let items = [
            URLQueryItem(name: "q", value: question.trimmingCharacters(in: .whitespacesAndNewlines)),
            URLQueryItem(name: "limit", value: String(limit)),
        ]
        return try await get("/api/context/ask?\(Self.encodeQuery(items))")
    }

    /// 拼 query 串，对值做百分号编码（对齐 Web URLSearchParams）。
    static func encodeQuery(_ items: [URLQueryItem]) -> String {
        var comps = URLComponents()
        comps.queryItems = items
        return comps.percentEncodedQuery ?? ""
    }
}
