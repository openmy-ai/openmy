import Foundation
import Observation
import AVFoundation

/// 场景音频回放：包一层 AVPlayer，把 chunk 音频按场景区间播放。
///
/// 这是 AVPlayer 胶水层，切片数学/进度映射/边界判定全部委托给纯逻辑 ScenePlayback，
/// 便于单测。视图层只读 `progress` / `isPlaying` / `errorMessage`，调用 load/play/pause/seek/setRate。
///
/// 语义对齐 app/static/modules/playback.js：
/// load → seek 到 offsetStart → 播到 sceneEnd 自动暂停 → progress 相对场景起点 → 支持倍速。
@MainActor
@Observable
public final class AudioPlayerModel {
    /// 是否正在播放。
    public private(set) var isPlaying = false
    /// 场景内进度（秒，相对场景起点）。
    public private(set) var progress: Double = 0
    /// 当前场景时长（秒），供进度条计算比例。
    public private(set) var sceneDuration: Double = 0
    /// 错误兜底信息。
    public private(set) var errorMessage: String?
    /// 当前倍速。
    public private(set) var rate: Double = PlaybackRate.default

    private let player = AVPlayer()
    private var timeObserver: Any?
    /// 当前加载的音频区间，用于进度映射与边界判定。
    private var currentRef: AudioRef?

    public init() {}

    // 不在 deinit 里手动移除 observer：@MainActor 隔离属性无法在 nonisolated deinit 访问
    // （Swift 6 严格并发）。观察器闭包用 [weak self]，self 释放后回调直接 no-op；
    // 且 timeObserver token 随 player 一同释放，无悬挂回调风险。load 时先 removeObserver 再重挂。

    /// 加载某段 chunk 音频的一个场景区间，seek 到场景起点，记忆倍速但不自动播放。
    /// - ref: 场景音频引用，决定起点/终点/时长。
    /// - rate: 初始倍速，会被钳制到合法选项。
    public func load(url: URL, ref: AudioRef, rate: Double = PlaybackRate.default) {
        errorMessage = nil
        removeObserver()

        currentRef = ref
        self.rate = PlaybackRate.clamp(rate)
        sceneDuration = ScenePlayback.sceneDuration(ref)
        progress = 0
        isPlaying = false

        let item = AVPlayerItem(url: url)
        player.replaceCurrentItem(with: item)

        let start = ScenePlayback.sceneStart(ref)
        seekToAbsolute(start)
        addObserver()
    }

    /// 开始播放（套用记忆的倍速）。
    public func play() {
        guard currentRef != nil else { return }
        player.rate = Float(rate)
        isPlaying = true
    }

    /// 暂停。
    public func pause() {
        player.pause()
        isPlaying = false
    }

    /// 设置倍速（钳制到合法选项）。播放中即时生效。
    public func setRate(_ newRate: Double) {
        rate = PlaybackRate.clamp(newRate)
        if isPlaying {
            player.rate = Float(rate)
        }
    }

    /// seek 到场景内某个进度（秒）。
    public func seek(toSceneProgress sceneProgress: Double) {
        guard let ref = currentRef else { return }
        let absolute = ScenePlayback.absoluteTime(in: ref, sceneProgress: sceneProgress)
        seekToAbsolute(absolute)
        progress = ScenePlayback.progress(in: ref, absoluteTime: absolute)
    }

    /// seek 到场景内某个比例 [0,1]（波形点击/拖动用）。
    public func seek(toFraction fraction: Double) {
        guard let ref = currentRef else { return }
        seek(toSceneProgress: ScenePlayback.sceneProgress(in: ref, fraction: fraction))
    }

    // MARK: - 内部

    private func seekToAbsolute(_ seconds: Double) {
        let time = CMTime(seconds: seconds, preferredTimescale: 600)
        player.seek(to: time, toleranceBefore: .zero, toleranceAfter: .zero)
    }

    private func addObserver() {
        let interval = CMTime(seconds: 0.1, preferredTimescale: 600)
        timeObserver = player.addPeriodicTimeObserver(forInterval: interval, queue: .main) { [weak self] time in
            // 回调在 .main 队列触发，转入 MainActor 访问可变状态。
            MainActor.assumeIsolated {
                guard let self, let ref = self.currentRef else { return }
                let absolute = time.seconds
                self.progress = ScenePlayback.progress(in: ref, absoluteTime: absolute)
                // 到场景终点自动暂停并停在终点。
                if self.isPlaying && ScenePlayback.reachedEnd(ref, absoluteTime: absolute) {
                    self.pause()
                    self.progress = ScenePlayback.sceneDuration(ref)
                }
                // 监测播放器错误兜底。
                if let error = self.player.currentItem?.error {
                    self.errorMessage = error.localizedDescription
                    self.pause()
                }
            }
        }
    }

    private func removeObserver() {
        if let timeObserver {
            player.removeTimeObserver(timeObserver)
            self.timeObserver = nil
        }
    }
}
