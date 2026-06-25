import XCTest
@testable import OpenMyKit

final class ReportAggregatorTests: XCTestCase {

    func day(_ date: String, segments: Int = 0, words: Int = 0, summary: String = "",
             decisions: [String] = [], todos: [String] = [],
             timeline: [TimelineEntry] = []) -> DayEntry {
        DayEntry(date: date, segments: segments, wordCount: words, summary: summary,
                 decisions: decisions, todos: todos, events: [], timeline: timeline)
    }

    // 行为：周报窗口取最近7天，含 today 当天，向前推6天
    func test_weekly_window_includes_last_7_days() {
        let dates = [
            day("2026-06-19", segments: 1), // today-6，含
            day("2026-06-18", segments: 1), // today-7，排除
            day("2026-06-25", segments: 1), // today，含
        ]
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-06-25")
        XCTAssertEqual(r.perDay.count, 2)
        XCTAssertEqual(r.perDay.map { $0.date }, ["2026-06-19", "2026-06-25"])
    }

    // 行为：未来日期（晚于 today）被排除
    func test_excludes_future_dates() {
        let dates = [day("2026-06-25", segments: 2), day("2026-06-26", segments: 5)]
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-06-25")
        XCTAssertEqual(r.totalSegments, 2)
    }

    // 行为：活跃天 = segments>0，求和正确
    func test_active_days_and_sums() {
        let dates = [
            day("2026-06-23", segments: 3, words: 100),
            day("2026-06-24", segments: 0, words: 0),
            day("2026-06-25", segments: 5, words: 200),
        ]
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-06-25")
        XCTAssertEqual(r.activeDays, 2)
        XCTAssertEqual(r.totalSegments, 8)
        XCTAssertEqual(r.totalWords, 300)
    }

    // 行为：perDay 按日期升序
    func test_perDay_sorted_ascending() {
        let dates = [day("2026-06-25", segments: 1), day("2026-06-23", segments: 2), day("2026-06-24", segments: 3)]
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-06-25")
        XCTAssertEqual(r.perDay.map { $0.date }, ["2026-06-23", "2026-06-24", "2026-06-25"])
    }

    // 行为：topSummary 取最长摘要
    func test_top_summary_longest() {
        let dates = [
            day("2026-06-24", segments: 1, summary: "短"),
            day("2026-06-25", segments: 1, summary: "这是更长的一段摘要"),
        ]
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-06-25")
        XCTAssertEqual(r.topSummary, "这是更长的一段摘要")
    }

    // 行为：summary 为空时回退首条 timeline preview
    func test_top_summary_falls_back_to_timeline_preview() {
        let dates = [
            day("2026-06-25", segments: 1, summary: "",
                timeline: [TimelineEntry(time: "09:00", preview: "时间线开头内容兜底")]),
        ]
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-06-25")
        XCTAssertEqual(r.topSummary, "时间线开头内容兜底")
    }

    // 行为：决策/待办去重保序聚合
    func test_decisions_todos_dedupe_keep_order() {
        let dates = [
            day("2026-06-24", segments: 1, decisions: ["决策A", "决策B"], todos: ["待办X"]),
            day("2026-06-25", segments: 1, decisions: ["决策A", "决策C"], todos: ["待办X", "待办Y"]),
        ]
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-06-25")
        XCTAssertEqual(r.decisions, ["决策A", "决策B", "决策C"])
        XCTAssertEqual(r.todos, ["待办X", "待办Y"])
    }

    // 行为：月报窗口 30 天
    func test_monthly_window_30_days() {
        let dates = [
            day("2026-05-27", segments: 1), // today-29，含
            day("2026-05-26", segments: 1), // today-30，排除
            day("2026-06-25", segments: 1),
        ]
        let r = ReportAggregator.aggregate(dates: dates, window: 30, today: "2026-06-25")
        XCTAssertEqual(r.perDay.count, 2)
        XCTAssertEqual(r.perDay.first?.date, "2026-05-27")
    }

    // 行为：跨月边界平移正确（窗口下界落到上个月）
    func test_window_crosses_month_boundary() {
        let dates = [day("2026-06-29", segments: 1), day("2026-06-28", segments: 1)]
        // today=2026-07-01，7天窗口下界=2026-06-25
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-07-01")
        XCTAssertEqual(r.perDay.count, 2)
    }

    // 行为：window<=0 返回空结果
    func test_nonpositive_window_empty() {
        let r = ReportAggregator.aggregate(dates: [day("2026-06-25", segments: 9)], window: 0, today: "2026-06-25")
        XCTAssertEqual(r.activeDays, 0)
        XCTAssertEqual(r.totalSegments, 0)
        XCTAssertTrue(r.perDay.isEmpty)
    }

    // 行为：非法日期格式的条目被忽略
    func test_invalid_date_ignored() {
        let dates = [day("not-a-date", segments: 5), day("2026-06-25", segments: 2)]
        let r = ReportAggregator.aggregate(dates: dates, window: 7, today: "2026-06-25")
        XCTAssertEqual(r.totalSegments, 2)
    }

    // 行为：空输入安全
    func test_empty_input() {
        let r = ReportAggregator.aggregate(dates: [], window: 7, today: "2026-06-25")
        XCTAssertEqual(r.activeDays, 0)
        XCTAssertTrue(r.perDay.isEmpty)
        XCTAssertTrue(r.decisions.isEmpty)
    }
}
