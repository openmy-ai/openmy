import Foundation
import Observation

/// 全局搜索状态机：query 输入 → 调 search → results，支持按日期分组与键盘上下导航。
/// 对齐 Web spotlight：结果按日期分组、selectedIndex 在扁平结果上移动、回车跳转。
@MainActor
@Observable
public final class SearchViewModel {
    /// 当前查询词。
    public var query: String = ""
    /// 扁平命中列表（保持后端返回顺序）。
    public private(set) var results: [SearchResult] = []
    /// 当前选中项在扁平列表中的序号；无结果时为 -1。
    public private(set) var selectedIndex: Int = -1
    public private(set) var errorMessage: String?

    private let client: APIClient
    /// 搜索序号：只有最新一次搜索的响应允许写入，防止快速输入时过期响应覆盖。
    private var searchToken = 0

    public init(client: APIClient) {
        self.client = client
    }

    /// 按 query 搜索并填充结果。空 query 直接清空。
    public func search() async {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        errorMessage = nil
        guard !trimmed.isEmpty else {
            results = []
            selectedIndex = -1
            return
        }
        searchToken += 1
        let token = searchToken
        do {
            let hits = try await client.search(query: trimmed)
            guard token == searchToken else { return }  // 被更新的搜索取代，丢弃
            results = hits
            selectedIndex = hits.isEmpty ? -1 : 0
        } catch {
            guard token == searchToken else { return }
            results = []
            selectedIndex = -1
            errorMessage = String(describing: error)
        }
    }

    /// 按日期分组，保持日期首次出现的顺序（对齐 Web reduce 行为）。
    /// 返回 [(date, 该日期下的命中)]。
    public var groupedByDate: [(date: String, results: [SearchResult])] {
        var order: [String] = []
        var buckets: [String: [SearchResult]] = [:]
        for r in results {
            if buckets[r.date] == nil { order.append(r.date) }
            buckets[r.date, default: []].append(r)
        }
        return order.map { (date: $0, results: buckets[$0] ?? []) }
    }

    /// 当前选中的命中项。
    public var selectedResult: SearchResult? {
        guard results.indices.contains(selectedIndex) else { return nil }
        return results[selectedIndex]
    }

    /// 上下移动选中项。delta=+1 下移，-1 上移。取模回环，对齐 Web spotlight。
    /// 未选中时：下移到首项、上移到末项。
    public func moveSelection(_ delta: Int) {
        guard !results.isEmpty else { selectedIndex = -1; return }
        let count = results.count
        if selectedIndex < 0 {
            selectedIndex = delta >= 0 ? 0 : count - 1
        } else {
            selectedIndex = ((selectedIndex + delta) % count + count) % count
        }
    }

    /// 清空查询与结果。
    public func clear() {
        query = ""
        results = []
        selectedIndex = -1
        errorMessage = nil
    }
}
