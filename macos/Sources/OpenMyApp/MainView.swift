import SwiftUI
import OpenMyKit
import UniformTypeIdentifiers

/// 主界面：左侧日期列表（可搜索 + 当前引擎 + 重新配置），右侧日报 / 进行中的任务进度。
/// 开始新任务有两条路：工具栏「处理录音」按钮（文件选择器）或直接把文件拖进详情区。
struct MainView: View {
    let client: APIClient
    /// 回到首次配置（重新选引擎）。
    var onReconfigure: () -> Void

    @State private var briefings: BriefingListViewModel
    @State private var job: JobViewModel
    @State private var isDropTargeted = false
    @State private var dropNote: String?
    @State private var search = ""
    @State private var showImporter = false
    @State private var currentEngine: String?

    init(client: APIClient, onReconfigure: @escaping () -> Void = {}) {
        self.client = client
        self.onReconfigure = onReconfigure
        _briefings = State(initialValue: BriefingListViewModel(client: client))
        _job = State(initialValue: JobViewModel(client: client))
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
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showImporter = true
                } label: {
                    Label("处理录音", systemImage: "waveform.badge.plus")
                }
                .help("选择录音文件开始转写")
            }
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
                ProgressPanelView(job: job, onDismiss: dismissJob)
            } else if let briefing = briefings.selectedBriefing {
                BriefingDetailView(briefing: briefing, client: client)
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
        let result = AudioFileFilter.evaluate(urls.map(\.path), maxBatch: 5)
        dropNote = result.note
        guard !result.isEmpty else { return }
        Task {
            await job.start(audioFiles: result.paths)
            job.startPolling()
        }
    }

    /// 任务终态后：清空任务并刷新日报列表，让刚生成的日报出现。
    private func dismissJob() {
        job.clear()
        Task { await briefings.loadDates() }
    }

    /// 读取当前 STT 引擎名（用于侧栏展示）。
    private func loadCurrentEngine() async {
        guard let state = try? await client.onboarding() else { return }
        let current = state.currentProvider
        currentEngine = state.allProviders.first { $0.name == current }?.label
            ?? (current.isEmpty ? nil : current)
    }
}
