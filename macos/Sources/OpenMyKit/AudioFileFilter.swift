import Foundation

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
}
