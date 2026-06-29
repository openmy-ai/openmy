import SwiftUI
import Charts
import OpenMyKit

/// 周报/月报页。顶部分段控件在「最近 7 天」「最近 30 天」之间切换，
/// 展示活跃天数/录音段数/总字数三张统计卡、每日活跃度柱状图、
/// 活跃项目列表（带出现天数）、决策与待办聚合、最长摘要。
///
/// 数据来源：传入的 `ReportViewModel`（已算好周报/月报与活跃项目标题）、
/// 全部 `dates`（用于在窗口内匹配项目出现天数）以及基准 `today`。
/// 点击某天的柱子通过 `onOpenDate` 回调上抛，由调用方打开对应日报。
///
/// 纯 SwiftUI 视图（含 Charts）按约定不写单测；聚合逻辑在 OpenMyKit 中已 TDD 覆盖。
struct ReportView: View {
    /// 报告视图模型：持有 weekly(7) / monthly(30) 两套聚合结果与活跃项目标题。
    let viewModel: ReportViewModel
    /// 全部日期条目，用于在当前窗口内统计各项目出现天数。
    let dates: [DayEntry]
    /// 基准「今天」日期串（"yyyy-MM-dd"），由调用方提供，避免依赖系统时钟。
    let today: String
    /// 点击某天柱子时回调，参数为该天日期串。
    var onOpenDate: (String) -> Void = { _ in }

    /// 当前选中的窗口。
    @State private var window: ReportWindow = .weekly

    var body: some View {
        ScrollView {
            // 提密度：区块间距 xl→lg、外层留白 xxl→lg，贴近 Linear 的紧凑节奏。
            VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
                header

                if let summary = currentSummary {
                    if summary.totalSegments == 0 && summary.activeDays == 0 {
                        emptyHint
                    } else {
                        metricCards(summary)
                        dailyActivitySection(summary)
                        projectsSection(summary)
                        decisionsSection(summary)
                        todosSection(summary)
                        topSummarySection(summary)
                    }
                } else {
                    skeletonHint
                }
            }
            .padding(Theme.Spacing.lg)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// 当前窗口对应的聚合结果。
    private var currentSummary: ReportSummary? {
        switch window {
        case .weekly: return viewModel.weekly
        case .monthly: return viewModel.monthly
        }
    }

    // MARK: - 头部

    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            Text("报告")
                .font(Theme.Typography.pageTitle)
                .tracking(Theme.Tracking.pageTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            windowPicker
        }
        .omSection()
    }

    /// 周/月切换：克制的自定义分段控件，替代原生 `.segmented`。
    /// `muted` 胶囊轨道 + 两段透明文本，选中段叠 `card` 底 + `accent` 文字，
    /// 未选走 `secondaryText`；按内容收窄、左对齐，不铺满。
    private var windowPicker: some View {
        HStack(spacing: Theme.Spacing.xxs) {
            ForEach(ReportWindow.allCases) { w in
                let selected = window == w
                Button {
                    window = w
                } label: {
                    Text(w.label)
                        .font(Theme.Typography.label)
                        .foregroundStyle(selected ? Theme.Palette.accent : Theme.Palette.secondaryText)
                        .padding(.horizontal, Theme.Spacing.md)
                        .frame(height: 26)
                        .background(selected ? Theme.Palette.card : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.sm))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(Theme.Spacing.xxs)
        .background(Theme.Palette.muted)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
    }

    // MARK: - 统计卡

    /// 密度收紧：三项指标并入单一带边容器，用 `borderSubtle` 细竖线分隔，
    /// 取代三张各自描边的卡片，纵向留白收到 `sm`。
    private func metricCards(_ summary: ReportSummary) -> some View {
        HStack(spacing: 0) {
            metricCell("\(summary.activeDays)", "活跃天数")
            metricDivider
            metricCell("\(summary.totalSegments)", "录音段数")
            metricDivider
            metricCell("\(summary.totalWords)", "总字数")
        }
        .omCard()
        .omSection()
    }

    private func metricCell(_ value: String, _ label: String) -> some View {
        OMMetric(value: value, label: label)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.sm)
    }

    /// 指标之间的极细分隔竖线。
    private var metricDivider: some View {
        Rectangle()
            .fill(Theme.Palette.borderSubtle)
            .frame(width: 1, height: 32)
    }

    // MARK: - 每日活跃度柱状图

    private func dailyActivitySection(_ summary: ReportSummary) -> some View {
        ReportSectionCard(title: "每日活跃度", systemImage: "chart.bar") {
            if summary.perDay.isEmpty {
                Text("窗口内还没有记录")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.tertiaryText)
            } else {
                Chart(summary.perDay, id: \.date) { day in
                    BarMark(
                        x: .value("日期", shortLabel(day.date)),
                        y: .value("段数", day.segments)
                    )
                    .foregroundStyle(Theme.Palette.accent)
                    .cornerRadius(3)
                }
                // X 轴：去网格线，仅留 caption2 + tertiary 轴标签。
                .chartXAxis {
                    AxisMarks(values: .automatic) { _ in
                        AxisValueLabel()
                            .font(Theme.Typography.caption2)
                            .foregroundStyle(Theme.Palette.tertiaryText)
                    }
                }
                // Y 轴：去默认网格线，仅保留 caption2 + tertiary 数值标签。
                .chartYAxis {
                    AxisMarks(position: .leading) { _ in
                        AxisValueLabel()
                            .font(Theme.Typography.caption2)
                            .foregroundStyle(Theme.Palette.tertiaryText)
                    }
                }
                // 点击图表落到最近的柱子，回调对应日期。
                .chartOverlay { proxy in
                    GeometryReader { geo in
                        Rectangle()
                            .fill(Color.clear)
                            .contentShape(Rectangle())
                            .onTapGesture { location in
                                handleChartTap(at: location, proxy: proxy, geo: geo, summary: summary)
                            }
                    }
                }
                .frame(height: 200)

                Text("点击柱子查看当天日报")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.tertiaryText)
            }
        }
    }

    /// 把点击坐标映射回 x 轴的日期标签，再还原成完整日期并回调。
    private func handleChartTap(
        at location: CGPoint, proxy: ChartProxy, geo: GeometryProxy,
        summary: ReportSummary
    ) {
        let origin = geo[proxy.plotFrame!].origin
        let xInPlot = location.x - origin.x
        guard let label: String = proxy.value(atX: xInPlot) else { return }
        // 短标签可能重复（跨月同日），优先在 perDay 顺序里找首个匹配。
        if let match = summary.perDay.first(where: { shortLabel($0.date) == label }) {
            onOpenDate(match.date)
        }
    }

    /// 把 "yyyy-MM-dd" 压成 "MM-DD" 短标签用于横轴。非法日期原样返回。
    private func shortLabel(_ date: String) -> String {
        let parts = date.split(separator: "-")
        guard parts.count == 3 else { return date }
        return "\(parts[1])-\(parts[2])"
    }

    // MARK: - 活跃项目（带出现天数）

    private func projectsSection(_ summary: ReportSummary) -> some View {
        let items = projectAppearances(summary)
        return Group {
            if !viewModel.activeProjects.isEmpty {
                ReportSectionCard(title: "活跃项目", systemImage: "folder") {
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(items, id: \.title) { item in
                            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.sm) {
                                // 列表标记走灰阶，accent 留给图表柱子。
                                Circle()
                                    .fill(Theme.Palette.secondaryText)
                                    .frame(width: 6, height: 6)
                                    .padding(.top, 5)
                                Text(item.title)
                                    .font(Theme.Typography.body)
                                    .foregroundStyle(Theme.Palette.primaryText)
                                    .fixedSize(horizontal: false, vertical: true)
                                Spacer(minLength: Theme.Spacing.sm)
                                // 出现天数是元数据计数，统一中性徽章不染 accent。
                                if item.days > 0 {
                                    OMStatusBadge("出现 \(item.days) 天")
                                } else {
                                    OMStatusBadge("本窗口未出现")
                                }
                            }
                            .omRow(minHeight: 32)
                        }
                    }
                }
            }
        }
    }

    /// 在当前窗口内统计每个活跃项目出现的天数：项目标题作为子串在当天文本中命中即记一天。
    /// 窗口的天集合来自 `summary.perDay`（聚合器已筛过窗口），与 dates 对齐取文本。
    private func projectAppearances(_ summary: ReportSummary) -> [(title: String, days: Int)] {
        let windowDates = Set(summary.perDay.map { $0.date })
        let entries = dates.filter { windowDates.contains($0.date) }
        return viewModel.activeProjects.map { title in
            let needle = title.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !needle.isEmpty else { return (title: title, days: 0) }
            let days = entries.filter { entryMentions($0, needle: needle) }.count
            return (title: title, days: days)
        }
    }

    /// 某天文本（摘要/事件/决策/待办/时间线预览）是否提及给定关键词。
    private func entryMentions(_ entry: DayEntry, needle: String) -> Bool {
        if entry.summary.contains(needle) { return true }
        if entry.events.contains(where: { $0.contains(needle) }) { return true }
        if entry.decisions.contains(where: { $0.contains(needle) }) { return true }
        if entry.todos.contains(where: { $0.contains(needle) }) { return true }
        if entry.timeline.contains(where: { $0.preview.contains(needle) }) { return true }
        return false
    }

    // MARK: - 决策聚合

    private func decisionsSection(_ summary: ReportSummary) -> some View {
        Group {
            if !summary.decisions.isEmpty {
                ReportSectionCard(title: "决策", systemImage: "checkmark.seal") {
                    bullets(summary.decisions, marker: .dot)
                }
            }
        }
    }

    // MARK: - 待办聚合

    private func todosSection(_ summary: ReportSummary) -> some View {
        Group {
            if !summary.todos.isEmpty {
                ReportSectionCard(title: "待办", systemImage: "checklist") {
                    bullets(summary.todos, marker: .checkbox)
                }
            }
        }
    }

    // MARK: - 最长摘要

    private func topSummarySection(_ summary: ReportSummary) -> some View {
        Group {
            if !summary.topSummary.isEmpty {
                ReportSectionCard(title: "最长摘要", systemImage: "text.alignleft") {
                    Text(summary.topSummary)
                        .font(Theme.Typography.body)
                        .foregroundStyle(Theme.Palette.primaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    // MARK: - 空态 / 骨架

    /// 数据已就绪但窗口内无任何记录时的提示。
    /// 紧凑居中：小号中性图标 + 主文 + 三级说明，去掉大卡片与铺满留白。
    /// 注：规范建议附「处理录音」CTA，但本视图无对应回调，按硬约束不新增数据流，故省略。
    private var emptyHint: some View {
        VStack(spacing: Theme.Spacing.md) {
            Image(systemName: "tray")
                .font(.system(size: 20))
                .foregroundStyle(Theme.Palette.secondaryText)
            Text("\(window.label)内还没有记录")
                .font(Theme.Typography.cardTitle)
                .tracking(Theme.Tracking.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
        }
        .frame(maxWidth: 320)
        .frame(maxWidth: .infinity, alignment: .center)
        .padding(.vertical, Theme.Spacing.xxl)
    }

    /// 聚合尚未算出（viewModel 未 load）时的骨架提示。
    private var skeletonHint: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            ForEach(0..<3, id: \.self) { _ in
                // 占位用 muted 底（浅色也可见），高度收到 44。
                RoundedRectangle(cornerRadius: Theme.Radius.lg)
                    .fill(Theme.Palette.muted)
                    .frame(height: 44)
            }
            Text("正在汇总报告…")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.tertiaryText)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .omSection()
    }

    // MARK: - 列表项

    private enum BulletMarker {
        case dot
        case checkbox
    }

    private func bullets(_ items: [String], marker: BulletMarker) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(items, id: \.self) { item in
                HStack(alignment: .top, spacing: Theme.Spacing.sm) {
                    switch marker {
                    case .dot:
                        // 列表标记走灰阶，accent 留给图表柱子。
                        Circle()
                            .fill(Theme.Palette.secondaryText)
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
                .omRow(minHeight: 32)
            }
        }
    }
}

// MARK: - 窗口枚举

/// 报告窗口：周报（最近 7 天）/ 月报（最近 30 天）。
private enum ReportWindow: String, CaseIterable, Identifiable {
    case weekly
    case monthly

    var id: String { rawValue }

    var label: String {
        switch self {
        case .weekly: return "最近 7 天"
        case .monthly: return "最近 30 天"
        }
    }
}

// MARK: - 区块卡片容器

/// 区块卡片：中性图标 + 区块标题在上，内容收进统一描边卡片。
/// 标题对齐 `OMSectionHeader` 风格（15 semibold + 负字距），图标去 accent 走灰阶；
/// 内容用 `.omCard()`（card 底 + 1px border + Radius.lg），与全 app 卡片一致。
/// 此处独立私有避免跨文件耦合。
private struct ReportSectionCard<Content: View>: View {
    let title: String
    let systemImage: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: systemImage)
                    .font(.subheadline)
                    .foregroundStyle(Theme.Palette.secondaryText)
                Text(title)
                    .font(Theme.Typography.sectionTitle)
                    .tracking(Theme.Tracking.sectionTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
            }

            content()
                .frame(maxWidth: .infinity, alignment: .leading)
                .omCard()
        }
        .omSection()
    }
}

#if DEBUG
#Preview {
    let vm = ReportViewModel()
    let dates = [
        DayEntry(
            date: "2026-06-25", segments: 12, wordCount: 3200,
            summary: "和 OpenMy 团队对齐了报告页设计，决定先做周报。",
            decisions: ["先做周报再做月报"], todos: ["补充活跃项目出现天数"],
            events: ["设计评审"], timeline: [TimelineEntry(time: "09:00", preview: "晨会")]
        ),
        DayEntry(
            date: "2026-06-24", segments: 8, wordCount: 2100,
            summary: "梳理 OpenMy 报告聚合逻辑。",
            decisions: ["决策去重保序"], todos: [],
            events: [], timeline: []
        ),
        DayEntry(
            date: "2026-06-23", segments: 0, wordCount: 0, summary: ""
        )
    ]
    let projects = [
        Project(projectId: "p1", title: "OpenMy"),
        Project(projectId: "p2", title: "未出现项目")
    ]
    vm.load(dates: dates, activeProjects: projects, today: "2026-06-25")
    return ReportView(viewModel: vm, dates: dates, today: "2026-06-25")
        .frame(width: 640, height: 800)
}
#endif
