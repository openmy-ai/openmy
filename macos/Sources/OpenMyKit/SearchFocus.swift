import Foundation

/// 跳转焦点：搜索命中后传给 BriefingDetailView，做段落定位 + 关键词高亮。
/// 对齐 Web 的 jumpToSearchResult(date, time, query)。
public struct SearchFocus: Equatable, Sendable {
    /// 目标日期。
    public let date: String
    /// 目标段落时间标记，用于滚动定位；为空则只切到该日期。
    public let time: String
    /// 命中关键词，用于在段落内做高亮。
    public let query: String

    public init(date: String, time: String, query: String) {
        self.date = date
        self.time = time
        self.query = query
    }
}
