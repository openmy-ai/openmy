import XCTest
@testable import OpenMyKit

final class WaveformDownsamplerTests: XCTestCase {

    // 桶内取绝对值峰值
    func test_takes_absolute_peak_per_bucket() {
        // 4 个采样分 2 桶：桶0=[0.1,-0.9]→0.9，桶1=[0.3,-0.2]→0.3
        let r = WaveformDownsampler.downsample([0.1, -0.9, 0.3, -0.2], buckets: 2)
        XCTAssertEqual(r.count, 2)
        XCTAssertEqual(r[0], 0.9, accuracy: 1e-6)
        XCTAssertEqual(r[1], 0.3, accuracy: 1e-6)
    }

    // buckets 等于采样数：每桶一个采样
    func test_buckets_equal_samples() {
        let r = WaveformDownsampler.downsample([-0.5, 0.4, -0.3], buckets: 3)
        XCTAssertEqual(r, [0.5, 0.4, 0.3])
    }

    // buckets 多于采样数：空桶补 0（不越界）
    func test_more_buckets_than_samples() {
        let r = WaveformDownsampler.downsample([0.7, -0.2], buckets: 4)
        XCTAssertEqual(r.count, 4)
        // 前面的桶覆盖到采样，后面的空桶为 0
        XCTAssertTrue(r.contains(0.7))
        XCTAssertEqual(r.filter { $0 == 0 }.count, 2)
    }

    // 空输入安全返回空
    func test_empty_samples_returns_empty() {
        XCTAssertEqual(WaveformDownsampler.downsample([], buckets: 8), [])
    }

    // buckets <= 0 安全返回空
    func test_nonpositive_buckets_returns_empty() {
        XCTAssertEqual(WaveformDownsampler.downsample([0.1, 0.2], buckets: 0), [])
        XCTAssertEqual(WaveformDownsampler.downsample([0.1, 0.2], buckets: -3), [])
    }
}
