import SwiftUI
import AVFoundation
import OpenMyKit

/// 波形条：把一组柱峰值用 Canvas 画成居中对称竖条，叠加播放头。
///
/// - 数据来源：调用方把音频解码成 PCM 后经 `WaveformDownsampler.downsample` 得到峰值数组，
///   传入 `samples`（每个元素是该桶的 |sample| 峰值，通常 0…1）。
/// - 播放头：按 `progress / duration` 比例落点；左侧（已播放）用强调色，右侧（未播放）用次要色。
/// - 交互：点击或拖动按 x 比例回调 `onSeek(progress)`，progress 钳制在 [0,1]。
/// - 无数据（`samples` 为空）：画一条占位基线，不渲染播放头、不响应拖动。
///
/// 本视图只负责绘制与交互，不持有播放器；进度与回放由上层 `AudioPlayerModel` 驱动。
/// 解码胶水见文件末尾的 `WaveformLoader`（需真实音频，不写单测）。
public struct WaveformView: View {
    /// 柱峰值数组（每桶一根竖条的高度比例，约 0…1）。空数组渲染占位。
    private let samples: [Float]
    /// 当前播放进度（场景内秒）。
    private let progress: Double
    /// 总时长（场景时长，秒）。<= 0 时不渲染播放头。
    private let duration: Double
    /// 拖动/点击回调：传回 [0,1] 的目标比例。
    private let onSeek: (Double) -> Void

    /// 竖条之间的间隙占单根槽位宽度的比例。
    private let barGapRatio: CGFloat = 0.35
    /// 竖条最小高度（即使峰值为 0 也留一点点，避免完全空白）。
    private let minBarHeight: CGFloat = 1

    public init(
        samples: [Float],
        progress: Double,
        duration: Double,
        onSeek: @escaping (Double) -> Void
    ) {
        self.samples = samples
        self.progress = progress
        self.duration = duration
        self.onSeek = onSeek
    }

    /// 当前播放比例 [0,1]。duration<=0 时为 0。
    private var playFraction: CGFloat {
        guard duration > 0 else { return 0 }
        let f = progress / duration
        return CGFloat(min(max(f, 0), 1))
    }

    public var body: some View {
        GeometryReader { geo in
            Canvas { context, size in
                guard !samples.isEmpty else {
                    drawPlaceholder(in: &context, size: size)
                    return
                }
                drawBars(in: &context, size: size)
                drawPlayhead(in: &context, size: size)
            }
            .contentShape(Rectangle())
            .gesture(seekGesture(width: geo.size.width))
        }
        .accessibilityLabel("音频波形")
        .accessibilityValue(samples.isEmpty ? "无波形数据" : "进度 \(Int(playFraction * 100))%")
    }

    // MARK: - 绘制

    /// 居中对称竖条：每根条以中线为基准上下对称延展，长度由峰值决定。
    private func drawBars(in context: inout GraphicsContext, size: CGSize) {
        let midY = size.height / 2
        let count = samples.count
        guard count > 0, size.width > 0, size.height > 0 else { return }

        let slot = size.width / CGFloat(count)
        let barWidth = max(slot * (1 - barGapRatio), 0.5)
        // 峰值归一化：以数组中最大峰值为满高，避免整体偏矮。全 0 时退化为最小高度。
        let peak = samples.max() ?? 0
        let scale: CGFloat = peak > 0 ? (size.height / 2) / CGFloat(peak) : 0

        let splitX = size.width * playFraction

        for i in 0..<count {
            let x = CGFloat(i) * slot + (slot - barWidth) / 2
            let half = max(CGFloat(samples[i]) * scale, minBarHeight / 2)
            let rect = CGRect(x: x, y: midY - half, width: barWidth, height: half * 2)
            let bar = Path(roundedRect: rect, cornerRadius: barWidth / 2)
            // 整根条按其中心是否在播放头左侧上色：已播放强调色，未播放次要色。
            let center = x + barWidth / 2
            let played = duration > 0 && center <= splitX
            let color = played ? Theme.Palette.accent : Theme.Palette.secondaryText.opacity(0.45)
            context.fill(bar, with: .color(color))
        }
    }

    /// 播放头：一条竖线落在 playFraction 处。duration<=0 不画。
    private func drawPlayhead(in context: inout GraphicsContext, size: CGSize) {
        guard duration > 0 else { return }
        let x = size.width * playFraction
        var line = Path()
        line.move(to: CGPoint(x: x, y: 0))
        line.addLine(to: CGPoint(x: x, y: size.height))
        context.stroke(line, with: .color(Theme.Palette.accent), lineWidth: 1.5)
    }

    /// 占位：无数据时画一条居中淡基线。
    private func drawPlaceholder(in context: inout GraphicsContext, size: CGSize) {
        guard size.width > 0 else { return }
        let midY = size.height / 2
        var line = Path()
        line.move(to: CGPoint(x: 0, y: midY))
        line.addLine(to: CGPoint(x: size.width, y: midY))
        context.stroke(
            line,
            with: .color(Theme.Palette.secondaryText.opacity(0.25)),
            style: StrokeStyle(lineWidth: 1, dash: [4, 4])
        )
    }

    // MARK: - 交互

    /// 点击或拖动 seek：把触点 x（相对画布左上角）换算成 [0,1] 比例回调。
    /// minimumDistance 为 0，所以单击（无拖动）也会触发一次 onChanged。无数据/无时长时不响应。
    private func seekGesture(width: CGFloat) -> some Gesture {
        DragGesture(minimumDistance: 0)
            .onChanged { value in
                guard !samples.isEmpty, duration > 0, width > 0 else { return }
                let fraction = min(max(value.location.x / width, 0), 1)
                onSeek(Double(fraction))
            }
    }
}

// MARK: - 解码工具

/// 波形解码胶水：从音频 URL 读出 PCM，降采样成柱峰值数组供 `WaveformView` 绘制。
///
/// 用 AVAssetReader 读单声道 32 位浮点 PCM，逐块取样本，再交给纯逻辑
/// `WaveformDownsampler.downsample` 压成 `buckets` 根竖条。任何解码失败（无音轨、
/// 读取出错、格式异常）都安全返回 `[]`，由视图侧渲染占位，绝不抛错打断 UI。
///
/// 需要真实音频才能验证，属胶水层，不写单测；切片与降采样数学已在 `WaveformDownsampler` 单测覆盖。
public enum WaveformLoader {

    /// 解码 `url` 指向的音频并降采样为 `buckets` 根竖条峰值。
    /// - Parameters:
    ///   - url: 音频文件或可读 URL（如 APIClient.audioURL 拼出的本地 chunk 地址）。
    ///   - buckets: 目标柱数。<=0 直接返回 []。
    /// - Returns: 峰值数组（约 0…1）；解码失败返回 []。
    public static func loadPeaks(from url: URL, buckets: Int) async -> [Float] {
        guard buckets > 0 else { return [] }
        do {
            return try await decode(url: url, buckets: buckets)
        } catch {
            return []
        }
    }

    private static func decode(url: URL, buckets: Int) async throws -> [Float] {
        let asset = AVURLAsset(url: url)
        let tracks = try await asset.loadTracks(withMediaType: .audio)
        guard let track = tracks.first else { return [] }

        let reader = try AVAssetReader(asset: asset)
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVLinearPCMBitDepthKey: 32,
            AVLinearPCMIsFloatKey: true,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsNonInterleaved: false,
            AVNumberOfChannelsKey: 1,
        ]
        let output = AVAssetReaderTrackOutput(track: track, outputSettings: settings)
        output.alwaysCopiesSampleData = false
        guard reader.canAdd(output) else { return [] }
        reader.add(output)
        guard reader.startReading() else { return [] }

        var samples: [Float] = []
        while let buffer = output.copyNextSampleBuffer() {
            guard let block = CMSampleBufferGetDataBuffer(buffer) else {
                CMSampleBufferInvalidate(buffer)
                continue
            }
            let length = CMBlockBufferGetDataLength(block)
            guard length > 0 else {
                CMSampleBufferInvalidate(buffer)
                continue
            }
            var data = [UInt8](repeating: 0, count: length)
            let status = data.withUnsafeMutableBytes { raw -> OSStatus in
                CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: length, destination: raw.baseAddress!)
            }
            if status == kCMBlockBufferNoErr {
                data.withUnsafeBytes { raw in
                    let floats = raw.bindMemory(to: Float.self)
                    samples.append(contentsOf: floats)
                }
            }
            CMSampleBufferInvalidate(buffer)
        }

        if reader.status == .failed { return [] }
        return WaveformDownsampler.downsample(samples, buckets: buckets)
    }
}
