import Foundation

/// 倍速选择：固定可选集合 + 钳制 + 循环切换。
///
/// 对齐 Web playbackRate 行为：可选 0.5 / 1 / 1.5 / 2（与 playback.js 的 select 一致），
/// 记忆上次选择，点一下切到下一个（到末尾回到开头）。
public enum PlaybackRate {

    /// 可选倍速集合（升序），与 Web playback.js 的 <select> 选项一致。
    public static let options: [Double] = [0.5, 1.0, 1.5, 2.0]

    /// 默认倍速。
    public static let `default`: Double = 1.0

    /// 把任意倍速钳制到最接近的合法选项。
    public static func clamp(_ rate: Double) -> Double {
        guard let nearest = options.min(by: { abs($0 - rate) < abs($1 - rate) }) else {
            return `default`
        }
        return nearest
    }

    /// 切换到下一个倍速（循环）。先把当前值钳制到合法选项再前进。
    public static func next(after rate: Double) -> Double {
        let current = clamp(rate)
        guard let idx = options.firstIndex(of: current) else { return `default` }
        let nextIdx = (idx + 1) % options.count
        return options[nextIdx]
    }
}
