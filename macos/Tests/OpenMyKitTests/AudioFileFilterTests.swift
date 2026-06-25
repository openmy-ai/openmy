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

    // 行为：全部可处理时无提示
    func test_evaluate_all_eligible_no_note() {
        let result = AudioFileFilter.evaluate(["/a/x.wav", "/a/y.mp3"], maxBatch: 5)
        XCTAssertEqual(result.paths, ["/a/x.wav", "/a/y.mp3"])
        XCTAssertNil(result.note)
        XCTAssertFalse(result.isEmpty)
    }

    // 行为：部分格式不支持时提示忽略
    func test_evaluate_partial_unsupported_notes() {
        let result = AudioFileFilter.evaluate(["/a/x.wav", "/a/y.txt"], maxBatch: 5)
        XCTAssertEqual(result.paths, ["/a/x.wav"])
        XCTAssertEqual(result.note, "已忽略部分文件，只处理前 1 个")
    }

    // 行为：超过批量上限时提示忽略
    func test_evaluate_over_batch_notes() {
        let input = (1...8).map { "/a/\($0).wav" }
        let result = AudioFileFilter.evaluate(input, maxBatch: 5)
        XCTAssertEqual(result.paths.count, 5)
        XCTAssertEqual(result.note, "已忽略部分文件，只处理前 5 个")
    }

    // 行为：全部不支持时给出明确提示且无可处理文件
    func test_evaluate_none_eligible() {
        let result = AudioFileFilter.evaluate(["/a/x.txt", "/a/y.pdf"], maxBatch: 5)
        XCTAssertTrue(result.isEmpty)
        XCTAssertEqual(result.note, "拖入的文件都不是支持的音频/视频格式")
    }

    // 行为：空拖入不报错也不提示
    func test_evaluate_empty_input() {
        let result = AudioFileFilter.evaluate([], maxBatch: 5)
        XCTAssertTrue(result.isEmpty)
        XCTAssertNil(result.note)
    }
}
