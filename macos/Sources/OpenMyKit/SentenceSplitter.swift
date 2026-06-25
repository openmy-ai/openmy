import Foundation

/// 字幕复核分句：把场景文本切成句子列表，供跟读高亮与逐句纠错。
///
/// 对齐 app/static/modules/subtitle-overlay.js：按中文标点（。！？；）和换行切分，
/// 标点保留在所属句末，去掉空白句。
public enum SentenceSplitter {

    /// 句末标点集合：中文句号/叹号/问号/分号。
    private static let terminators: Set<Character> = ["。", "！", "？", "；"]

    /// 把文本切成句子列表。空白句或仅含标点/空白的句被丢弃；纯空白输入返回 []。
    public static func split(_ text: String) -> [String] {
        var sentences: [String] = []
        var current = ""

        func flush() {
            let trimmed = current.trimmingCharacters(in: .whitespacesAndNewlines)
            // 丢弃空句，以及去掉空白后只剩句末标点的残句（如孤立的「。」）。
            let hasContent = trimmed.contains { !$0.isWhitespace && !terminators.contains($0) }
            if hasContent {
                sentences.append(trimmed)
            }
            current = ""
        }

        // 先把回车归一为换行，避免 Swift 把 "\r\n" 当成单个 grapheme cluster 漏判。
        let normalized = text.replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")

        for ch in normalized {
            if ch == "\n" {
                // 换行作为分句边界，但本身不计入句子。
                flush()
            } else if terminators.contains(ch) {
                current.append(ch)
                flush()
            } else {
                current.append(ch)
            }
        }
        flush()
        return sentences
    }
}
