import SwiftUI
import OpenMyKit

/// 记忆库面板：以 `.sheet` 呈现，分三个分区（待办 / 项目 / 决策）+ 查询工作台。
///
/// 每条记忆带修整操作：
/// - 待办：「标记完成」（closeLoop）、「移除」（rejectLoop）
/// - 项目：「合并到…」（mergeProject，选另一项目作 target）、「移除」（rejectProject）
/// - 决策：「移除」（rejectDecision）
/// 修整与查询都走环境注入的共享 `ContextViewModel`，成功后用 `ToastCenter` 反馈、列表自动刷新。
///
/// 接入方式（由上层负责，本视图不改根 App）：
/// 与 `ToastCenter` 一样在 App 根 `.environment(contextVM)` 注入一份共享实例，
/// 本面板通过 `@Environment(ContextViewModel.self)` 取用。VM 修整成功后内部 `await load()` 自动刷新列表。
///
/// 查询工作台预设按钮一键 `runQuery`，结果按时态分桶（current/future/past/closed）展示；
/// 证据条目点了走 `onJumpToEvidence(vm.focus(for:))`，复用 MainView.handleSearchSelect 的证据回链。
///
/// 视觉对齐 Linear：三类条目用统一扁平行（去卡片化）+ 行间细分隔 + hover 行操作；
/// 元数据走三级灰阶，accent 仅留选中态，空状态克制。
struct ContextView: View {
    /// 共享上下文记忆状态机（修整 / 查询 / 证据回链都在这里）。
    @Environment(ContextViewModel.self) private var viewModel
    /// 全局 Toast 中心：修整成功 / 失败给反馈。
    @Environment(ToastCenter.self) private var toastCenter

    /// 关闭整个面板。
    var onClose: () -> Void
    /// 证据回链：把证据解析出的 SearchFocus 交给外层跳到对应日期段落。
    /// 外层（MainView）通常在跳转前先关掉本面板。
    var onJumpToEvidence: (SearchFocus) -> Void

    /// 「填写原因」弹层的待执行修整（nil 表示未弹）。
    @State private var pendingReason: PendingReasonAction?
    /// 「合并到…」目标选择弹层的源项目（nil 表示未弹）。
    @State private var mergingSource: Project?
    /// 查询工作台当前激活的预设（仅驱动按钮选中态高亮，不影响查询逻辑）。
    @State private var activePreset: QueryPreset?

    init(
        onClose: @escaping () -> Void = {},
        onJumpToEvidence: @escaping (SearchFocus) -> Void = { _ in }
    ) {
        self.onClose = onClose
        self.onJumpToEvidence = onJumpToEvidence
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            header
            OMErrorText(viewModel.errorMessage)

            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
                    memorySections
                    Divider().overlay(Theme.Palette.borderSubtle)
                    queryWorkbench
                }
                .padding(.bottom, Theme.Spacing.lg)
            }
        }
        .padding(Theme.Spacing.xl)
        // 弹性上限而非固定尺寸：让外层 sheet 的 ZStack 蒙层能撑满父窗口、本面板居中（issue #14）。
        .frame(maxWidth: 640, maxHeight: 680)
        // 面板实底卡片：对齐 SettingsView，避免透出外层蒙层灰底。
        .background(Theme.Palette.popover)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.xl))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.xl)
                .strokeBorder(Theme.Palette.border, lineWidth: 1)
        )
        .task { await viewModel.load() }
        .sheet(item: $pendingReason) { action in
            ReasonSheet(
                title: action.title,
                prompt: action.prompt,
                confirmLabel: action.confirmLabel,
                onConfirm: { reason in
                    pendingReason = nil
                    runReasonAction(action, reason: reason)
                },
                onCancel: { pendingReason = nil }
            )
        }
        .sheet(item: $mergingSource) { source in
            MergeTargetSheet(
                source: source,
                candidates: viewModel.projects.filter { $0.id != source.id },
                onConfirm: { target, reason in
                    mergingSource = nil
                    Task { await performMerge(source: source, target: target, reason: reason) }
                },
                onCancel: { mergingSource = nil }
            )
        }
    }

    // MARK: - 头部

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.sm) {
            Text("记忆库")
                .font(Theme.Typography.sectionTitle)
                .tracking(Theme.Tracking.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            OMStatusBadge(
                "\(viewModel.loops.count + viewModel.projects.count + viewModel.decisions.count) 条",
                status: .neutral
            )
            Spacer()
            Button("关闭", role: .cancel) { onClose() }
                .omButton(.ghost)
                .keyboardShortcut(.cancelAction)
        }
    }

    // MARK: - 三个记忆分区

    private var memorySections: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
            loopsSection
            projectsSection
            decisionsSection
        }
    }

    // MARK: 待办

    private var loopsSection: some View {
        sectionContainer(
            title: "待办",
            count: viewModel.loops.count
        ) {
            if !viewModel.loops.isEmpty {
                // 扁平行 + 行间 borderSubtle 细分隔，去掉卡片间距。
                VStack(spacing: 0) {
                    ForEach(Array(viewModel.loops.enumerated()), id: \.element.id) { index, loop in
                        if index > 0 {
                            Divider().overlay(Theme.Palette.borderSubtle)
                        }
                        loopRow(loop)
                    }
                }
            }
        }
    }

    private func loopRow(_ loop: Loop) -> some View {
        MemoryRow {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                HStack(spacing: Theme.Spacing.sm) {
                    Text(loop.title.isEmpty ? "（未命名待办）" : loop.title)
                        .font(Theme.Typography.cardTitle)
                        .tracking(Theme.Tracking.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    priorityBadge(loop.priority)
                }
                if !loop.waitingOn.isEmpty {
                    metaLine(icon: "hourglass", text: "等待：\(loop.waitingOn)")
                }
                if !loop.closeCondition.isEmpty {
                    metaLine(icon: "flag.checkered", text: "完成条件：\(loop.closeCondition)")
                }
            }
        } actions: {
            Button {
                Task { await performCloseLoop(loop) }
            } label: {
                Label("标记完成", systemImage: "checkmark.circle")
            }
            .omButton(.ghost, size: .small)

            Button(role: .destructive) {
                pendingReason = .rejectLoop(loop)
            } label: {
                Label("移除", systemImage: "trash")
            }
            .omButton(.ghostDanger, size: .small)
        }
    }

    // MARK: 项目

    private var projectsSection: some View {
        sectionContainer(
            title: "项目",
            count: viewModel.projects.count
        ) {
            if !viewModel.projects.isEmpty {
                VStack(spacing: 0) {
                    ForEach(Array(viewModel.projects.enumerated()), id: \.element.id) { index, project in
                        if index > 0 {
                            Divider().overlay(Theme.Palette.borderSubtle)
                        }
                        projectRow(project)
                    }
                }
            }
        }
    }

    private func projectRow(_ project: Project) -> some View {
        MemoryRow {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                HStack(spacing: Theme.Spacing.sm) {
                    Text(project.title.isEmpty ? "（未命名项目）" : project.title)
                        .font(Theme.Typography.cardTitle)
                        .tracking(Theme.Tracking.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    priorityBadge(project.priority)
                }
                if !project.currentGoal.isEmpty {
                    metaLine(icon: "target", text: project.currentGoal)
                }
            }
        } actions: {
            Button {
                mergingSource = project
            } label: {
                Label("合并到…", systemImage: "arrow.triangle.merge")
            }
            .omButton(.ghost, size: .small)
            // 只有一个项目时无处可并，禁用。
            .disabled(viewModel.projects.count < 2)

            Button(role: .destructive) {
                pendingReason = .rejectProject(project)
            } label: {
                Label("移除", systemImage: "trash")
            }
            .omButton(.ghostDanger, size: .small)
        }
    }

    // MARK: 决策

    private var decisionsSection: some View {
        sectionContainer(
            title: "决策",
            count: viewModel.decisions.count
        ) {
            if !viewModel.decisions.isEmpty {
                VStack(spacing: 0) {
                    ForEach(Array(viewModel.decisions.enumerated()), id: \.element.id) { index, decision in
                        if index > 0 {
                            Divider().overlay(Theme.Palette.borderSubtle)
                        }
                        decisionRow(decision)
                    }
                }
            }
        }
    }

    private func decisionRow(_ decision: Decision) -> some View {
        MemoryRow {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(decision.decision.isEmpty ? "（未记录内容）" : decision.decision)
                    .font(Theme.Typography.cardTitle)
                    .tracking(Theme.Tracking.cardTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
                if !decision.topic.isEmpty {
                    metaLine(icon: "text.bubble", text: "主题：\(decision.topic)")
                }
                if !decision.effectiveFrom.isEmpty {
                    metaLine(icon: "calendar", text: "生效：\(decision.effectiveFrom)")
                }
            }
        } actions: {
            Button(role: .destructive) {
                pendingReason = .rejectDecision(decision)
            } label: {
                Label("移除", systemImage: "trash")
            }
            .omButton(.ghostDanger, size: .small)
        }
    }

    // MARK: - 查询工作台

    private var queryWorkbench: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            OMSectionHeader("查询工作台") {
                if viewModel.isQuerying {
                    ProgressView().controlSize(.small)
                }
            }

            // 预设按钮：一键填 kind 并查询；当前激活项高亮（selectedSurface 底 + accent 文字）。
            HStack(spacing: Theme.Spacing.sm) {
                ForEach(QueryPreset.allCases) { preset in
                    presetButton(preset)
                }
            }

            queryResultView
        }
    }

    /// 预设查询按钮：激活态走 `selectedSurface` 底 + accent 文字，其余为 ghost。
    @ViewBuilder
    private func presetButton(_ preset: QueryPreset) -> some View {
        if activePreset == preset {
            Button {
                runPreset(preset)
            } label: {
                Text(preset.label)
                    .font(Theme.Typography.label)
                    .foregroundStyle(Theme.Palette.accent)
                    .frame(height: 26)
                    .padding(.horizontal, Theme.Spacing.sm)
                    .background(Theme.Palette.selectedSurface)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(viewModel.isQuerying)
        } else {
            Button {
                runPreset(preset)
            } label: {
                Text(preset.label)
            }
            .omButton(.ghost, size: .small)
            .disabled(viewModel.isQuerying)
        }
    }

    /// 记录激活预设并发起查询（激活态仅为视觉高亮，查询逻辑不变）。
    private func runPreset(_ preset: QueryPreset) {
        activePreset = preset
        Task { await viewModel.runQuery(kind: preset.kind, query: "") }
    }

    @ViewBuilder
    private var queryResultView: some View {
        if let result = viewModel.queryResult {
            VStack(alignment: .leading, spacing: Theme.Spacing.md) {
                if !result.summary.isEmpty {
                    Text(result.summary)
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                }

                let buckets = orderedBuckets(result.temporalBuckets)
                let hasHits = buckets.contains { !$0.hits.isEmpty }

                if hasHits {
                    ForEach(buckets, id: \.label) { bucket in
                        if !bucket.hits.isEmpty {
                            bucketView(bucket)
                        }
                    }
                } else {
                    queryEmptyState
                }

                if !result.evidence.isEmpty {
                    evidenceSection(result.evidence)
                }
            }
        }
    }

    private func bucketView(_ bucket: TemporalBucket) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            HStack(spacing: Theme.Spacing.sm) {
                OMGroupLabel(bucket.label)
                OMStatusBadge("\(bucket.hits.count)", status: .neutral)
            }
            VStack(spacing: 0) {
                ForEach(Array(bucket.hits.enumerated()), id: \.element.id) { index, hit in
                    if index > 0 {
                        Divider().overlay(Theme.Palette.borderSubtle)
                    }
                    hitRow(hit)
                }
            }
        }
    }

    private func hitRow(_ hit: ContextHit) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs / 2) {
            HStack(spacing: Theme.Spacing.sm) {
                Text(hit.title.isEmpty ? "（无标题）" : hit.title)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.primaryText)
                Spacer()
                if !hit.date.isEmpty {
                    Text(hit.date)
                        .font(Theme.Typography.caption2)
                        .foregroundStyle(Theme.Palette.tertiaryText)
                }
            }
            let detail = hit.currentState.isEmpty ? hit.summary : hit.currentState
            if !detail.isEmpty {
                Text(detail)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .lineLimit(2)
            }
        }
        .omRow(minHeight: 36)
    }

    private func evidenceSection(_ evidence: [ContextEvidence]) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            OMGroupLabel("证据")
            VStack(spacing: 0) {
                ForEach(Array(evidence.enumerated()), id: \.element.id) { index, item in
                    if index > 0 {
                        Divider().overlay(Theme.Palette.borderSubtle)
                    }
                    evidenceRow(item)
                }
            }
        }
    }

    private func evidenceRow(_ item: ContextEvidence) -> some View {
        Button {
            onJumpToEvidence(viewModel.focus(for: item))
        } label: {
            HStack(alignment: .top, spacing: Theme.Spacing.sm) {
                Image(systemName: "quote.opening")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                VStack(alignment: .leading, spacing: Theme.Spacing.xs / 2) {
                    Text(item.quote.isEmpty ? item.sceneSummary : item.quote)
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.primaryText)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)
                    HStack(spacing: Theme.Spacing.xs) {
                        if !item.date.isEmpty {
                            Text(item.date)
                        }
                        if !item.timeRange.isEmpty {
                            Text(item.timeRange)
                        }
                    }
                    .font(Theme.Typography.caption2)
                    .foregroundStyle(Theme.Palette.tertiaryText)
                }
                Spacer()
                Image(systemName: "arrow.up.right.square")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
            }
            .omRow(minHeight: 36)
        }
        .buttonStyle(.plain)
    }

    private var queryEmptyState: some View {
        Text("这一类暂时没有命中。")
            .font(Theme.Typography.caption)
            .foregroundStyle(Theme.Palette.tertiaryText)
            .padding(.vertical, Theme.Spacing.sm)
    }

    // MARK: - 复用片段

    /// 分区容器：分组标签 + 计数徽章 + 内容；为空时给克制的空状态。
    @ViewBuilder
    private func sectionContainer<Content: View>(
        title: String,
        count: Int,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            HStack(spacing: Theme.Spacing.sm) {
                OMGroupLabel(title)
                OMStatusBadge("\(count)", status: .neutral)
            }
            if count > 0 {
                content()
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func metaLine(icon: String, text: String) -> some View {
        HStack(spacing: Theme.Spacing.xs) {
            Image(systemName: icon)
                .font(Theme.Typography.caption2)
                .foregroundStyle(Theme.Palette.tertiaryText)
            Text(text)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.tertiaryText)
                .lineLimit(2)
        }
    }

    @ViewBuilder
    private func priorityBadge(_ priority: String) -> some View {
        if !priority.isEmpty {
            OMStatusBadge(priorityLabel(priority), status: priorityStatus(priority))
        }
    }

    private func priorityLabel(_ priority: String) -> String {
        switch priority {
        case "high": return "高"
        case "medium": return "中"
        case "low": return "低"
        default: return priority
        }
    }

    /// 优先级映射到低饱和语义状态：高→危险、中→警告、低→中性。
    private func priorityStatus(_ priority: String) -> OMStatusBadge.Status {
        switch priority {
        case "high": return .danger
        case "medium": return .warning
        case "low": return .neutral
        default: return .neutral
        }
    }

    // MARK: - 动作执行

    private func performCloseLoop(_ loop: Loop) async {
        let ok = await viewModel.closeLoop(query: loop.title)
        toastCenter.show(ok ? "已标记完成" : "操作失败：\(viewModel.errorMessage ?? "未知原因")")
    }

    private func performMerge(source: Project, target: Project, reason: String) async {
        let ok = await viewModel.mergeProject(source: source.title, target: target.title, reason: reason)
        toastCenter.show(ok ? "已合并到「\(target.title)」" : "合并失败：\(viewModel.errorMessage ?? "未知原因")")
    }

    /// 执行「填原因」类修整（移除待办 / 项目 / 决策）。
    private func runReasonAction(_ action: PendingReasonAction, reason: String) {
        Task {
            let ok: Bool
            let successText: String
            switch action {
            case .rejectLoop(let loop):
                ok = await viewModel.rejectLoop(query: loop.title, reason: reason)
                successText = "已移除待办"
            case .rejectProject(let project):
                ok = await viewModel.rejectProject(query: project.title, reason: reason)
                successText = "已移除项目"
            case .rejectDecision(let decision):
                ok = await viewModel.rejectDecision(query: decision.decision, reason: reason)
                successText = "已移除决策"
            }
            toastCenter.show(ok ? successText : "操作失败：\(viewModel.errorMessage ?? "未知原因")")
        }
    }

    // MARK: - 时态分桶呈现顺序

    private func orderedBuckets(_ buckets: TemporalBuckets) -> [TemporalBucket] {
        [
            TemporalBucket(label: "进行中", hits: buckets.current),
            TemporalBucket(label: "未来", hits: buckets.future),
            TemporalBucket(label: "过去", hits: buckets.past),
            TemporalBucket(label: "已关闭", hits: buckets.closed),
        ]
    }
}

// MARK: - 内部辅助类型

/// 记忆条目行容器：左侧主内容铺满，右侧行操作仅在指针悬停时淡入。
/// 仅承载视觉 hover 态（本地 @State），动作逻辑由调用方通过 `actions` 槽注入，不改数据流。
/// 静止行只显标题 + 元信息；hover 才显形「标记完成 / 移除 / 合并」等操作（对齐 Linear 行密度）。
private struct MemoryRow<Leading: View, Actions: View>: View {
    private let minHeight: CGFloat
    private let leading: Leading
    private let actions: Actions
    @State private var hovering = false

    init(
        minHeight: CGFloat = 36,
        @ViewBuilder leading: () -> Leading,
        @ViewBuilder actions: () -> Actions
    ) {
        self.minHeight = minHeight
        self.leading = leading()
        self.actions = actions()
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.sm) {
            leading
                .frame(maxWidth: .infinity, alignment: .leading)
            HStack(spacing: Theme.Spacing.xs) {
                actions
            }
            // hover 才显形：淡入并放开点击，静止时隐藏且不拦截命中。
            .opacity(hovering ? 1 : 0)
            .allowsHitTesting(hovering)
        }
        .omRow(minHeight: minHeight)
        .onHover { hovering = $0 }
        .animation(.easeOut(duration: 0.12), value: hovering)
    }
}

/// 时态桶的呈现单元：标签 + 命中数组。
private struct TemporalBucket {
    let label: String
    let hits: [ContextHit]
}

/// 查询预设：按钮文案 + 对应 kind。
private enum QueryPreset: String, CaseIterable, Identifiable {
    case project
    case open
    case closed
    case evidence

    var id: String { rawValue }

    var label: String {
        switch self {
        case .project: return "查项目"
        case .open: return "查未关闭待办"
        case .closed: return "查已关闭"
        case .evidence: return "查证据"
        }
    }

    var kind: ContextQueryKind {
        switch self {
        case .project: return .project
        case .open: return .open
        case .closed: return .closed
        case .evidence: return .evidence
        }
    }
}

/// 待填原因的修整动作（移除三类条目）。用 `.sheet(item:)` 承载，故需 Identifiable。
private enum PendingReasonAction: Identifiable {
    case rejectLoop(Loop)
    case rejectProject(Project)
    case rejectDecision(Decision)

    var id: String {
        switch self {
        case .rejectLoop(let loop): return "loop|\(loop.id)"
        case .rejectProject(let project): return "project|\(project.id)"
        case .rejectDecision(let decision): return "decision|\(decision.id)"
        }
    }

    var title: String {
        switch self {
        case .rejectLoop: return "移除待办"
        case .rejectProject: return "移除项目"
        case .rejectDecision: return "移除决策"
        }
    }

    var prompt: String {
        switch self {
        case .rejectLoop(let loop): return loop.title
        case .rejectProject(let project): return project.title
        case .rejectDecision(let decision): return decision.decision
        }
    }

    var confirmLabel: String { "移除" }
}

/// 填原因弹层：可选输入一句原因，留空也能确认。
private struct ReasonSheet: View {
    let title: String
    let prompt: String
    let confirmLabel: String
    let onConfirm: (String) -> Void
    let onCancel: () -> Void

    @State private var reason = ""

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            Text(title)
                .font(Theme.Typography.sectionTitle)
                .tracking(Theme.Tracking.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            if !prompt.isEmpty {
                Text(prompt)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .lineLimit(3)
            }

            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text("原因（可选）")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.tertiaryText)
                OMTextField("不填也可以直接确认", text: $reason)
            }

            HStack {
                Spacer()
                Button("取消", role: .cancel) { onCancel() }
                    .omButton(.secondary)
                    .keyboardShortcut(.cancelAction)
                Button(confirmLabel, role: .destructive) {
                    onConfirm(reason.trimmingCharacters(in: .whitespacesAndNewlines))
                }
                .omButton(.destructive)
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(Theme.Spacing.xl)
        .frame(width: 420)
    }
}

/// 合并目标选择弹层：从其余项目里选一个作 target，可选填原因。
private struct MergeTargetSheet: View {
    let source: Project
    let candidates: [Project]
    let onConfirm: (Project, String) -> Void
    let onCancel: () -> Void

    @State private var selectedId: String?
    @State private var reason = ""

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            Text("合并项目")
                .font(Theme.Typography.sectionTitle)
                .tracking(Theme.Tracking.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            Text("把「\(source.title)」合并到下面选中的项目，原项目会并入对方。")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)

            if candidates.isEmpty {
                Text("没有其他项目可供合并。")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.tertiaryText)
            } else {
                ScrollView {
                    VStack(spacing: 0) {
                        ForEach(candidates) { project in
                            candidateRow(project)
                        }
                    }
                }
                .frame(maxHeight: 220)

                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text("原因（可选）")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.tertiaryText)
                    OMTextField("不填也可以直接确认", text: $reason)
                }
            }

            HStack {
                Spacer()
                Button("取消", role: .cancel) { onCancel() }
                    .omButton(.secondary)
                    .keyboardShortcut(.cancelAction)
                Button("合并") {
                    guard let target = candidates.first(where: { $0.id == selectedId }) else { return }
                    onConfirm(target, reason.trimmingCharacters(in: .whitespacesAndNewlines))
                }
                .omButton(.primary)
                .disabled(selectedId == nil)
            }
        }
        .padding(Theme.Spacing.xl)
        .frame(width: 440)
    }

    private func candidateRow(_ project: Project) -> some View {
        Button {
            selectedId = project.id
        } label: {
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: selectedId == project.id ? "largecircle.fill.circle" : "circle")
                    .foregroundStyle(selectedId == project.id ? Theme.Palette.accent : Theme.Palette.secondaryText)
                VStack(alignment: .leading, spacing: Theme.Spacing.xs / 2) {
                    Text(project.title.isEmpty ? "（未命名项目）" : project.title)
                        .font(Theme.Typography.body)
                        .foregroundStyle(Theme.Palette.primaryText)
                    if !project.currentGoal.isEmpty {
                        Text(project.currentGoal)
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Palette.secondaryText)
                            .lineLimit(1)
                    }
                }
                Spacer()
            }
            .omRow(isSelected: selectedId == project.id, minHeight: 40)
        }
        .buttonStyle(.plain)
    }
}

#if DEBUG
// 预览用真实 VM，未连后端时 load() 失败 -> 三类列表为空，呈现空状态与查询工作台占位。
#Preview {
    ContextView()
        .environment(ContextViewModel(client: APIClient()))
        .environment(ToastCenter(autoDismissSeconds: 0))
}
#endif
