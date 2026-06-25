import SwiftUI
import AVFoundation
import OpenMyKit

/// 字幕复核浮层（.sheet）：复核某个场景的逐句转写。
///
/// 顶部场景信息（时间区间 / 角色），中部按 SentenceSplitter 切出的句子列表（播放时跟读高亮当前句、
/// 点句 seek 到该句起点、每句右侧「纠错」入口），底部波形 + 播放控件（播放/暂停、倍速、进度）。
///
/// 跟读高亮与逐句 seek 都按「句索引占比」估算：第 i 句覆盖 [i/n, (i+1)/n) 这段场景进度。
/// 这是估算而非真实时间对齐——场景内没有逐句时间戳，按句数均分是最接近 Web subtitle-overlay 的近似。
///
/// AudioPlayerModel 由本视图 @State 持有；切片/进度/边界全部委托已单测的 ScenePlayback。
/// CorrectionSheet 复用环境里的 CorrectionsViewModel，把当前句预填为 context。
struct SubtitleReviewView: View {
    /// 当前复核的场景。
    let scene: TranscriptScene
    /// 所属日期：拼音频地址、提交纠错时随 body 带上。
    let date: String
    /// 后端客户端：拼音频流地址。
    let client: APIClient
    /// 关闭浮层。
    var onClose: () -> Void

    /// 共享校正状态机（与侧栏词典、段落纠错同一实例，App 根注入）。
    @Environment(CorrectionsViewModel.self) private var correctionsVM
    /// 全局 Toast 中心，纠错提交成功后弹提示。
    @Environment(ToastCenter.self) private var toastCenter

    /// 场景音频回放：本视图持有，随浮层生命周期存活。
    @State private var player = AudioPlayerModel()
    /// 当前打开的逐句纠错表单：非空时弹出 CorrectionSheet。
    @State private var correctionTarget: SentenceCorrectionTarget?

    /// 场景文本切出的句子列表（跟读高亮 + 逐句纠错的数据源）。
    private var sentences: [String] {
        SentenceSplitter.split(scene.text)
    }

    /// 是否有可播放音频：audioRef 存在即可。
    private var hasAudio: Bool {
        scene.audioRef != nil
    }

    /// 当前播放进度占比 [0,1]：进度条与跟读高亮共用。sceneDuration 为 0 时归 0 避免除零。
    private var progressFraction: Double {
        guard player.sceneDuration > 0 else { return 0 }
        return min(max(0, player.progress / player.sceneDuration), 1)
    }

    /// 当前跟读高亮的句索引：按句数均分场景进度，定位 progressFraction 落在的句段。
    /// 没句子或未播放（fraction=0）时返回 nil，不强制高亮第一句。
    private var activeSentenceIndex: Int? {
        let n = sentences.count
        guard n > 0, progressFraction > 0 else { return nil }
        let idx = Int(progressFraction * Double(n))
        return min(idx, n - 1)
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            sentenceList
            Divider()
            playbackBar
        }
        .frame(width: 560, height: 620)
        .background(Theme.Palette.cardBackground.opacity(0.001))  // 撑满 sheet 命中区
        .onAppear(perform: loadAudioIfNeeded)
        // Esc / 下滑手势 / 点浮层外关闭时也停播，对齐 Web 的 stopScenePlayback。
        .onDisappear { player.pause() }
        // 逐句纠错表单：把该句预填为上下文，原文待用户填入。
        .sheet(item: $correctionTarget) { target in
            CorrectionSheet(
                viewModel: correctionsVM,
                currentDate: date,
                prefillWrong: "",
                prefillContext: target.context,
                onSubmitted: { result in
                    correctionTarget = nil
                    toastCenter.show(correctionToastText(result))
                },
                onCancel: { correctionTarget = nil }
            )
        }
    }

    // MARK: - 顶部场景信息

    private var header: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.md) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                HStack(spacing: Theme.Spacing.sm) {
                    Image(systemName: "waveform")
                        .foregroundStyle(Theme.Palette.accent)
                    Text("场景复核")
                        .font(Theme.Typography.sectionTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                }
                HStack(spacing: Theme.Spacing.sm) {
                    if !timeRangeText.isEmpty {
                        Label(timeRangeText, systemImage: "clock")
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Palette.secondaryText)
                    }
                    if !scene.roleCategory.isEmpty {
                        OMBadge(scene.roleCategory, kind: .accent)
                    }
                }
                if !scene.summary.isEmpty {
                    Text(scene.summary)
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
            Button {
                player.pause()
                onClose()
            } label: {
                Image(systemName: "xmark")
            }
            .omButton(.ghost, size: .icon)
            .help("关闭复核")
        }
        .padding(Theme.Spacing.xl)
    }

    /// 时间区间文案：两端都非空时拼成「start – end」，否则取非空那一端。
    private var timeRangeText: String {
        let s = scene.timeStart.trimmingCharacters(in: .whitespaces)
        let e = scene.timeEnd.trimmingCharacters(in: .whitespaces)
        switch (s.isEmpty, e.isEmpty) {
        case (false, false): return "\(s) – \(e)"
        case (false, true): return s
        case (true, false): return e
        case (true, true): return ""
        }
    }

    // MARK: - 句子列表

    private var sentenceList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    if sentences.isEmpty {
                        Text("这个场景没有可复核的文本")
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Palette.secondaryText)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, Theme.Spacing.lg)
                    } else {
                        ForEach(Array(sentences.enumerated()), id: \.offset) { index, sentence in
                            sentenceRow(index: index, sentence: sentence)
                                .id(index)
                        }
                    }
                }
                .padding(Theme.Spacing.xl)
            }
            // 跟读时把当前句滚到可视区中部。
            .onChange(of: activeSentenceIndex) { _, newValue in
                guard let newValue else { return }
                withAnimation(.easeInOut(duration: 0.2)) {
                    proxy.scrollTo(newValue, anchor: .center)
                }
            }
        }
        .frame(maxHeight: .infinity)
    }

    private func sentenceRow(index: Int, sentence: String) -> some View {
        let isActive = index == activeSentenceIndex
        return HStack(alignment: .top, spacing: Theme.Spacing.md) {
            // 句序号（也是跟读节点）。
            Text("\(index + 1)")
                .font(Theme.Typography.caption)
                .monospacedDigit()
                .foregroundStyle(isActive ? Theme.Palette.accent : Theme.Palette.secondaryText)
                .frame(minWidth: 20, alignment: .trailing)
                .padding(.top, 2)

            // 句子正文：点击 seek 到该句起点。无音频时不可点。
            Button {
                seekToSentence(index)
            } label: {
                Text(sentence)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.primaryText)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            .buttonStyle(.plain)
            .disabled(!hasAudio)
            .help(hasAudio ? "跳到这句开头" : "")

            // 逐句纠错入口。
            Button {
                openCorrection(for: sentence)
            } label: {
                Label("纠错", systemImage: "pencil.line")
                    .labelStyle(.iconOnly)
            }
            .omButton(.ghost, size: .icon)
            .help("修正这句话里的识别错误")
        }
        .padding(Theme.Spacing.sm)
        .background(
            RoundedRectangle(cornerRadius: Theme.Radius.card)
                .fill(isActive ? Theme.Palette.accent.opacity(0.14) : Color.clear)
        )
        .contextMenu {
            Button { openCorrection(for: sentence) } label: {
                Label("纠错这句", systemImage: "pencil.line")
            }
            if hasAudio {
                Button { seekToSentence(index) } label: {
                    Label("跳到这句", systemImage: "play")
                }
            }
        }
    }

    // MARK: - 底部波形 + 播放控件

    private var playbackBar: some View {
        VStack(spacing: Theme.Spacing.md) {
            WaveformStrip(
                speechSegments: scene.audioRef?.speechSegments ?? [],
                sceneDuration: player.sceneDuration,
                progressFraction: progressFraction,
                enabled: hasAudio,
                onSeek: { fraction in player.seek(toFraction: fraction) }
            )
            .frame(height: 56)

            if let err = player.errorMessage {
                OMErrorText(err)
            }

            HStack(spacing: Theme.Spacing.lg) {
                Button {
                    togglePlay()
                } label: {
                    Image(systemName: player.isPlaying ? "pause.circle.fill" : "play.circle.fill")
                        .font(.system(size: 34))
                        .foregroundStyle(Theme.Palette.accent)
                }
                .buttonStyle(.plain)
                .disabled(!hasAudio)
                .help(player.isPlaying ? "暂停" : "播放")

                Text("\(timeText(player.progress)) / \(timeText(player.sceneDuration))")
                    .font(Theme.Typography.caption)
                    .monospacedDigit()
                    .foregroundStyle(Theme.Palette.secondaryText)

                Spacer(minLength: 0)

                rateMenu
            }

            if !hasAudio {
                Text("这个场景没有可回放的音频")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(Theme.Spacing.xl)
    }

    /// 倍速菜单：固定选项 PlaybackRate.options，当前值打勾。
    private var rateMenu: some View {
        Menu {
            ForEach(PlaybackRate.options, id: \.self) { option in
                Button {
                    player.setRate(option)
                } label: {
                    HStack {
                        Text(rateLabel(option))
                        if abs(option - player.rate) < 0.001 {
                            Image(systemName: "checkmark")
                        }
                    }
                }
            }
        } label: {
            Label(rateLabel(player.rate), systemImage: "speedometer")
                .font(Theme.Typography.caption)
        }
        .menuStyle(.borderlessButton)
        .fixedSize()
        .disabled(!hasAudio)
        .help("播放倍速")
    }

    // MARK: - 行为

    /// 进入浮层时加载音频并 seek 到场景起点（不自动播）。
    private func loadAudioIfNeeded() {
        guard let ref = scene.audioRef else { return }
        let url = client.audioURL(date: date, chunkId: ref.chunkId)
        player.load(url: url, ref: ref, rate: player.rate)
    }

    private func togglePlay() {
        if player.isPlaying {
            player.pause()
        } else {
            player.play()
        }
    }

    /// 点句 seek：把第 index 句的起点估算成 index/句数 的占比，seek 过去。
    private func seekToSentence(_ index: Int) {
        guard hasAudio else { return }
        let n = sentences.count
        guard n > 0 else { return }
        let fraction = Double(index) / Double(n)
        player.seek(toFraction: fraction)
    }

    /// 打开某句的纠错表单：该句预填为上下文，原文待填。
    private func openCorrection(for sentence: String) {
        correctionTarget = SentenceCorrectionTarget(context: sentence)
    }

    /// 提交成功后的 Toast 文案：当天有替换时附替换处数。
    private func correctionToastText(_ result: CorrectionResult) -> String {
        if result.replacedInFile > 0 {
            return "已保存校正，当天替换 \(result.replacedInFile) 处"
        }
        return "已保存校正"
    }

    // MARK: - 格式化

    /// 秒数格式化为 mm:ss。
    private func timeText(_ seconds: Double) -> String {
        guard seconds.isFinite, seconds >= 0 else { return "00:00" }
        let total = Int(seconds.rounded())
        return String(format: "%02d:%02d", total / 60, total % 60)
    }

    /// 倍速标签：整数倍速去掉小数（1.0 → 1x）。
    private func rateLabel(_ rate: Double) -> String {
        if rate == rate.rounded() {
            return "\(Int(rate))x"
        }
        return "\(rate)x"
    }
}

// MARK: - 逐句纠错目标

/// 逐句纠错入口数据：驱动 .sheet(item:) 弹出 CorrectionSheet。
/// context 是被纠错的句子，预填到表单上下文框；UUID 作稳定 id（同句可重复打开）。
private struct SentenceCorrectionTarget: Identifiable, Equatable {
    let id = UUID()
    let context: String
}

// MARK: - 波形条

/// 波形条：把语音子区间画成横向色块，叠加播放进度。点击/拖动按落点占比 seek。
///
/// 场景内不暴露原始 PCM 采样，这里用 audio_ref.speech_segments（相对 chunk 的语音区间）
/// 作为可视依据：把每段语音映射到 [0,1] 横轴画块，已播部分用强调色覆盖。
/// 没有语音区间时退化为一条占满的底条，进度照常推进。纯绘制胶水，不写单测。
private struct WaveformStrip: View {
    /// 语音子区间（相对 chunk 起点的秒数对）。
    let speechSegments: [[Double]]
    /// 场景时长（秒），用于把语音区间映射到本场景横轴。
    let sceneDuration: Double
    /// 当前播放进度占比 [0,1]。
    let progressFraction: Double
    /// 是否可交互（有音频）。
    let enabled: Bool
    /// 点击/拖动 seek 回调，参数为落点占比 [0,1]。
    let onSeek: (Double) -> Void

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                // 底槽。
                RoundedRectangle(cornerRadius: Theme.Radius.card)
                    .fill(Theme.Palette.cardBackground)

                Canvas { context, size in
                    drawBars(context: context, size: size)
                }

                // 进度游标。
                if enabled {
                    Rectangle()
                        .fill(Theme.Palette.accent)
                        .frame(width: 2)
                        .offset(x: CGFloat(progressFraction) * geo.size.width - 1)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.card))
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        guard enabled, geo.size.width > 0 else { return }
                        let fraction = min(max(0, value.location.x / geo.size.width), 1)
                        onSeek(fraction)
                    }
            )
        }
    }

    /// 画语音色块：已播部分用强调色，未播部分用淡色。无语音区间时画整条淡底。
    private func drawBars(context: GraphicsContext, size: CGSize) {
        let w = size.width
        let h = size.height
        guard w > 0, h > 0 else { return }

        let played = CGFloat(min(max(0, progressFraction), 1)) * w
        let bars = normalizedBars()

        if bars.isEmpty {
            // 没有语音区间：画一条占满中线的淡条，进度照样能推进。
            let rect = CGRect(x: 0, y: h * 0.4, width: w, height: h * 0.2)
            paint(context: context, rect: rect, playedX: played)
            return
        }

        for (startFrac, endFrac) in bars {
            let x = CGFloat(startFrac) * w
            let bw = max(1, CGFloat(endFrac - startFrac) * w)
            let rect = CGRect(x: x, y: h * 0.15, width: bw, height: h * 0.7)
            paint(context: context, rect: rect, playedX: played)
        }
    }

    /// 一块按已播分界拆成两段上色：左侧（已播）强调色，右侧未播淡色。
    private func paint(context: GraphicsContext, rect: CGRect, playedX: CGFloat) {
        let path = Path(roundedRect: rect, cornerRadius: 2)
        if playedX <= rect.minX {
            context.fill(path, with: .color(Theme.Palette.accent.opacity(0.3)))
        } else if playedX >= rect.maxX {
            context.fill(path, with: .color(Theme.Palette.accent.opacity(0.85)))
        } else {
            // 分界落在块内：左半已播，右半未播。
            let leftRect = CGRect(x: rect.minX, y: rect.minY, width: playedX - rect.minX, height: rect.height)
            let rightRect = CGRect(x: playedX, y: rect.minY, width: rect.maxX - playedX, height: rect.height)
            context.fill(Path(roundedRect: leftRect, cornerRadius: 2), with: .color(Theme.Palette.accent.opacity(0.85)))
            context.fill(Path(roundedRect: rightRect, cornerRadius: 2), with: .color(Theme.Palette.accent.opacity(0.3)))
        }
    }

    /// 把 speech_segments（相对 chunk 的绝对秒）归一到本场景 [0,1] 横轴。
    /// 用 sceneDuration 作分母；区间钳到 [0,1]，丢掉零宽/越界段。
    private func normalizedBars() -> [(Double, Double)] {
        guard sceneDuration > 0 else { return [] }
        var bars: [(Double, Double)] = []
        for seg in speechSegments {
            guard seg.count >= 2 else { continue }
            let s = min(max(0, seg[0] / sceneDuration), 1)
            let e = min(max(0, seg[1] / sceneDuration), 1)
            if e > s {
                bars.append((s, e))
            }
        }
        return bars
    }
}
