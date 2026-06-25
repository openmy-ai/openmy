import Foundation

/// 友好日期显示：把 "2026-06-05" 这类 ISO 日期串转成人类可读标签。
///
/// 基准日 `today` 由外部传入（不依赖系统时钟），便于测试与跨时区可控。
/// 规则（在 Web formatFriendlyDate 仅 "M月D日" 基础上扩展，本前端按任务约定加入相对日）：
/// - 同一天 → 今天
/// - 早一天 → 昨天
/// - 早两天 → 前天
/// - 本周内（同一自然周、且非上面三种）→ 星期一…星期日
/// - 其它 → M月D日
public enum FriendlyDate {

    /// 解析 "YYYY-MM-DD" 为本地日历的 DateComponents（无效串返回 nil）。
    static func components(_ iso: String) -> DateComponents? {
        let parts = iso.split(separator: "-").map { Int($0) }
        guard parts.count == 3, let y = parts[0], let m = parts[1], let d = parts[2] else {
            return nil
        }
        var c = DateComponents()
        c.year = y
        c.month = m
        c.day = d
        return c
    }

    /// 把 ISO 日期串相对基准日 `today` 格式化为友好标签。
    ///
    /// - Parameters:
    ///   - date: 目标日期 "YYYY-MM-DD"。
    ///   - today: 基准"今天" "YYYY-MM-DD"，外部传入。
    ///   - calendar: 日历（默认公历，可注入便于测试）。
    /// - Returns: 友好标签。无法解析时回退原串。
    public static func format(
        date: String,
        today: String,
        calendar: Calendar = Calendar(identifier: .gregorian)
    ) -> String {
        guard
            let dc = components(date),
            let tc = components(today),
            let target = calendar.date(from: dc),
            let base = calendar.date(from: tc)
        else {
            return date
        }

        let dayDiff = calendar.dateComponents([.day], from: calendar.startOfDay(for: base), to: calendar.startOfDay(for: target)).day ?? 0

        switch dayDiff {
        case 0: return "今天"
        case -1: return "昨天"
        case -2: return "前天"
        default:
            // 本周内（同一自然周，周一为周首）显示星期几。
            if let weekday = sameWeekWeekday(target: target, base: base, calendar: calendar) {
                return weekday
            }
            let month = dc.month ?? 0
            let day = dc.day ?? 0
            return "\(month)月\(day)日"
        }
    }

    /// 若 target 与 base 落在同一自然周（周一为周首），返回 target 的"星期X"；否则 nil。
    private static func sameWeekWeekday(target: Date, base: Date, calendar: Calendar) -> String? {
        var cal = calendar
        cal.firstWeekday = 2 // 周一为一周第一天，对齐中文习惯
        let targetWeek = cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: target)
        let baseWeek = cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: base)
        guard
            targetWeek.weekOfYear == baseWeek.weekOfYear,
            targetWeek.yearForWeekOfYear == baseWeek.yearForWeekOfYear
        else {
            return nil
        }
        let names = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"]
        let wd = cal.component(.weekday, from: target) // 1=周日 … 7=周六
        guard (1...7).contains(wd) else { return nil }
        return names[wd - 1]
    }
}

/// 时段问候语：按小时返回早上好/下午好/晚上好。
///
/// `hour` 由外部传入（不依赖系统时钟）。规则对齐 Web dates.js getGreetingByHour：
/// hour < 11 → 早上好；hour < 18 → 下午好；否则 晚上好。
public enum Greeting {
    /// 按小时（0–23）返回问候语。越界小时按区间规则归类。
    public static func text(hour: Int) -> String {
        if hour < 11 { return "早上好" }
        if hour < 18 { return "下午好" }
        return "晚上好"
    }
}
