import XCTest
@testable import OpenMyKit

final class MarkHighlightTests: XCTestCase {

    // 行为："a<mark>b</mark>c" → 3 段，中间命中
    func test_single_mark_three_segments() {
        let segs = parseHighlight("a<mark>b</mark>c")
        XCTAssertEqual(segs, [
            HighlightSegment(text: "a", isMatch: false),
            HighlightSegment(text: "b", isMatch: true),
            HighlightSegment(text: "c", isMatch: false),
        ])
    }

    // 行为：多个 <mark> 各自成命中段
    func test_multiple_marks() {
        let segs = parseHighlight("<mark>x</mark>y<mark>z</mark>")
        XCTAssertEqual(segs, [
            HighlightSegment(text: "x", isMatch: true),
            HighlightSegment(text: "y", isMatch: false),
            HighlightSegment(text: "z", isMatch: true),
        ])
    }

    // 行为：无 <mark> → 单段非命中
    func test_no_mark_single_segment() {
        let segs = parseHighlight("纯文本无标记")
        XCTAssertEqual(segs, [HighlightSegment(text: "纯文本无标记", isMatch: false)])
    }

    // 行为：空串 → 单段空串
    func test_empty_string() {
        XCTAssertEqual(parseHighlight(""), [HighlightSegment(text: "", isMatch: false)])
    }

    // 行为：HTML 实体被还原
    func test_unescapes_entities() {
        let segs = parseHighlight("a &amp; <mark>b&lt;c</mark>")
        XCTAssertEqual(segs, [
            HighlightSegment(text: "a & ", isMatch: false),
            HighlightSegment(text: "b<c", isMatch: true),
        ])
    }

    // 行为：标记不闭合时不吞字
    func test_unclosed_mark_does_not_drop_text() {
        let segs = parseHighlight("前<mark>未闭合")
        XCTAssertEqual(segs.map(\.text).joined(), "前<mark>未闭合")
        XCTAssertFalse(segs.contains { $0.isMatch })
    }

    // 行为：中文命中片段正确切分
    func test_chinese_match() {
        let segs = parseHighlight("今天去<mark>新疆</mark>自驾")
        XCTAssertEqual(segs[1], HighlightSegment(text: "新疆", isMatch: true))
        XCTAssertEqual(segs.count, 3)
    }
}
