import XCTest
@testable import OpenMyKit

final class AudioFileFilterTests: XCTestCase {

    // 行为：只保留受支持的音频/视频扩展名
    func test_filters_unsupported_extensions() {
        let input = ["/a/x.wav", "/a/y.txt", "/a/z.MP3", "/a/note.pdf", "/a/v.m4a"]
        let result = AudioFileFilter.eligible(input, maxBatch: 10)
        XCTAssertEqual(result, ["/a/x.wav", "/a/z.MP3", "/a/v.m4a"])
    }

    // 行为：超出批量上限时截断（云端引擎 5 个上限）
    func test_caps_batch() {
        let input = (1...8).map { "/a/\($0).wav" }
        let result = AudioFileFilter.eligible(input, maxBatch: 5)
        XCTAssertEqual(result.count, 5)
    }
}
