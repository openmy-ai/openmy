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
            VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
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
            .padding(Theme.Spacing.xxl)
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
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            Text("报告")
                .font(Theme.Typography.pageTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            Picker("窗口", selection: $window) {
                ForEach(ReportWindow.allCases) { w in
                    Text(w.label).tag(w)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(maxWidth: 320)
        }
        .omSection()
    }

    // MARK: - 统计卡

    private func metricCards(_ summary: ReportSummary) -> some View {
        HStack(spacing: Theme.Spacing.md) {
            metricCard("\(summary.activeDays)", "活跃天数")
            metricCard("\(summary.totalSegments)", "录音段数")
            metricCard("\(summary.totalWords)", "总字数")
        }
        .omSection()
    }

    private func metricCard(_ value: String, _ label: String) -> some View {
        OMMetric(value: value, label: label)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.md)
            .omCard()
    }

    // MARK: - 每日活跃度柱状图

    private func dailyActivitySection(_ summary: ReportSummary) -> some View {
        ReportSectionCard(title: "每日活跃度", systemImage: "chart.bar") {
            if summary.perDay.isEmpty {
                Text("窗口内还没有记录")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
            } else {
                Chart(summary.perDay, id: \.date) { day in
                    BarMark(
                        x: .value("日期", shortLabel(day.date)),
                        y: .value("段数", day.segments)
                    )
                    .foregroundStyle(Theme.Palette.accent)
                    .cornerRadius(Theme.Radius.card / 2)
                }
                .chartXAxis {
                    AxisMarks(values: .automatic) { _ in
                        AxisValueLabel()
                            .font(Theme.Typography.caption)
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading)
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
                    .foregroundStyle(Theme.Palette.secondaryText)
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
                    VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                        ForEach(items, id: \.title) { item in
                            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.sm) {
                                Circle()
                                    .fill(Theme.Palette.accent)
                                    .frame(width: 6, height: 6)
                                    .padding(.top, 5)
                                Text(item.title)
                                    .font(Theme.Typography.body)
                                    .foregroundStyle(Theme.Palette.primaryText)
                                    .fixedSize(horizontal: false, vertical: true)
                                Spacer(minLength: Theme.Spacing.sm)
                                if item.days > 0 {
                                    OMBadge("出现 \(item.days) 天", kind: .accent)
                                } else {
                                    OMBadge("本窗口未出现", kind: .neutral)
                                }
                            }
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
    private var emptyHint: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            Image(systemName: "tray")
                .font(.title)
                .foregroundStyle(Theme.Palette.secondaryText)
            Text("\(window.label)内还没有记录")
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Text("处理更多录音后，这里会显示活跃度、决策与待办的汇总。")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.lg)
        .omCard()
        .omSection()
    }

    /// 聚合尚未算出（viewModel 未 load）时的骨架提示。
    private var skeletonHint: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            ForEach(0..<3, id: \.self) { _ in
                RoundedRectangle(cornerRadius: Theme.Radius.card)
                    .fill(Theme.Palette.cardBackground)
                    .frame(height: 56)
            }
            Text("正在汇总报告…")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
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

/// 带强调色标题条的区块卡片：图标 + 标题在上，内容在卡片内。
/// 与 BriefingDetailView 的 SectionCard 同款样式，此处独立私有避免跨文件耦合。
private struct ReportSectionCard<Content: View>: View {
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
