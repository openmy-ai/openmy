import Foundation

/// 周报/月报聚合结果。周报=最近7天、月报=最近30天，对最近窗口的 dates 求和。
/// 对齐 reports.js renderReportPage：活跃天/段数/字数 + 每日柱状 + 决策/待办聚合 + 最长摘要。
public struct ReportSummary: Equatable, Sendable {
    /// 活跃天数（窗口内 segments>0 的天数）。
    public let activeDays: Int
    /// 窗口内总录音段数。
    public let totalSegments: Int
    /// 窗口内总字数。
    public let totalWords: Int
    /// 逐日 (date, segments)，按日期升序，供柱状图。
    public let perDay: [DaySegments]
    /// 最长摘要（窗口内 summary 取最长；为空时回退首条 timeline preview）。
    public let topSummary: String
    /// 决策文本聚合（去重保序）。
    public let decisions: [String]
    /// 待办文本聚合（去重保序）。
    public let todos: [String]

    public struct DaySegments: Equatable, Sendable {
        public let date: String
        public let segments: Int
        public init(date: String, segments: Int) {
            self.date = date
            self.segments = segments
        }
    }

    public init(
        activeDays: Int, totalSegments: Int, totalWords: Int,
        perDay: [DaySegments], topSummary: String,
        decisions: [String], todos: [String]
    ) {
        self.activeDays = activeDays
        self.totalSegments = totalSegments
        self.totalWords = totalWords
        self.perDay = perDay
        self.topSummary = topSummary
        self.decisions = decisions
        self.todos = todos
    }
}

/// 纯函数聚合器：把 [DayEntry] 在指定窗口内汇总成 ReportSummary。
/// 「今天」基准日期由外部以字符串传入（如 "2026-06-25"），避免依赖系统时钟便于测试。
public enum ReportAggregator {
    /// - Parameters:
    ///   - dates: 全部日期条目，顺序不限。
    ///   - window: 窗口天数（周报 7、月报 30）。<=0 时按 0 处理（空结果）。
    ///   - today: 基准「今天」日期字符串（"yyyy-MM-dd"）。
    /// 窗口含 today 当天，向前推 window-1 天，即闭区间 [today-(window-1), today]。
    /// 超出该区间或日期格式非法的条目被忽略。
    public static func aggregate(dates: [DayEntry], window: Int, today: String) -> ReportSummary {
        guard window > 0 else {
            return ReportSummary(
                activeDays: 0, totalSegments: 0, totalWords: 0,
                perDay: [], topSummary: "", decisions: [], todos: []
            )
        }
        // 用字典序比较日期串即可（"yyyy-MM-dd" 字典序等价时间序）。下界 = today 向前 window-1 天。
        let lowerBound = shiftDate(today, byDays: -(window - 1))
        let inWindow = dates.filter { entry in
            guard isValidDate(entry.date) else { return false }
            if let lower = lowerBound, entry.date < lower { return false }
            return entry.date <= today
        }

        let perDay = inWindow
            .sorted { $0.date < $1.date }
            .map { ReportSummary.DaySegments(date: $0.date, segments: $0.segments) }

        let activeDays = inWindow.filter { $0.segments > 0 }.count
        let totalSegments = inWindow.reduce(0) { $0 + $1.segments }
        let totalWords = inWindow.reduce(0) { $0 + $1.wordCount }

        // 最长摘要：summary 优先，空则回退首条 timeline preview（对齐 reports.js allSummaries）。
        let summaries = inWindow.compactMap { entry -> String? in
            if !entry.summary.isEmpty { return entry.summary }
            return entry.timeline.first.map { $0.preview }.flatMap { $0.isEmpty ? nil : $0 }
        }
        let topSummary = summaries.max(by: { $0.count < $1.count }) ?? ""

        let decisions = dedupeKeepingOrder(inWindow.flatMap { $0.decisions })
        let todos = dedupeKeepingOrder(inWindow.flatMap { $0.todos })

        return ReportSummary(
            activeDays: activeDays, totalSegments: totalSegments, totalWords: totalWords,
            perDay: perDay, topSummary: topSummary, decisions: decisions, todos: todos
        )
    }

    /// 去重保序：剔除空串与重复项，保留首次出现顺序。
    static func dedupeKeepingOrder(_ items: [String]) -> [String] {
        var seen = Set<String>()
        var result: [String] = []
        for item in items where !item.isEmpty {
            if seen.insert(item).inserted { result.append(item) }
        }
        return result
    }

    /// 校验 "yyyy-MM-dd" 格式（10 位、两个连字符在 5/8 位、其余为数字）。
    static func isValidDate(_ s: String) -> Bool {
        let chars = Array(s)
        guard chars.count == 10 else { return false }
        for (i, ch) in chars.enumerated() {
            if i == 4 || i == 7 {
                if ch != "-" { return false }
            } else if !ch.isNumber {
                return false
            }
        }
        return true
    }

    /// 把 "yyyy-MM-dd" 平移若干天，返回新日期串；输入非法返回 nil。
    /// 用 UTC 日历做日期算术，避免时区导致的跨日偏差。
    static func shiftDate(_ s: String, byDays days: Int) -> String? {
        guard isValidDate(s) else { return nil }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "UTC")!
        let parts = s.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        var comps = DateComponents()
        comps.year = parts[0]; comps.month = parts[1]; comps.day = parts[2]
        guard let base = cal.date(from: comps),
              let shifted = cal.date(byAdding: .day, value: days, to: base) else { return nil }
        let out = cal.dateComponents([.year, .month, .day], from: shifted)
        guard let y = out.year, let m = out.month, let d = out.day else { return nil }
        return String(format: "%04d-%02d-%02d", y, m, d)
    }
}
