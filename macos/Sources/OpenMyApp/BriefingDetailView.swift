import SwiftUI
import AVFoundation
import Charts
import OpenMyKit

/// 日报详情。用设计系统 token 重做：头部统计卡片 + 分区块卡片，
/// 每个区块有强调色标题条，时间线、关键事件、待办、洞察各自有区分样式。
struct BriefingDetailView: View {
    let briefing: Briefing
    let client: APIClient
    /// 来自搜索的跳转焦点。date 命中本日报时自动展开转写、滚动定位并段内高亮。
    var focus: SearchFocus?
    /// 行内纠错应用成功后上抛：让 MainView 整日重载（纠错也改写蒸馏正文，对齐 Web loadDate）。
    var onCorrectionApplied: () -> Void = {}

    /// 共享校正状态机（与侧栏词典、新增校正同一实例，App 根注入）。
    @Environment(CorrectionsViewModel.self) private var correctionsVM
    /// 全局 Toast 中心，提交成功后弹一条提示。
    @Environment(ToastCenter.self) private var toastCenter

    /// 下钻：逐段原始转写。展开时懒加载。
    @State private var segments: [TranscriptSegment] = []
    /// 场景列表（与 segments 同一次 dateDetail 拉取）。仅含有音频引用的可回放。
    @State private var scenes: [TranscriptScene] = []
    @State private var transcriptExpanded = false
    @State private var loadingTranscript = false
    @State private var transcriptError: String?

    /// 当前打开字幕复核的场景：非空时弹出 SubtitleReviewView 浮层。
    @State private var reviewScene: TranscriptScene?

    /// 本日 meta 四分区（发生/打算/记住/决定）。进入时拉取，缺失/为空全降级空数组。
    @State private var dateMeta: DateMeta?

    /// 当前打开的纠错表单：非空时弹出 CorrectionSheet。
    /// 由某段转写的「纠错」入口触发，把该段文本预填为 context。
    @State private var correctionTarget: CorrectionTarget?

    /// 已消费的焦点：同一个 focus 只触发一次定位，避免无限重触发。
    @State private var consumedFocus: SearchFocus?
    /// 待滚动到的段落时间标记。转写加载完成后由 onChange 触发滚动并清空。
    @State private var pendingScrollTime: String?

    /// 当前生效的段内高亮关键词：仅当 focus 命中本日报时非空。
    private var activeQuery: String? {
        guard let focus, focus.date == briefing.date else { return nil }
        let q = focus.query.trimmingCharacters(in: .whitespacesAndNewlines)
        return q.isEmpty ? nil : focus.query
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
                    header

                    if !briefing.summary.isEmpty {
                        SectionCard(title: "摘要", systemImage: "text.alignleft") {
                            Text(briefing.summary)
                                .font(Theme.Typography.body)
                                .foregroundStyle(Theme.Palette.primaryText)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }

                    if !briefing.timeBlocks.isEmpty {
                        SectionCard(title: "时间线", systemImage: "clock") {
                            timeline
                        }
                    }

                    if hasHourActivity {
                        SectionCard(title: "时段热度", systemImage: "chart.bar") {
                            hourHeatmap
                        }
                    }

                    metaSection

                    if !briefing.keyEvents.isEmpty {
                        SectionCard(title: "关键事件", systemImage: "star") {
                            bullets(briefing.keyEvents, marker: .dot)
                        }
                    }

                    if !briefing.todosOpen.isEmpty {
                        SectionCard(title: "待办", systemImage: "checklist") {
                            bullets(briefing.todosOpen, marker: .checkbox)
                        }
                    }

                    if !briefing.insights.isEmpty {
                        SectionCard(title: "洞察", systemImage: "lightbulb") {
                            insights
                        }
                    }

                    transcriptSection
                }
                .padding(Theme.Spacing.xxl)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            // 进入时加载头部统计/时段热度所需的逐段转写与 meta（不展开原始记录区块）。
            .task(id: briefing.date) { await loadStatsData() }
            // 焦点命中本日报：进入时一次性消费，自动展开并加载转写。
            .onAppear { consumeFocusIfNeeded() }
            .onChange(of: focus) { _, _ in consumeFocusIfNeeded() }
            // 转写加载完成后再滚动：此时目标段已渲染，id 才可命中。
            .onChange(of: segments) { _, _ in performPendingScroll(proxy) }
            .onChange(of: pendingScrollTime) { _, _ in performPendingScroll(proxy) }
        }
        // 段落纠错表单：把该段文本预填为上下文，wrong 留空待填。
        .sheet(item: $correctionTarget) { target in
            CorrectionSheet(
                viewModel: correctionsVM,
                currentDate: briefing.date,
                prefillWrong: "",
                prefillContext: target.context,
                onSubmitted: { result in
                    correctionTarget = nil
                    toastCenter.show(correctionToastText(result))
                    Task { await reloadTranscript() }
                    // 纠错会就地改写蒸馏日报正文，上抛让 MainView 整日重载刷新摘要/时间线等。
                    onCorrectionApplied()
                },
                onCancel: { correctionTarget = nil }
            )
        }
        // 字幕复核浮层：逐句对照转写、跟读高亮、底部波形 + 播放控件、逐句纠错。
        // SubtitleReviewView 内部自持 AudioPlayerModel，并复用环境里的 CorrectionsViewModel。
        .sheet(item: $reviewScene) { scene in
            SubtitleReviewView(
                scene: scene,
                date: briefing.date,
                client: client,
                onClose: { reviewScene = nil }
            )
        }
    }

    /// 提交成功后的 Toast 文案：当天文件有替换时附上替换处数，否则仅提示已保存。
    private func correctionToastText(_ result: CorrectionResult) -> String {
        if result.replacedInFile > 0 {
            return "已保存校正，当天替换 \(result.replacedInFile) 处"
        }
        return "已保存校正"
    }

    // MARK: - 焦点定位

    /// 一次性消费 focus：date 命中本日报时展开转写、加载、登记待滚动段。
    private func consumeFocusIfNeeded() {
        guard let focus, focus.date == briefing.date else { return }
        guard consumedFocus != focus else { return }  // 已消费过同一焦点，不重触发
        consumedFocus = focus
        if !focus.time.isEmpty {
            pendingScrollTime = focus.time
        }
        Task { await loadTranscript() }
    }

    /// 若有待滚动段且转写已就绪，滚动到对应段并清空待滚动标记。
    private func performPendingScroll(_ proxy: ScrollViewProxy) {
        guard let time = pendingScrollTime, !segments.isEmpty else { return }
        guard segments.contains(where: { $0.time == time }) else { return }
        withAnimation(.easeInOut) {
            proxy.scrollTo(transcriptRowID(time), anchor: .center)
        }
        pendingScrollTime = nil
    }

    /// 段落行的稳定 id：用时间标记，供 ScrollViewReader 定位。
    private func transcriptRowID(_ time: String) -> String { "transcript-\(time)" }

    /// 打开某段的纠错表单：该段文本预填为上下文，原文待用户填入。
    private func openCorrection(for seg: TranscriptSegment) {
        correctionTarget = CorrectionTarget(time: seg.time, context: seg.text)
    }

    // MARK: - 原始记录下钻

    private var transcriptSection: some View {
        SectionCard(title: "原始记录", systemImage: "text.quote") {
            VStack(alignment: .leading, spacing: Theme.Spacing.md) {
                if transcriptExpanded {
                    if loadingTranscript {
                        HStack(spacing: Theme.Spacing.sm) {
                            ProgressView().controlSize(.small)
                            Text("加载逐段转写…")
                                .font(Theme.Typography.caption)
                                .foregroundStyle(Theme.Palette.secondaryText)
                        }
                    } else if let err = transcriptError {
                        OMErrorText(err)
                    } else if segments.isEmpty {
                        Text("没有逐段转写")
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Palette.secondaryText)
                    } else {
                        ForEach(Array(segments.enumerated()), id: \.offset) { _, seg in
                            VStack(alignment: .leading, spacing: Theme.Spacing.xs / 2) {
                                HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.sm) {
                                    Text(seg.time)
                                        .font(Theme.Typography.caption)
                                        .foregroundStyle(Theme.Palette.accent)
                                        .monospacedDigit()
                                    Spacer(minLength: 0)
                                    Button { openCorrection(for: seg) } label: {
                                        Label("纠错", systemImage: "pencil.line")
                                            .labelStyle(.titleAndIcon)
                                    }
                                    .buttonStyle(.borderless)
                                    .font(Theme.Typography.caption)
                                    .help("修正这段文字里的识别错误")
                                }
                                Text(highlightedText(seg.text))
                                    .font(Theme.Typography.body)
                                    .foregroundStyle(Theme.Palette.primaryText)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .textSelection(.enabled)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .id(transcriptRowID(seg.time))
                            // 右键也能进纠错，与小按钮等价。
                            .contextMenu {
                                Button { openCorrection(for: seg) } label: {
                                    Label("纠错这段", systemImage: "pencil.line")
                                }
                            }
                        }
                    }

                    if !playableScenes.isEmpty {
                        scenesBlock
                    }

                    Button("收起") { transcriptExpanded = false }
                        .buttonStyle(.borderless)
                        .font(Theme.Typography.caption)
                } else {
                    Button {
                        Task { await loadTranscript() }
                    } label: {
                        Label("查看逐段转写", systemImage: "chevron.down")
                    }
                    .buttonStyle(.bordered)
                }
            }
        }
    }

    // MARK: - 场景回放

    /// 可回放场景区块：每个场景一张卡片，含播放原声内联播放器 + 字幕复核入口。
    private var scenesBlock: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            Divider()
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: "waveform")
                    .font(.subheadline)
                    .foregroundStyle(Theme.Palette.accent)
                Text("场景原声")
                    .font(Theme.Typography.cardTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
            }
            ForEach(playableScenes) { scene in
                SceneRowView(
                    scene: scene,
                    date: briefing.date,
                    client: client,
                    onReview: { reviewScene = scene }
                )
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// 段内关键词高亮：focus 命中本日报时，把段落文本里命中 query 的子串上色。
    /// segments 来自 dateDetail 是无标记原文，故对 rawText 做大小写不敏感匹配。
    private func highlightedText(_ text: String) -> AttributedString {
        guard let query = activeQuery else { return AttributedString(text) }

        var attributed = AttributedString(text)
        var searchStart = text.startIndex
        while searchStart < text.endIndex,
              let range = text.range(
                of: query,
                options: .caseInsensitive,
                range: searchStart..<text.endIndex
              ) {
            if let lower = AttributedString.Index(range.lowerBound, within: attributed),
               let upper = AttributedString.Index(range.upperBound, within: attributed) {
                attributed[lower..<upper].backgroundColor = Theme.Palette.accent.opacity(0.28)
                attributed[lower..<upper].foregroundColor = Theme.Palette.primaryText
            }
            // 命中长度为 0 时强制前移，避免死循环
            searchStart = range.upperBound > range.lowerBound ? range.upperBound : text.index(after: range.lowerBound)
        }
        return attributed
    }

    private func loadTranscript() async {
        transcriptExpanded = true
        transcriptError = nil
        if !segments.isEmpty { return }  // 已加载过，直接展开
        loadingTranscript = true
        defer { loadingTranscript = false }
        do {
            let detail = try await client.dateDetail(date: briefing.date)
            segments = detail.segments
            scenes = detail.scenes
        } catch {
            transcriptError = "加载失败：\(error)"
        }
    }

    /// 纠错提交成功后强制重拉逐段转写：后端已就地替换当天文件，刷新展示替换后的文本。
    /// 与 loadTranscript 不同——不因 segments 非空提前返回。
    private func reloadTranscript() async {
        guard transcriptExpanded else { return }
        transcriptError = nil
        loadingTranscript = true
        defer { loadingTranscript = false }
        do {
            let detail = try await client.dateDetail(date: briefing.date)
            segments = detail.segments
            scenes = detail.scenes
        } catch {
            transcriptError = "加载失败：\(error)"
        }
    }

    /// 有音频可回放的场景子集。
    private var playableScenes: [TranscriptScene] {
        scenes.filter { $0.audioRef != nil }
    }

    /// 进入时为头部统计与时段热度预取数据：逐段转写（取 time 算跨度/分桶）+ meta 四分区。
    /// 不展开「原始记录」区块；失败静默（这些只是增强信息，不阻断主体渲染）。
    private func loadStatsData() async {
        if segments.isEmpty {
            if let detail = try? await client.dateDetail(date: briefing.date) {
                segments = detail.segments
                scenes = detail.scenes
            }
        }
        if dateMeta == nil {
            dateMeta = try? await client.dateMeta(date: briefing.date)
        }
    }

    /// 逐段时间串（用于首末跨度与时段分桶）。
    private var segmentTimes: [String] {
        segments.map(\.time)
    }

    // MARK: - 头部

    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            Text(briefing.date)
                .font(Theme.Typography.pageTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            HStack(spacing: Theme.Spacing.md) {
                metricCard("\(briefing.totalScenes)", "场景")
                metricCard("\(briefing.totalWords)", "字")
                metricCard(String(format: "%.1f", briefing.voiceHours), "小时语音")
                if let span = TimeSpan.span(times: segmentTimes) {
                    metricCard("\(span.first)–\(span.last)", "时间跨度")
                }
            }
        }
        .omSection()
    }

    private func metricCard(_ value: String, _ label: String) -> some View {
        OMMetric(value: value, label: label)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.md)
            .omCard()
    }

    // MARK: - 时间线

    private var timeline: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(briefing.timeBlocks.enumerated()), id: \.element.period) { index, tb in
                HStack(alignment: .top, spacing: Theme.Spacing.md) {
                    // 时间轴竖线 + 节点
                    VStack(spacing: 0) {
                        Circle()
                            .fill(Theme.Palette.accent)
                            .frame(width: 8, height: 8)
                            .padding(.top, Theme.Spacing.xs)
                        if index < briefing.timeBlocks.count - 1 {
                            Rectangle()
                                .fill(Theme.Palette.accent.opacity(0.25))
                                .frame(width: 2)
                                .frame(maxHeight: .infinity)
                        }
                    }
                    .frame(width: 8)

                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        Text(tb.period)
                            .font(Theme.Typography.cardTitle)
                            .foregroundStyle(Theme.Palette.primaryText)
                        Text(tb.summary)
                            .font(Theme.Typography.body)
                            .foregroundStyle(Theme.Palette.secondaryText)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.bottom, index < briefing.timeBlocks.count - 1 ? Theme.Spacing.lg : 0)

                    Spacer(minLength: 0)
                }
            }
        }
    }

    // MARK: - 时段热度

    /// 24 小时活跃分桶（下标即小时）。从逐段时间串计数。
    private var hourCounts: [Int] {
        HourHistogram.counts(times: segmentTimes)
    }

    /// 是否有可画的活跃数据：任一小时桶非空。空则整个区块不渲染。
    private var hasHourActivity: Bool {
        hourCounts.contains { $0 > 0 }
    }

    /// 24 小时活跃柱状图：每根柱代表一个整点小时的段落数。
    private var hourHeatmap: some View {
        Chart(Array(hourCounts.enumerated()), id: \.offset) { hour, count in
            BarMark(
                x: .value("小时", Double(hour)),
                y: .value("段落数", count)
            )
            .foregroundStyle(Theme.Palette.accent)
            .cornerRadius(2)
        }
        .chartXScale(domain: -0.5...23.5)
        .chartXAxis {
            AxisMarks(values: [0.0, 6.0, 12.0, 18.0, 23.0]) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let hour = value.as(Double.self) {
                        Text(String(format: "%02d", Int(hour)))
                            .font(Theme.Typography.caption)
                    }
                }
            }
        }
        .chartYAxis {
            AxisMarks(position: .leading)
        }
        .frame(height: 160)
        .frame(maxWidth: .infinity)
    }

    // MARK: - meta 四分区（发生/打算/记住/决定）

    /// meta 四分区卡片：仅当对应类目非空才显示。四类全空时整个区块不渲染。
    @ViewBuilder
    private var metaSection: some View {
        if let meta = dateMeta {
            if !meta.events.isEmpty {
                SectionCard(title: "发生", systemImage: "sparkles") {
                    metaEntries(meta.events)
                }
            }
            if !meta.intents.isEmpty {
                SectionCard(title: "打算", systemImage: "flag") {
                    metaEntries(meta.intents)
                }
            }
            if !meta.facts.isEmpty {
                SectionCard(title: "记住", systemImage: "brain") {
                    metaEntries(meta.facts)
                }
            }
            if !meta.decisions.isEmpty {
                SectionCard(title: "决定", systemImage: "checkmark.seal") {
                    metaEntries(meta.decisions)
                }
            }
        }
    }

    /// 一组 meta 项渲染：每项一行，时间/项目标签在前，文本在后。
    private func metaEntries(_ entries: [MetaEntry]) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            ForEach(Array(entries.enumerated()), id: \.offset) { _, entry in
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    if !entry.time.isEmpty || !entry.project.isEmpty {
                        HStack(spacing: Theme.Spacing.sm) {
                            if !entry.time.isEmpty {
                                Text(entry.time)
                                    .font(Theme.Typography.caption)
                                    .foregroundStyle(Theme.Palette.accent)
                                    .monospacedDigit()
                            }
                            if !entry.project.isEmpty {
                                OMBadge(entry.project, kind: .neutral)
                            }
                            Spacer(minLength: 0)
                        }
                    }
                    if !entry.text.isEmpty {
                        Text(entry.text)
                            .font(Theme.Typography.body)
                            .foregroundStyle(Theme.Palette.primaryText)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    // MARK: - 洞察

    private var insights: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            ForEach(briefing.insights, id: \.topic) { insight in
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    OMBadge(insight.topic, kind: .accent)
                    Text(insight.content)
                        .font(Theme.Typography.body)
                        .foregroundStyle(Theme.Palette.primaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    // MARK: - 列表项

    private enum BulletMarker {
        case dot
        case checkbox
    }

    private func bullets(_ items: [String], marker: BulletMarker) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            ForEach(items, id: \.self) { item in
                HStack(alignment: .top, spacing: Theme.Spacing.sm) {
                    switch marker {
                    case .dot:
                        Circle()
                            .fill(Theme.Palette.accent)
                            .frame(width: 6, height: 6)
                            .padding(.top, 6)
                    case .checkbox:
                        Image(systemName: "square")
                            .font(.caption)
                            .foregroundStyle(Theme.Palette.secondaryText)
                            .padding(.top, 2)
                    }
                    Text(item)
                        .font(Theme.Typography.body)
                        .foregroundStyle(Theme.Palette.primaryText)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
            }
        }
    }
}

// MARK: - 纠错目标

/// 某段转写的纠错入口数据：驱动 .sheet(item:) 弹出 CorrectionSheet。
/// time 既是稳定 id，也对应转写行；context 是该段原文，预填到表单的上下文框。
private struct CorrectionTarget: Identifiable, Equatable {
    let time: String
    let context: String
    var id: String { time }
}

// MARK: - 角色徽章（按 RoleColorKey 配色）

/// 场景角色徽章：把原始 role.category 归一到 RoleColorKey，按类目取色。
/// 原始文案照常展示，仅底色/前景色随角色类别变化，便于一眼区分对话对象。
private struct RoleBadge: View {
    let role: String

    var body: some View {
        let key = RoleColorKey.from(role)
        let color = RoleBadge.color(for: key)
        Text(role)
            .font(.caption2)
            .padding(.horizontal, Theme.Spacing.sm)
            .padding(.vertical, Theme.Spacing.xs / 2)
            .foregroundStyle(color)
            .background(color.opacity(0.18))
            .clipShape(Capsule())
    }

    /// 角色类别 → 展示色。rawValue 稳定，便于映射。
    static func color(for key: RoleColorKey) -> Color {
        switch key {
        case .ai: return .blue
        case .merchant: return .orange
        case .pet: return .pink
        case .self: return .purple
        case .interpersonal: return .green
        case .uncertain: return Theme.Palette.secondaryText
        case .other: return Theme.Palette.secondaryText
        }
    }
}

// MARK: - 区块卡片容器

/// 带强调色标题条的区块卡片：图标 + 标题在上，内容在卡片内。
private struct SectionCard<Content: View>: View {
    let title: String
    let systemImage: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: systemImage)
                    .font(.subheadline)
                    .foregroundStyle(Theme.Palette.accent)
                Text(title)
                    .font(Theme.Typography.sectionTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
            }

            content()
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(Theme.Spacing.lg)
                .background(Theme.Palette.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.container))
        }
        .omSection()
    }
}

// MARK: - 场景行（播放原声 + 字幕复核）

/// 单个可回放场景：摘要/文本预览 + 内联播放器 + 字幕复核按钮。
/// 播放器（AudioPlayerModel）首次点「播放原声」时才 load，避免一次性为所有场景建 AVPlayerItem。
private struct SceneRowView: View {
    let scene: TranscriptScene
    let date: String
    let client: APIClient
    /// 打开字幕复核浮层。
    let onReview: () -> Void

    /// 该场景独立的播放器实例。
    @State private var playerModel = AudioPlayerModel()
    /// 是否已对该场景调用过 load（决定是否展示内联播放器条）。
    @State private var loaded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            // 顶部：时间区间 + 角色徽章。
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.sm) {
                Text(timeLabel)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.accent)
                    .monospacedDigit()
                if !scene.roleCategory.isEmpty {
                    RoleBadge(role: scene.roleCategory)
                }
                Spacer(minLength: 0)
            }

            // 文本预览：优先摘要，否则正文。
            let preview = scene.summary.isEmpty ? scene.text : scene.summary
            if !preview.isEmpty {
                Text(preview)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.primaryText)
                    .fixedSize(horizontal: false, vertical: true)
                    .lineLimit(3)
            }

            // 操作行：播放原声 + 字幕复核。
            HStack(spacing: Theme.Spacing.md) {
                Button { togglePlay() } label: {
                    Label(
                        playerModel.isPlaying ? "暂停" : "播放原声",
                        systemImage: playerModel.isPlaying ? "pause.fill" : "play.fill"
                    )
                }
                .buttonStyle(.bordered)
                .help("播放这段场景对应的原始录音")

                Button { onReview() } label: {
                    Label("字幕复核", systemImage: "text.badge.checkmark")
                }
                .buttonStyle(.borderless)
                .font(Theme.Typography.caption)
                .help("逐句对照字幕，发现错字可跳到纠错")

                Spacer(minLength: 0)
            }

            // 内联播放器条：仅在已 load 后展示进度与倍速。
            if loaded {
                playerBar
            }

            OMErrorText(playerModel.errorMessage)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.md)
        .omCard()
        // 折叠转写 / 离开日报详情时停播，避免被移除后 AVPlayer 还在出声。
        .onDisappear { playerModel.pause() }
    }

    /// 时间区间标签，如 "00:05 – 00:42"；缺一端时只显示存在的一端。
    private var timeLabel: String {
        switch (scene.timeStart.isEmpty, scene.timeEnd.isEmpty) {
        case (false, false): return "\(scene.timeStart) – \(scene.timeEnd)"
        case (false, true): return scene.timeStart
        case (true, false): return scene.timeEnd
        case (true, true): return ""
        }
    }

    /// 进度条 + 倍速切换。
    private var playerBar: some View {
        HStack(spacing: Theme.Spacing.md) {
            Slider(
                value: Binding(
                    get: { playerModel.sceneDuration > 0 ? playerModel.progress / playerModel.sceneDuration : 0 },
                    set: { playerModel.seek(toFraction: $0) }
                ),
                in: 0...1
            )
            Text(progressLabel)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
                .monospacedDigit()
            Button {
                playerModel.setRate(PlaybackRate.next(after: playerModel.rate))
            } label: {
                Text(rateLabel)
                    .font(Theme.Typography.caption)
                    .monospacedDigit()
            }
            .buttonStyle(.bordered)
            .help("切换播放速度")
        }
    }

    /// 进度文本：当前/总时长，按 m:ss。
    private var progressLabel: String {
        "\(formatTime(playerModel.progress)) / \(formatTime(playerModel.sceneDuration))"
    }

    /// 倍速文本，如 "1x" / "1.25x"。整数倍速不带小数。
    private var rateLabel: String {
        let r = playerModel.rate
        if r == r.rounded() {
            return "\(Int(r))x"
        }
        return "\(r)x"
    }

    /// 秒数格式化为 m:ss。
    private func formatTime(_ seconds: Double) -> String {
        let total = Int(seconds.rounded())
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    /// 播放/暂停切换。首次播放时先 load 音频区间。
    private func togglePlay() {
        guard let ref = scene.audioRef else { return }
        if !loaded {
            let url = client.audioURL(date: date, chunkId: ref.chunkId)
            playerModel.load(url: url, ref: ref, rate: playerModel.rate)
            loaded = true
        }
        if playerModel.isPlaying {
            playerModel.pause()
        } else {
            playerModel.play()
        }
    }
}
