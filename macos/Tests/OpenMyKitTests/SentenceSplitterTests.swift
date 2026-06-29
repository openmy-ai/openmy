import XCTest
@testable import OpenMyKit

final class SentenceSplitterTests: XCTestCase {

    // 按中文标点切句，标点留在句末
    func test_splits_on_chinese_punctuation() {
        let r = SentenceSplitter.split("今天开会。讨论了方案！还有疑问？需要跟进；")
        XCTAssertEqual(r, ["今天开会。", "讨论了方案！", "还有疑问？", "需要跟进；"])
    }

    // 按换行切句，换行本身不计入
    func test_splits_on_newline() {
        let r = SentenceSplitter.split("第一行\n第二行\r\n第三行")
        XCTAssertEqual(r, ["第一行", "第二行", "第三行"])
    }

    // 去掉空白句与多余空白
    func test_drops_empty_and_trims() {
        let r = SentenceSplitter.split("  你好。  。\n\n  世界  ")
        XCTAssertEqual(r, ["你好。", "世界"])
    }

    // 末尾无标点的残句也保留
    func test_keeps_trailing_fragment() {
        let r = SentenceSplitter.split("完整句。残句没有标点")
        XCTAssertEqual(r, ["完整句。", "残句没有标点"])
    }

    // 纯空白返回空
    func test_blank_returns_empty() {
        XCTAssertEqual(SentenceSplitter.split("   \n  "), [])
        XCTAssertEqual(SentenceSplitter.split(""), [])
    }
}
