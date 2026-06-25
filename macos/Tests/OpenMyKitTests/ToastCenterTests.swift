import XCTest
@testable import OpenMyKit

@MainActor
final class ToastCenterTests: XCTestCase {

    // 行为：show 后列表非空，且包含该消息文本
    func test_show_appends_message() {
        // 不自动消失，避免测试依赖时钟
        let center = ToastCenter(autoDismissSeconds: 0)
        center.show("已开始处理")
        XCTAssertEqual(center.toasts.count, 1)
        XCTAssertEqual(center.toasts.first?.text, "已开始处理")
    }

    // 行为：dismiss 按 id 精确移除
    func test_dismiss_removes_by_id() {
        let center = ToastCenter(autoDismissSeconds: 0)
        let first = center.show("A")
        center.show("B")
        center.dismiss(first)
        XCTAssertEqual(center.toasts.map(\.text), ["B"])
    }

    // 行为：clear 清空全部
    func test_clear_empties() {
        let center = ToastCenter(autoDismissSeconds: 0)
        center.show("A")
        center.show("B")
        center.clear()
        XCTAssertTrue(center.toasts.isEmpty)
    }
}
