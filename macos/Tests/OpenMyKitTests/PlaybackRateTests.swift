import XCTest
@testable import OpenMyKit

final class PlaybackRateTests: XCTestCase {

    // 合法值原样保留
    func test_clamp_keeps_valid() {
        XCTAssertEqual(PlaybackRate.clamp(1.0), 1.0)
        XCTAssertEqual(PlaybackRate.clamp(2.0), 2.0)
    }

    // 非法值钳到最接近的合法选项（选项 0.5/1/1.5/2，对齐 Web）
    func test_clamp_to_nearest() {
        XCTAssertEqual(PlaybackRate.clamp(0.9), 1.0)   // 0.9 离 1.0 更近
        XCTAssertEqual(PlaybackRate.clamp(1.4), 1.5)
        XCTAssertEqual(PlaybackRate.clamp(3.0), 2.0)   // 超上限钳到 2.0
        XCTAssertEqual(PlaybackRate.clamp(0.1), 0.5)   // 低于下限钳到 0.5
    }

    // 循环切换：到末尾回到开头
    func test_next_cycles() {
        XCTAssertEqual(PlaybackRate.next(after: 0.5), 1.0)
        XCTAssertEqual(PlaybackRate.next(after: 1.0), 1.5)
        XCTAssertEqual(PlaybackRate.next(after: 1.5), 2.0)
        XCTAssertEqual(PlaybackRate.next(after: 2.0), 0.5)
    }

    // next 先钳制再前进（非法当前值也能切换）
    func test_next_clamps_first() {
        XCTAssertEqual(PlaybackRate.next(after: 1.4), 2.0) // 1.4→1.5→next=2.0
    }
}
