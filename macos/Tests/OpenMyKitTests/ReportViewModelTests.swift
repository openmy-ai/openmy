import XCTest
@testable import OpenMyKit

@MainActor
final class ReportViewModelTests: XCTestCase {

    func day(_ date: String, segments: Int, words: Int = 0,
             decisions: [String] = [], todos: [String] = []) -> DayEntry {
        DayEntry(date: date, segments: segments, wordCount: words, summary: "",
                 decisions: decisions, todos: todos, events: [], timeline: [])
    }

    // 行为：load 同时算周报与月报两套
    func test_load_computes_weekly_and_monthly() {
        let dates = [
            day("2026-06-25", segments: 2, words: 50),
            day("2026-06-10", segments: 3, words: 80), // 周报外（>7天），月报内
        ]
        let vm = ReportViewModel()
        vm.load(dates: dates, activeProjects: [], today: "2026-06-25")

        XCTAssertEqual(vm.weekly?.totalSegments, 2)
        XCTAssertEqual(vm.monthly?.totalSegments, 5)
        XCTAssertEqual(vm.weekly?.activeDays, 1)
        XCTAssertEqual(vm.monthly?.activeDays, 2)
    }

    // 行为：load 前 weekly/monthly 为 nil
    func test_initial_nil() {
        let vm = ReportViewModel()
        XCTAssertNil(vm.weekly)
        XCTAssertNil(vm.monthly)
        XCTAssertTrue(vm.activeProjects.isEmpty)
    }

    // 行为：activeProjects 透传 title，空 title 丢弃
    func test_active_projects_titles() {
        let vm = ReportViewModel()
        let projects = [
            Project(projectId: "p1", title: "项目A"),
            Project(projectId: "p2", title: ""),
            Project(projectId: "p3", title: "项目C"),
        ]
        vm.load(dates: [], activeProjects: projects, today: "2026-06-25")
        XCTAssertEqual(vm.activeProjects, ["项目A", "项目C"])
    }

    // 行为：compute 任意窗口不改变已存 weekly/monthly
    func test_compute_does_not_mutate_stored() {
        let dates = [day("2026-06-25", segments: 4)]
        let vm = ReportViewModel()
        vm.load(dates: dates, activeProjects: [], today: "2026-06-25")
        let custom = vm.compute(dates: dates, window: 1, today: "2026-06-25")
        XCTAssertEqual(custom.totalSegments, 4)
        // 已存结果不变
        XCTAssertEqual(vm.weekly?.totalSegments, 4)
    }

    // 行为：决策聚合透传到 weekly
    func test_weekly_aggregates_decisions() {
        let dates = [day("2026-06-25", segments: 1, decisions: ["决策A"], todos: ["待办X"])]
        let vm = ReportViewModel()
        vm.load(dates: dates, activeProjects: [], today: "2026-06-25")
        XCTAssertEqual(vm.weekly?.decisions, ["决策A"])
        XCTAssertEqual(vm.weekly?.todos, ["待办X"])
    }
}
