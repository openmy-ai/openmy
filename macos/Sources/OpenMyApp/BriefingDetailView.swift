import SwiftUI
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
    @State private var transcriptExpanded = false
    @State private var loadingTranscript = false
    @State private var transcriptError: String?

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
            segments = try await client.dateDetail(date: briefing.date).segments
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
            segments = try await client.dateDetail(date: briefing.date).segments
        } catch {
            transcriptError = "加载失败：\(error)"
        }
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
