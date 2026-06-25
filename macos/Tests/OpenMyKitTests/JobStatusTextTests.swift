import XCTest
@testable import OpenMyKit

final class JobStatusTextTests: XCTestCase {

    // 行为：已知任务状态映射为中文
    func test_job_known_statuses() {
        XCTAssertEqual(JobStatusText.job("queued"), "排队中")
        XCTAssertEqual(JobStatusText.job("running"), "处理中")
        XCTAssertEqual(JobStatusText.job("paused"), "已暂停")
        XCTAssertEqual(JobStatusText.job("succeeded"), "已完成")
        XCTAssertEqual(JobStatusText.job("partial"), "部分完成")
        XCTAssertEqual(JobStatusText.job("failed"), "失败")
        XCTAssertEqual(JobStatusText.job("cancelled"), "已取消")
    }

    // 行为：interrupted 也有中文文案，不再显示英文原值
    func test_job_interrupted_has_chinese() {
        XCTAssertEqual(JobStatusText.job("interrupted"), "已中断")
    }

    // 行为：未知状态回退为原值，不丢信息
    func test_job_unknown_falls_back() {
        XCTAssertEqual(JobStatusText.job("weird_state"), "weird_state")
    }

    // 行为：步骤状态映射
    func test_step_statuses() {
        XCTAssertEqual(JobStatusText.step("pending"), "等待中")
        XCTAssertEqual(JobStatusText.step("running"), "进行中")
        XCTAssertEqual(JobStatusText.step("done"), "已完成")
        XCTAssertEqual(JobStatusText.step("failed"), "失败")
        XCTAssertEqual(JobStatusText.step("skipped"), "已跳过")
        XCTAssertEqual(JobStatusText.step("xyz"), "xyz")
    }
}
