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
                    Divider()
                    queryWorkbench
                }
                .padding(.bottom, Theme.Spacing.lg)
            }
        }
        .padding(Theme.Spacing.xl)
        // 弹性上限而非固定尺寸：让外层 sheet 的 ZStack 蒙层能撑满父窗口、本面板居中（issue #14）。
        .frame(maxWidth: 640, maxHeight: 680)
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
                .foregroundStyle(Theme.Palette.primaryText)
            OMBadge("\(viewModel.loops.count + viewModel.projects.count + viewModel.decisions.count) 条")
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
            systemImage: "checklist",
            count: viewModel.loops.count,
            emptyHint: "暂无未关闭的待办。处理录音后，对话里的待办事项会自动收集到这里。"
        ) {
            if !viewModel.loops.isEmpty {
                VStack(spacing: Theme.Spacing.sm) {
                    ForEach(viewModel.loops) { loop in
                        loopRow(loop)
                    }
                }
            }
        }
    }

    private func loopRow(_ loop: Loop) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            HStack(spacing: Theme.Spacing.sm) {
                Text(loop.title.isEmpty ? "（未命名待办）" : loop.title)
                    .font(Theme.Typography.cardTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
                priorityBadge(loop.priority)
                Spacer()
            }
            if !loop.waitingOn.isEmpty {
                metaLine(icon: "hourglass", text: "等待：\(loop.waitingOn)")
            }
            if !loop.closeCondition.isEmpty {
                metaLine(icon: "flag.checkered", text: "完成条件：\(loop.closeCondition)")
            }
            HStack(spacing: Theme.Spacing.sm) {
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
            .font(Theme.Typography.caption)
            .padding(.top, Theme.Spacing.xs / 2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .omCard()
    }

    // MARK: 项目

    private var projectsSection: some View {
        sectionContainer(
            title: "项目",
            systemImage: "folder",
            count: viewModel.projects.count,
            emptyHint: "暂无活跃项目。多次提到的事会被归拢成项目，出现在这里。"
        ) {
            if !viewModel.projects.isEmpty {
                VStack(spacing: Theme.Spacing.sm) {
                    ForEach(viewModel.projects) { project in
                        projectRow(project)
                    }
                }
            }
        }
    }

    private func projectRow(_ project: Project) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            HStack(spacing: Theme.Spacing.sm) {
                Text(project.title.isEmpty ? "（未命名项目）" : project.title)
                    .font(Theme.Typography.cardTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
                priorityBadge(project.priority)
                Spacer()
            }
            if !project.currentGoal.isEmpty {
                metaLine(icon: "target", text: project.currentGoal)
            }
            HStack(spacing: Theme.Spacing.sm) {
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
            .font(Theme.Typography.caption)
            .padding(.top, Theme.Spacing.xs / 2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .omCard()
    }

    // MARK: 决策

    private var decisionsSection: some View {
        sectionContainer(
            title: "决策",
            systemImage: "gavel",
            count: viewModel.decisions.count,
            emptyHint: "暂无近期决策。明确拍板的事会记录在这里，附带证据出处。"
        ) {
            if !viewModel.decisions.isEmpty {
                VStack(spacing: Theme.Spacing.sm) {
                    ForEach(viewModel.decisions) { decision in
                        decisionRow(decision)
                    }
                }
            }
        }
    }

    private func decisionRow(_ decision: Decision) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(decision.decision.isEmpty ? "（未记录内容）" : decision.decision)
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            if !decision.topic.isEmpty {
                metaLine(icon: "text.bubble", text: "主题：\(decision.topic)")
            }
            if !decision.effectiveFrom.isEmpty {
                metaLine(icon: "calendar", text: "生效：\(decision.effectiveFrom)")
            }
            HStack(spacing: Theme.Spacing.sm) {
                Button(role: .destructive) {
                    pendingReason = .rejectDecision(decision)
                } label: {
                    Label("移除", systemImage: "trash")
                }
                .omButton(.ghostDanger, size: .small)
            }
            .font(Theme.Typography.caption)
            .padding(.top, Theme.Spacing.xs / 2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .omCard()
    }

    // MARK: - 查询工作台

    private var queryWorkbench: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: "magnifyingglass.circle")
                    .foregroundStyle(Theme.Palette.accent)
                Text("查询工作台")
                    .font(Theme.Typography.cardTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
                Spacer()
                if viewModel.isQuerying {
                    ProgressView().controlSize(.small)
                }
            }

            // 预设按钮：一键填 kind 并查询。
            HStack(spacing: Theme.Spacing.sm) {
                ForEach(QueryPreset.allCases) { preset in
                    Button {
                        Task { await viewModel.runQuery(kind: preset.kind, query: "") }
                    } label: {
                        Text(preset.label)
                    }
                    .omButton(.outline, size: .small)
                    .disabled(viewModel.isQuerying)
                }
            }

            queryResultView
        }
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
        } else if !viewModel.isQuerying {
            Text("点上面的预设查一类记忆，结果会按时间段分组列在这里。")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
        }
    }

    private func bucketView(_ bucket: TemporalBucket) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            HStack(spacing: Theme.Spacing.xs) {
                Text(bucket.label)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                OMBadge("\(bucket.hits.count)")
            }
            ForEach(bucket.hits) { hit in
                hitRow(hit)
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
                        .foregroundStyle(Theme.Palette.secondaryText)
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
        .frame(maxWidth: .infinity, alignment: .leading)
        .omCard()
    }

    private func evidenceSection(_ evidence: [ContextEvidence]) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text("证据")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
            ForEach(evidence) { item in
                evidenceRow(item)
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
                    .foregroundStyle(Theme.Palette.accent)
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
                    .foregroundStyle(Theme.Palette.secondaryText)
                }
                Spacer()
                Image(systemName: "arrow.up.right.square")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .omCard()
        }
        .buttonStyle(.plain)
    }

    private var queryEmptyState: some View {
        Text("这一类暂时没有命中。")
            .font(Theme.Typography.caption)
            .foregroundStyle(Theme.Palette.secondaryText)
            .padding(.vertical, Theme.Spacing.sm)
    }

    // MARK: - 复用片段

    /// 分区容器：标题 + 计数徽章 + 内容；为空时给友好空状态。
    @ViewBuilder
    private func sectionContainer<Content: View>(
        title: String,
        systemImage: String,
        count: Int,
        emptyHint: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: systemImage)
                    .foregroundStyle(Theme.Palette.accent)
                Text(title)
                    .font(Theme.Typography.cardTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
                OMBadge("\(count)")
                Spacer()
            }
            if count == 0 {
                Text(emptyHint)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, Theme.Spacing.sm)
            } else {
                content()
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func metaLine(icon: String, text: String) -> some View {
        HStack(spacing: Theme.Spacing.xs) {
            Image(systemName: icon)
                .font(Theme.Typography.caption2)
                .foregroundStyle(Theme.Palette.secondaryText)
            Text(text)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
                .lineLimit(2)
        }
    }

    @ViewBuilder
    private func priorityBadge(_ priority: String) -> some View {
        if !priority.isEmpty {
            OMBadge(priorityLabel(priority), kind: priority == "high" ? .accent : .neutral)
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
                    .foregroundStyle(Theme.Palette.secondaryText)
                TextField("不填也可以直接确认", text: $reason)
                    .textFieldStyle(.roundedBorder)
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
                .foregroundStyle(Theme.Palette.primaryText)

            Text("把「\(source.title)」合并到下面选中的项目，原项目会并入对方。")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)

            if candidates.isEmpty {
                Text("没有其他项目可供合并。")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
            } else {
                ScrollView {
                    VStack(spacing: Theme.Spacing.xs) {
                        ForEach(candidates) { project in
                            candidateRow(project)
                        }
                    }
                }
                .frame(maxHeight: 220)

                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text("原因（可选）")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                    TextField("不填也可以直接确认", text: $reason)
                        .textFieldStyle(.roundedBorder)
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
            .frame(maxWidth: .infinity, alignment: .leading)
            .omCard()
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
