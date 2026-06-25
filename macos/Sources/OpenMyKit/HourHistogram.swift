import Foundation

/// 24 小时分桶直方图：把逐段时间字符串（如 "16:50"）按小时计数。
/// 对齐 daily.js initCharts 的时段热度（按段落 time 的小时分桶）。
public enum HourHistogram {
    /// 输入时间串数组 → 长度 24 的计数数组（下标即小时 0...23）。
    /// 解析规则：取冒号前部分作小时；非 0...23 或非法/空项安全跳过。
    public static func counts(times: [String]) -> [Int] {
        var buckets = [Int](repeating: 0, count: 24)
        for raw in times {
            guard let hour = hour(of: raw) else { continue }
            buckets[hour] += 1
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
