import SwiftUI
import OpenMyKit
import UniformTypeIdentifiers

/// 主界面：左侧日期列表（可搜索 + 当前引擎 + 重新配置），右侧日报 / 进行中的任务进度。
/// 开始新任务有两条路：工具栏「处理录音」按钮（文件选择器）或直接把文件拖进详情区。
struct MainView: View {
    let client: APIClient
    /// 回到首次配置（重新选引擎）。
    var onReconfigure: () -> Void

    /// 全局 Toast 中心：建任务 / 失败 / 完成时给反馈，对齐 Web 的 showToast。
    @Environment(ToastCenter.self) private var toastCenter

    @State private var briefings: BriefingListViewModel
    @State private var job: JobViewModel
    /// 全局搜索状态机：检索逻辑、防过期、选中序号都在这里，SpotlightView 只负责呈现。
    @State private var searchVM: SearchViewModel
    /// 校正词典状态机：侧栏词典面板、划选纠错、新增校正共读同一份 corrections。
    /// 像 ToastCenter 一样在 NavigationSplitView 上 .environment 注入，详情区与纠错弹层都能读到。
    @State private var correctionsVM: CorrectionsViewModel
    @State private var isDropTargeted = false
    @State private var dropNote: String?
    @State private var search = ""
    @State private var showImporter = false
    @State private var currentEngine: String?
    /// 上一帧是否已是终态：用于在任务进入终态的那一刻只触发一次完成 / 失败的 toast 与跳转。
    @State private var lastJobTerminal = false
    /// ⌘K 全局搜索浮层是否呈现。
    @State private var showSpotlight = false
    /// 搜索命中后的跳转焦点，透传给 BriefingDetailView 做段内定位 + 关键词高亮。
    @State private var searchFocus: SearchFocus?
    /// 全局统计（天 / 条 / 字），启动时拉取，展示在侧栏底部。
    @State private var stats: Stats?
    /// 「校正词典」面板是否呈现。
    @State private var showCorrections = false

    init(client: APIClient, onReconfigure: @escaping () -> Void = {}) {
        self.client = client
        self.onReconfigure = onReconfigure
        _briefings = State(initialValue: BriefingListViewModel(client: client))
        _job = State(initialValue: JobViewModel(client: client))
        _searchVM = State(initialValue: SearchViewModel(client: client))
        _correctionsVM = State(initialValue: CorrectionsViewModel(client: client))
    }

    /// 按搜索词过滤日期（匹配日期或摘要）。
    private var visibleDates: [DayEntry] {
        let q = search.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return briefings.dates }
        return briefings.dates.filter { $0.date.contains(q) || $0.summary.contains(q) }
    }

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            detail
        }
        // 校正词典共享给详情区（划选纠错）与「校正词典」面板，同一份 corrections。
        .environment(correctionsVM)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showSpotlight = true
                } label: {
                    Label("搜索", systemImage: "magnifyingglass")
                }
                .help("全局搜索（⌘K）")
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showCorrections = true
                } label: {
                    Label("校正词典", systemImage: "character.book.closed")
                }
                .help("查看校正词典并新增校正")
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showImporter = true
                } label: {
                    Label("处理录音", systemImage: "waveform.badge.plus")
                }
                .help("选择录音文件开始转写")
            }
        }
        // ⌘K 打开全局搜索浮层。用隐藏按钮承载快捷键，避免与可见控件状态耦合。
        .background {
            Button("") { showSpotlight = true }
                .keyboardShortcut("k", modifiers: .command)
                .hidden()
        }
        .sheet(isPresented: $showSpotlight) {
            SpotlightView(
                viewModel: searchVM,
                onSelect: { focus in handleSearchSelect(focus) },
                onClose: { showSpotlight = false },
                recentDates: briefings.dates
            )
        }
        .sheet(isPresented: $showCorrections) {
            // 词典面板从环境里取 correctionsVM 与 toastCenter（上面 .environment 已注入）。
            // 自身负责提交成功的 toast；当天日报的重载在面板关闭时按当前日期触发（对齐 Web loadDate）。
            CorrectionsView(
                currentDate: briefings.selectedDate,
                onClose: { reloadAfterCorrections() }
            )
        }
        .fileImporter(
            isPresented: $showImporter,
            allowedContentTypes: [.audio, .movie, .mpeg4Movie],
            allowsMultipleSelection: true
        ) { result in
            if case .success(let urls) = result { startJob(with: urls) }
        }
        .task {
            await briefings.loadDates()
            await loadCurrentEngine()
            await loadStats()
            await correctionsVM.load()
        }
    }

    // MARK: - 侧栏

    private var sidebar: some View {
        List(selection: Binding(
            get: { briefings.selectedDate },
            set: { if let d = $0 { Task { await briefings.select(date: d) } } }
        )) {
            Section {
                if briefings.dates.isEmpty {
                    Text("还没有日报")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                        .padding(.vertical, Theme.Spacing.xs)
                } else if visibleDates.isEmpty {
                    Text("没有匹配「\(search)」的日报")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                        .padding(.vertical, Theme.Spacing.xs)
                } else {
                    ForEach(visibleDates) { entry in
                        sidebarRow(entry).tag(entry.date)
                    }
                }
            } header: {
                Text("日报")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
            }
        }
        .searchable(text: $search, placement: .sidebar, prompt: "搜索日期或内容")
        .frame(minWidth: 240)
        .safeAreaInset(edge: .bottom) { sidebarFooter }
    }

    /// 侧栏底部：当前引擎 + 重新配置入口。
    private var sidebarFooter: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            OMErrorText(briefings.errorMessage)
            if let stats {
                statsOverview(stats)
            }
            Divider()
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: "cpu")
                    .font(.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                VStack(alignment: .leading, spacing: 0) {
                    Text("当前引擎").font(.caption2).foregroundStyle(Theme.Palette.secondaryText)
                    Text(currentEngine ?? "未配置")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.primaryText)
                        .lineLimit(1)
                }
                Spacer()
                Button("重新配置", action: onReconfigure)
                    .buttonStyle(.borderless)
                    .font(.caption)
            }
        }
        .padding(.horizontal, Theme.Spacing.lg)
        .padding(.bottom, Theme.Spacing.sm)
    }

    /// 侧栏底部统计概览：天 / 条 / 字三项紧凑展示。
    private func statsOverview(_ stats: Stats) -> some View {
        HStack(spacing: Theme.Spacing.md) {
            statsItem(value: "\(stats.totalDates)", label: "天")
            statsItem(value: "\(stats.totalSegments)", label: "条")
            statsItem(value: "\(stats.totalWords)", label: "字")
        }
        .frame(maxWidth: .infinity)
    }

    private func statsItem(value: String, label: String) -> some View {
        VStack(spacing: 0) {
            Text(value)
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Text(label)
                .font(.caption2)
                .foregroundStyle(Theme.Palette.secondaryText)
        }
        .frame(maxWidth: .infinity)
    }

    private func sidebarRow(_ entry: DayEntry) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs / 2) {
            Text(entry.date)
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Text(entry.summary.isEmpty
                 ? "\(entry.segments) 段 · \(entry.wordCount) 字"
                 : entry.summary)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
                .lineLimit(1)
        }
        .padding(.vertical, Theme.Spacing.xs / 2)
    }

    // MARK: - 详情区

    @ViewBuilder
    private var detail: some View {
        ZStack {
            if job.job != nil {
                ProgressPanelView(job: job, onDismiss: viewBriefingFromJob, onReconfigure: onReconfigure)
            } else if let briefing = briefings.selectedBriefing {
                // 仅当焦点日期与当前日报一致时透传，避免切换日期后旧焦点串到别的日报。
                BriefingDetailView(
                    briefing: briefing,
                    client: client,
                    focus: searchFocus?.date == briefing.date ? searchFocus : nil,
                    onCorrectionApplied: reloadAfterCorrections
                )
            } else {
                dropPrompt
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .dropDestination(for: URL.self) { urls, _ in
            startJob(with: urls)
            return true
        } isTargeted: { isDropTargeted = $0 }
        .overlay { dropHighlight }
        .onChange(of: job.job?.status) { _, _ in handleJobStatusChange() }
    }

    /// 拖拽悬停时的高亮边框 + 蒙层。
    @ViewBuilder
    private var dropHighlight: some View {
        if isDropTargeted {
            RoundedRectangle(cornerRadius: Theme.Radius.container)
                .fill(Theme.Palette.accent.opacity(0.06))
                .overlay {
                    RoundedRectangle(cornerRadius: Theme.Radius.container)
                        .strokeBorder(
                            Theme.Palette.accent,
                            style: StrokeStyle(lineWidth: 2, dash: [8])
                        )
                }
                .padding(Theme.Spacing.sm)
                .allowsHitTesting(false)
                .transition(.opacity)
        }
    }

    /// 空状态：引导拖入录音或用按钮选择。
    private var dropPrompt: some View {
        VStack(spacing: Theme.Spacing.lg) {
            ZStack {
                Circle()
                    .fill(Theme.Palette.accent.opacity(0.12))
                    .frame(width: 96, height: 96)
                Image(systemName: "square.and.arrow.down.on.square")
                    .font(.system(size: 40, weight: .light))
                    .foregroundStyle(Theme.Palette.accent)
            }

            VStack(spacing: Theme.Spacing.xs) {
                Text("把录音拖到这里")
                    .font(Theme.Typography.sectionTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
                Text("自动转写、整理成当天的日报")
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.secondaryText)
            }

            Button {
                showImporter = true
            } label: {
                Label("选择录音文件", systemImage: "folder")
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(job.isUploading)

            if job.isUploading {
                HStack(spacing: Theme.Spacing.sm) {
                    ProgressView().controlSize(.small)
                    Text("正在上传…")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                }
            }

            if let note = dropNote {
                Text(note)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.warning)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Spacing.md)
                    .padding(.vertical, Theme.Spacing.sm)
                    .background(Theme.Palette.warning.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.card))
            }

            OMErrorText(briefings.errorMessage)
        }
        .padding(Theme.Spacing.xxl)
    }

    // MARK: - 动作

    private func startJob(with urls: [URL]) {
        // 过滤受支持的格式，并对云端引擎设 5 个批量上限（见 CLAUDE.md 云端批量限制）。
        // 注意：过滤按路径判断格式，真正建任务走上传流程（job.start(uploading:)），
        // 让外置盘 / 任意位置的文件都先 copy 到后端 inbox 再处理（对齐 Web upload.py）。
        let result = AudioFileFilter.evaluate(urls.map(\.path), maxBatch: 5)
        dropNote = result.note
        guard !result.isEmpty else { return }
        // 用保留下来的合法路径回到 URL，交给上传流程。
        let validURLs = urls.filter { result.paths.contains($0.path) }
        guard !validURLs.isEmpty else { return }

        lastJobTerminal = false
        toastCenter.show("正在上传 \(validURLs.count) 个文件…")
        Task {
            await job.start(uploading: validURLs)
            if let error = job.errorMessage {
                toastCenter.show("建任务失败：\(error)")
                return
            }
            toastCenter.show("开始处理")
            job.startPolling()
        }
    }

    /// 任务状态每次变化时检查是否刚进入终态，只在边沿触发一次完成 / 失败反馈。
    private func handleJobStatusChange() {
        let nowTerminal = job.job?.isTerminal == true
        defer { lastJobTerminal = nowTerminal }
        guard nowTerminal, !lastJobTerminal, let finished = job.job else { return }

        switch finished.status {
        case "succeeded", "partial":
            let dateText = finished.targetDate.map { "（\($0)）" } ?? ""
            toastCenter.show("处理完成\(dateText)")
        default:
            let detail = finished.error.isEmpty ? "" : "：\(finished.error)"
            toastCenter.show("处理未完成\(detail)")
        }
    }

    /// 进度面板「查看日报」：成功则跳到任务的 target_date 日报，否则仅回到浏览。
    private func viewBriefingFromJob() {
        let targetDate = job.job?.targetDate
        let succeeded = job.job.map { ["succeeded", "partial"].contains($0.status) } ?? false
        job.clear()
        lastJobTerminal = false
        Task {
            await briefings.loadDates()
            if succeeded, let date = targetDate {
                await briefings.select(date: date)
            }
        }
    }

    /// 关闭校正词典面板后：重载当前日期的日报（对齐 Web 提交后 loadDate）。
    /// 面板内提交时后端已就地替换当天 transcript，关闭时重拉让详情区即时反映替换结果。
    /// 词典面板自身已弹提交成功 toast，这里只负责重载，不重复反馈。
    private func reloadAfterCorrections() {
        showCorrections = false
        if let date = briefings.selectedDate {
            Task { await briefings.select(date: date) }
        }
    }

    /// 搜索命中后：切到目标日期、记下焦点供详情区定位 + 高亮、关闭浮层。
    private func handleSearchSelect(_ focus: SearchFocus) {
        searchFocus = focus
        showSpotlight = false
        // 命中可能落在尚未处理过任务的旧日期；正在进行的任务面板会盖住详情，先不强切。
        Task { await briefings.select(date: focus.date) }
    }

    /// 拉取全局统计（天 / 条 / 字），失败则保持空，侧栏不展示该行。
    private func loadStats() async {
        stats = try? await client.stats()
    }

    /// 读取当前 STT 引擎名（用于侧栏展示）。
    private func loadCurrentEngine() async {
        guard let state = try? await client.onboarding() else { return }
        let current = state.currentProvider
        currentEngine = state.allProviders.first { $0.name == current }?.label
            ?? (current.isEmpty ? nil : current)
    }
}
