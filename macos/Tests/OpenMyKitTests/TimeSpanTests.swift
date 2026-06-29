import XCTest
@testable import OpenMyKit

final class TimeSpanTests: XCTestCase {

    // 行为：取首末时间
    func test_first_and_last() {
        let span = TimeSpan.span(times: ["16:50", "09:00", "23:10", "12:30"])
        XCTAssertEqual(span?.first, "09:00")
        XCTAssertEqual(span?.last, "23:10")
    }

    // 行为：乱序输入也取最早最晚（不靠字典序，靠分钟数）
    func test_orders_by_minutes_not_lexical() {
        // 字典序 "9:00" > "12:30"，但分钟序 9:00 在前
        let span = TimeSpan.span(times: ["12:30", "9:00"])
        XCTAssertEqual(span?.first, "9:00")
        XCTAssertEqual(span?.last, "12:30")
    }

    // 行为：单个有效项时 first == last
    func test_single() {
        let span = TimeSpan.span(times: ["08:15"])
        XCTAssertEqual(span?.first, "08:15")
        XCTAssertEqual(span?.last, "08:15")
    }

    // 行为：空数组返回 nil
    func test_empty_nil() {
        XCTAssertNil(TimeSpan.span(times: []))
    }

    // 行为：全非法返回 nil
    func test_all_invalid_nil() {
        XCTAssertNil(TimeSpan.span(times: ["", "abc", "99:99"]))
    }

    // 行为：混入非法项时只取有效项
    func test_mixed_valid_invalid() {
        let span = TimeSpan.span(times: ["bad", "10:00", "07:00", ""])
        XCTAssertEqual(span?.first, "07:00")
        XCTAssertEqual(span?.last, "10:00")
    }
}
