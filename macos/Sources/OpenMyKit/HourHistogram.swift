import Foundation

/// 24 小时分桶直方图：把逐段（时间串 + 权重）按小时累加权重。
/// 对齐 daily.js 的时段热度——按段落文本字数加权（weight 传 text.count），不是段落数。
public enum HourHistogram {
    /// 输入 (时间串, 权重) 数组 → 长度 24 的加权直方图（下标即小时 0...23）。
    /// 解析规则：取冒号前部分作小时；非 0...23 或非法/空时间项连同其权重安全跳过；负权重按 0 计。
    public static func counts(weighted items: [(time: String, weight: Int)]) -> [Int] {
        var buckets = [Int](repeating: 0, count: 24)
        for item in items {
            guard let hour = hour(of: item.time) else { continue }
            buckets[hour] += max(0, item.weight)
        }
        return buckets
    }

    /// 从单个时间串解析小时（0...23），无法解析返回 nil。
    static func hour(of raw: String) -> Int? {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return nil }
        let head = trimmed.split(separator: ":", maxSplits: 1).first.map(String.init) ?? trimmed
        guard let value = Int(head), (0...23).contains(value) else { return nil }
        return value
    }
}
