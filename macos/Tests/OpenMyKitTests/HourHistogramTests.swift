import XCTest
@testable import OpenMyKit

final class HourHistogramTests: XCTestCase {

    // 行为：长度恒为 24
    func test_length_always_24() {
        XCTAssertEqual(HourHistogram.counts(times: []).count, 24)
        XCTAssertEqual(HourHistogram.counts(times: ["09:00"]).count, 24)
    }

    // 行为：按小时计数
    func test_counts_by_hour() {
        let h = HourHistogram.counts(times: ["09:05", "09:50", "16:50", "00:01"])
        XCTAssertEqual(h[9], 2)
        XCTAssertEqual(h[16], 1)
        XCTAssertEqual(h[0], 1)
        XCTAssertEqual(h[12], 0)
    }

    // 行为：非法/空项跳过
    func test_skips_invalid() {
        let h = HourHistogram.counts(times: ["", "abc", "99:00", "25:10", "12:30"])
        XCTAssertEqual(h[12], 1)
        XCTAssertEqual(h.reduce(0, +), 1)
    }

    // 行为：边界小时 0 与 23
    func test_boundary_hours() {
        let h = HourHistogram.counts(times: ["00:00", "23:59"])
        XCTAssertEqual(h[0], 1)
        XCTAssertEqual(h[23], 1)
    }

    // 行为：带空白的项可解析
    func test_trims_whitespace() {
        let h = HourHistogram.counts(times: [" 08:15 "])
        XCTAssertEqual(h[8], 1)
    }
}
