import Foundation
import Observation

/// 上下文记忆库状态机：持有三类记忆条目（待办/项目/决策）+ 查询工作台状态。
/// 像 CorrectionsViewModel 一样供多视图共享（环境注入）。
///
/// 修整操作成功后自动 reload 三类列表，保证记忆库即时刷新（对齐 Web submitContextAction → loadContext）。
@MainActor
@Observable
public final class ContextViewModel {
    /// 未关闭待办。
    public private(set) var loops: [Loop] = []
    /// 活跃项目。
    public private(set) var projects: [Project] = []
    /// 近期决策。
    public private(set) var decisions: [Decision] = []
    /// 错误信息（加载/修整异常，或后端 success=false 的原因）。
    public private(set) var errorMessage: String?

    // MARK: - 查询工作台状态

    /// 当前查询种类，默认 project。
    public var queryKind: ContextQueryKind = .project
    /// 当前查询词。
    public var queryText: String = ""
    /// 最近一次查询结果。
    public private(set) var queryResult: ContextQueryResult?
    /// 查询进行中标志，供视图显示加载态。
    public private(set) var isQuerying: Bool = false

    private let client: APIClient

    public init(client: APIClient) {
        self.client = client
    }

    /// 加载三类记忆条目。任一失败则 errorMessage 置位，已有列表保持原值。
    public func load() async {
        errorMessage = nil
        do {
            async let loopsTask = client.contextLoops()
            async let projectsTask = client.contextProjects()
            async let decisionsTask = client.contextDecisions()
            loops = try await loopsTask
            projects = try await projectsTask
            decisions = try await decisionsTask
        } catch {
            errorMessage = String(describing: error)
        }
    }

    // MARK: - 修整操作（成功后 reload）

    /// 关闭待办。成功后 reload，返回是否成功。
    @discardableResult
    public func closeLoop(query: String, status: String = "done", reason: String = "") async -> Bool {
        await runAction { try await self.client.closeLoop(query: query, status: status, reason: reason) }
    }

    /// 拒绝待办。
    @discardableResult
    public func rejectLoop(query: String, reason: String = "") async -> Bool {
        await runAction { try await self.client.rejectLoop(query: query, reason: reason) }
    }

    /// 合并项目（source 合入 target）。
    @discardableResult
    public func mergeProject(source: String, target: String, reason: String = "") async -> Bool {
        await runAction { try await self.client.mergeProject(source: source, target: target, reason: reason) }
    }

    /// 拒绝项目。
    @discardableResult
    public func rejectProject(query: String, reason: String = "") async -> Bool {
        await runAction { try await self.client.rejectProject(query: query, reason: reason) }
    }

    /// 拒绝决策。
    @discardableResult
    public func rejectDecision(query: String, reason: String = "") async -> Bool {
        await runAction { try await self.client.rejectDecision(query: query, reason: reason) }
    }

    /// 执行一次修整：调 API，success 则 reload，否则把 error 写入 errorMessage。
    private func runAction(_ call: () async throws -> ContextActionResult) async -> Bool {
        errorMessage = nil
        do {
            let result = try await call()
            guard result.success else {
                errorMessage = result.error ?? "操作失败"
                return false
            }
            await load()
            return true
        } catch {
            errorMessage = String(describing: error)
            return false
        }
    }

    // MARK: - 查询工作台

    /// 跑一次查询。可覆盖 kind/query（用于预设一键查），缺省用当前状态。
    /// 成功填充 queryResult；失败置 errorMessage 并清空结果。
    public func runQuery(kind: ContextQueryKind? = nil, query: String? = nil) async {
        if let kind { queryKind = kind }
        if let query { queryText = query }
        errorMessage = nil
        isQuerying = true
        defer { isQuerying = false }
        do {
            queryResult = try await client.contextQuery(
                kind: queryKind,
                query: queryText,
                limit: 8,
                includeEvidence: true
            )
        } catch {
            errorMessage = String(describing: error)
            queryResult = nil
        }
    }

    /// 把查询证据回链解析成 SearchFocus，供 MainView.handleSearchSelect 跳到对应日期段落。
    /// time_range 取起点（"00:05-00:12" → "00:05"），对齐 Web jumpToEvidence。
    public func focus(for evidence: ContextEvidence) -> SearchFocus {
        let time = evidence.timeRange.split(separator: "-", maxSplits: 1).first.map(String.init) ?? ""
        return SearchFocus(date: evidence.date, time: time, query: queryText)
    }
}
