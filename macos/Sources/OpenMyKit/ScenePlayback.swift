import Foundation

/// 场景播放的切片数学：把 chunk 音频的绝对时间与场景内进度互相换算。
///
/// 语义对齐 app/static/modules/playback.js：
/// - 场景起点 sceneStart = offsetStart。
/// - 场景终点 sceneEnd：offsetEnd > offsetStart 时取 offsetEnd；否则用 durationSeconds 兜底为整段。
/// - 进度相对场景起点（chunk 绝对时间 - sceneStart），并钳制在 [0, sceneDuration]。
public enum ScenePlayback {

    /// 场景在 chunk 内的绝对起点（秒）。
    public static func sceneStart(_ ref: AudioRef) -> Double {
        ref.offsetStart
    }

    /// 场景在 chunk 内的绝对终点（秒）。offsetEnd 无效（<= offsetStart）时用整段兜底。
    public static func sceneEnd(_ ref: AudioRef) -> Double {
        if ref.offsetEnd > ref.offsetStart {
            return ref.offsetEnd
        }
        // 兜底为整段：从场景起点到 chunk 末尾。
        return max(ref.offsetStart, ref.durationSeconds)
    }

    /// 场景时长（秒），保证非负。
    public static func sceneDuration(_ ref: AudioRef) -> Double {
        max(0, sceneEnd(ref) - sceneStart(ref))
    }

    /// 把 chunk 绝对时间映射成场景内进度（秒），钳制在 [0, sceneDuration]。
    public static func progress(in ref: AudioRef, absoluteTime: Double) -> Double {
        let raw = absoluteTime - sceneStart(ref)
        return min(max(0, raw), sceneDuration(ref))
    }

    /// 把场景内进度（秒）映射回 chunk 绝对时间，先把进度钳制到合法区间。
    public static func absoluteTime(in ref: AudioRef, sceneProgress: Double) -> Double {
        let clamped = min(max(0, sceneProgress), sceneDuration(ref))
        return sceneStart(ref) + clamped
    }

    /// 是否已到/越过场景终点（用于自动暂停）。
    public static func reachedEnd(_ ref: AudioRef, absoluteTime: Double) -> Bool {
        absoluteTime >= sceneEnd(ref)
    }

    /// 把 [0,1] 比例（波形点击/拖动）换算成场景内进度（秒）。
    public static func sceneProgress(in ref: AudioRef, fraction: Double) -> Double {
        let f = min(max(0, fraction), 1)
        return f * sceneDuration(ref)
    }
}
