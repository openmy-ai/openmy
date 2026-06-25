import XCTest
@testable import OpenMyKit

final class HourHistogramTests: XCTestCase {

    // 行为：长度恒为 24
    func test_length_always_24() {
        XCTAssertEqual(HourHistogram.counts(weighted: []).count, 24)
        XCTAssertEqual(HourHistogram.counts(weighted: [("09:00", 5)]).count, 24)
    }

    // 行为：同小时多段按权重累加（对齐网页版按字数加权）
    func test_weights_accumulate_by_hour() {
        let h = HourHistogram.counts(weighted: [
            ("09:05", 12), ("09:50", 8), ("16:50", 30), ("00:01", 3),
        ])
        XCTAssertEqual(h[9], 20)
        XCTAssertEqual(h[16], 30)
        XCTAssertEqual(h[0], 3)
        XCTAssertEqual(h[12], 0)
    }

    // 行为：非法/空时间项连同权重跳过
    func test_skips_invalid() {
        let h = HourHistogram.counts(weighted: [
            ("", 99), ("abc", 99), ("99:00", 99), ("25:10", 99), ("12:30", 7),
        ])
        XCTAssertEqual(h[12], 7)
        XCTAssertEqual(h.reduce(0, +), 7)
    }

    // 行为：负权重按 0 计，不污染桶
    func test_negative_weight_counts_as_zero() {
        let h = HourHistogram.counts(weighted: [("10:00", -5), ("10:30", 4)])
        XCTAssertEqual(h[10], 4)
    }

    // 行为：边界小时 0 与 23
    func test_boundary_hours() {
        let h = HourHistogram.counts(weighted: [("00:00", 2), ("23:59", 6)])
        XCTAssertEqual(h[0], 2)
        XCTAssertEqual(h[23], 6)
    }

    // 行为：带空白的时间项可解析
    func test_trims_whitespace() {
        let h = HourHistogram.counts(weighted: [(" 08:15 ", 9)])
        XCTAssertEqual(h[8], 9)
    }
}
