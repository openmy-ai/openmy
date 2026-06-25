import XCTest
@testable import OpenMyKit

final class FriendlyDateTests: XCTestCase {

    // 基准 today 固定，不依赖系统时钟。2026-06-25 是星期四。
    let today = "2026-06-25"

    func test_today() {
        XCTAssertEqual(FriendlyDate.format(date: "2026-06-25", today: today), "今天")
    }

    func test_yesterday() {
        XCTAssertEqual(FriendlyDate.format(date: "2026-06-24", today: today), "昨天")
    }

    func test_dayBeforeYesterday() {
        XCTAssertEqual(FriendlyDate.format(date: "2026-06-23", today: today), "前天")
    }

    // 本周内（周一为周首）：2026-06-22 是周一，与 06-25（周四）同周
    func test_sameWeek_weekday() {
        XCTAssertEqual(FriendlyDate.format(date: "2026-06-22", today: today), "星期一")
    }

    // 上周日 2026-06-21 不属于 06-22~06-28 这一自然周 → 回退 M月D日
    func test_previousWeek_fallsBack_to_monthDay() {
        XCTAssertEqual(FriendlyDate.format(date: "2026-06-21", today: today), "6月21日")
    }

    // 未来同周（06-26 周五）显示星期五
    func test_futureSameWeek_weekday() {
        XCTAssertEqual(FriendlyDate.format(date: "2026-06-26", today: today), "星期五")
    }

    // 远日期回退 M月D日
    func test_farDate_monthDay() {
        XCTAssertEqual(FriendlyDate.format(date: "2026-05-10", today: today), "5月10日")
    }

    // 无效串回退原值
    func test_invalid_returns_input() {
        XCTAssertEqual(FriendlyDate.format(date: "not-a-date", today: today), "not-a-date")
    }
}

final class GreetingTests: XCTestCase {
    // 对齐 Web getGreetingByHour：<11 早上好；<18 下午好；否则 晚上好
    func test_morning() {
        XCTAssertEqual(Greeting.text(hour: 0), "早上好")
        XCTAssertEqual(Greeting.text(hour: 10), "早上好")
    }

    func test_afternoon() {
        XCTAssertEqual(Greeting.text(hour: 11), "下午好")
        XCTAssertEqual(Greeting.text(hour: 17), "下午好")
    }

    func test_evening() {
        XCTAssertEqual(Greeting.text(hour: 18), "晚上好")
        XCTAssertEqual(Greeting.text(hour: 23), "晚上好")
    }
}
