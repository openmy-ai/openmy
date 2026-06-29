import Foundation

/// 高亮片段：把后端 <mark>…</mark> 解析后的一段文本及其是否命中。
/// 搜索结果高亮与跳转段落关键词高亮共用这一结构。
public struct HighlightSegment: Equatable, Sendable {
    /// 片段文本（已还原 HTML 实体）。
    public let text: String
    /// 是否为命中片段（原文被 <mark> 包裹）。
    public let isMatch: Bool

    public init(text: String, isMatch: Bool) {
        self.text = text
        self.isMatch = isMatch
    }
}

/// 把后端返回的带 <mark> 标记的文本解析成可渲染的片段数组。
///
/// 规则：
/// - "a<mark>b</mark>c" → 3 段，中间 isMatch=true。
/// - 多个 <mark> 各自成段。
/// - 无 <mark> → 单段，isMatch=false（空串也返回单段空串，便于调用方统一处理）。
/// - 同时还原常见 HTML 实体（&amp; &lt; &gt; &quot; &#39;），因为后端片段可能含转义。
///
/// 不做完整 HTML 解析：后端只产出 <mark> 一种标记，按字符串切分足够且更稳。
public func parseHighlight(_ html: String) -> [HighlightSegment] {
    let openTag = "<mark>"
    let closeTag = "</mark>"

    var segments: [HighlightSegment] = []
    var remainder = Substring(html)

    while let openRange = remainder.range(of: openTag) {
        // <mark> 之前的普通文本
        let before = remainder[remainder.startIndex..<openRange.lowerBound]
        if !before.isEmpty {
            segments.append(HighlightSegment(text: unescapeHTML(String(before)), isMatch: false))
        }
        let afterOpen = remainder[openRange.upperBound...]
        guard let closeRange = afterOpen.range(of: closeTag) else {
            // 标记不闭合：剩余整体当普通文本处理，避免吞字
            let rest = remainder[openRange.lowerBound...]
            segments.append(HighlightSegment(text: unescapeHTML(String(rest)), isMatch: false))
            remainder = afterOpen[afterOpen.endIndex...]
            break
        }
        let matched = afterOpen[afterOpen.startIndex..<closeRange.lowerBound]
        if !matched.isEmpty {
            segments.append(HighlightSegment(text: unescapeHTML(String(matched)), isMatch: true))
        }
        remainder = afterOpen[closeRange.upperBound...]
    }

    if !remainder.isEmpty {
        segments.append(HighlightSegment(text: unescapeHTML(String(remainder)), isMatch: false))
    }

    // 全空输入时也返回单段空串，调用方无需特判空数组
    if segments.isEmpty {
        segments.append(HighlightSegment(text: "", isMatch: false))
    }
    return segments
}

/// 还原后端片段里可能出现的 HTML 实体。&amp; 最后处理，避免二次解码。
func unescapeHTML(_ s: String) -> String {
    var out = s
    out = out.replacingOccurrences(of: "&lt;", with: "<")
    out = out.replacingOccurrences(of: "&gt;", with: ">")
    out = out.replacingOccurrences(of: "&quot;", with: "\"")
    out = out.replacingOccurrences(of: "&#39;", with: "'")
    out = out.replacingOccurrences(of: "&amp;", with: "&")
    return out
}
