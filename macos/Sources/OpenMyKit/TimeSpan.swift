import Foundation

/// 首末时间跨度：从逐段时间串数组取最早与最晚（对齐 daily.js timeSpan = 排序后首尾）。
public enum TimeSpan {
    /// 输入时间串数组 → (first, last)。
    /// 只统计可解析为 "HH:mm" 的项（按分钟数排序取最小/最大，返回原始串）；无有效项返回 nil。
    /// 单个有效项时 first == last。
    public static func span(times: [String]) -> (first: String, last: String)? {
        let valid = times.compactMap { raw -> (minutes: Int, text: String)? in
            guard let m = minutes(of: raw) else { return nil }
            return (m, raw.trimmingCharacters(in: .whitespaces))
        }
        guard !valid.isEmpty else { return nil }
        let first = valid.min { $0.minutes < $1.minutes }!.text
        let last = valid.max { $0.minutes < $1.minutes }!.text
        return (first, last)
    }

    /// 把 "HH:mm" 解析成自 0 点起的分钟数；非法返回 nil。
    static func minutes(of raw: String) -> Int? {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
        let parts = trimmed.split(separator: ":", maxSplits: 1)
        guard parts.count == 2,
              let h = Int(parts[0]), let m = Int(parts[1]),
              (0...23).contains(h), (0...59).contains(m) else { return nil }
        return h * 60 + m
    }
}
