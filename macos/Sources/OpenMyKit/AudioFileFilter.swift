import Foundation

/// 拖入文件后的校验结果：可处理的路径 + 给用户的轻量提示文案。
///
/// 把「过滤 + 提示文案」从视图里抽出来集中成纯逻辑，视图只渲染 `note`，
/// 不再自己拼字符串判断忽略了多少文件。
public struct DropResult: Equatable, Sendable {
    /// 经过过滤与批量上限截断后，真正交给任务接口的路径。
    public let paths: [String]
    /// 给用户的提示；无需提示时为 `nil`。
    public let note: String?

    public init(paths: [String], note: String?) {
        self.paths = paths
        self.note = note
    }

    /// 是否有可处理的文件。
    public var isEmpty: Bool { paths.isEmpty }
}

/// 拖入文件的入口校验：过滤受支持的音频/视频格式，并限制批量数量。
/// 后端 createJob 直接接受本机路径，这里只做客户端侧的防呆与云端批量上限保护。
public enum AudioFileFilter {
    /// 受支持的扩展名：本地后端可处理的音频/视频格式（比浏览器上传白名单更宽，含 opus/wma/m4v）。
    public static let supportedExtensions: Set<String> = [
        "wav", "mp3", "m4a", "aac", "flac", "ogg", "opus", "wma",
        "mp4", "mov", "m4v", "webm",
    ]

    /// 过滤掉不支持的格式，并截断到批量上限。
    public static func eligible(_ paths: [String], maxBatch: Int) -> [String] {
        let filtered = paths.filter { path in
            supportedExtensions.contains((path as NSString).pathExtension.lowercased())
        }
        return Array(filtered.prefix(maxBatch))
    }

    /// 评估一次拖入：返回可处理路径与对应的用户提示。
    ///
    /// 提示规则（优先级从高到低）：
    /// - 全部不支持 → "拖入的文件都不是支持的音频/视频格式"
    /// - 部分被忽略（格式不支持或超过批量上限）→ "已忽略部分文件，只处理前 N 个"
    /// - 全部可处理 → 无提示
    public static func evaluate(_ paths: [String], maxBatch: Int) -> DropResult {
        let eligiblePaths = eligible(paths, maxBatch: maxBatch)
        if eligiblePaths.isEmpty {
            let note = paths.isEmpty ? nil : "拖入的文件都不是支持的音频/视频格式"
            return DropResult(paths: [], note: note)
        }
        let note = eligiblePaths.count < paths.count
            ? "已忽略部分文件，只处理前 \(eligiblePaths.count) 个"
            : nil
        return DropResult(paths: eligiblePaths, note: note)
    }
}
