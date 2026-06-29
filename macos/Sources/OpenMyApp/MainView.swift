import SwiftUI
import OpenMyKit
import UniformTypeIdentifiers
import Charts

/// 主界面：左侧栏（导航分区 + 日报列表 + 个人资料 / 引擎），右侧日报 / 进行中的任务进度。
/// 一级入口（首页 / 报告 / 记忆库 / 校正词典 / 设置）都收进侧栏顶部导航分区（对齐 Linear，
/// 侧栏即主导航）；右上工具栏只留与当前操作相关的「处理录音」主操作与「搜索」。
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
    /// 记忆库状态机：三类记忆条目（待办/项目/决策）+ 查询工作台。
    /// 与 correctionsVM 一样在 NavigationSplitView 上 .environment 注入，记忆库面板从环境读取同一份实例。
    @State private var contextVM: ContextViewModel
    /// 报告状态机：周报（7天）/月报（30天）聚合，纯逻辑无网络，数据由视图从 dates 与 projects 取好后传入。
    @State private var reportVM = ReportViewModel()
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
    /// 「记忆库」面板是否呈现。
    @State private var showContext = false
    /// 「报告」面板是否呈现（默认周视图）。
    @State private var showReport = false
    /// 「设置」面板是否呈现（屏幕上下文 + 个人资料 + 外观 + 引擎）。
    @State private var showSettings = false
    /// 侧栏「首页」导航：是否强制回到首页概览。BriefingListViewModel 的 selectedDate 为
    /// private(set) 无法清空，故用本地呈现标记覆盖详情分支——点「首页」置 true 回概览，
    /// 任何跳转到具体日报的路径都重置回 false。纯呈现层，不动数据流与选择逻辑。
    @State private var showingHome = false
    /// 设置面板状态机：屏幕上下文设置（加载/部分合并更新），面板呈现时按需 load。
    @State private var settingsVM: SettingsViewModel
    /// 设置面板内「转写引擎」分区复用的 onboarding 状态机（与首次配置同源 providers/select）。
    @State private var settingsOnboardingVM: OnboardingViewModel

    /// 个人资料（纯本地偏好，@AppStorage）：顶栏 / 首页概览展示头像与昵称。
    @AppStorage(PreferenceKeys.profileName) private var profileName = ""
    @AppStorage(PreferenceKeys.profileEmoji) private var profileEmoji = ""

    init(client: APIClient, onReconfigure: @escaping () -> Void = {}) {
        self.client = client
        self.onReconfigure = onReconfigure
        _briefings = State(initialValue: BriefingListViewModel(client: client))
        _job = State(initialValue: JobViewModel(client: client))
        _searchVM = State(initialValue: SearchViewModel(client: client))
        _correctionsVM = State(initialValue: CorrectionsViewModel(client: client))
        _contextVM = State(initialValue: ContextViewModel(client: client))
        _settingsVM = State(initialValue: SettingsViewModel(client: client))
        _settingsOnboardingVM = State(initialValue: OnboardingViewModel(client: client))
    }

    /// 按搜索词过滤日期（匹配日期或摘要）。
    private var visibleDates: [DayEntry] {
        let q = search.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return briefings.dates }
        return briefings.dates.filter { $0.date.contains(q) || $0.summary.contains(q) }
    }

    /// 当前是否处于首页概览（无选中日报，或显式点了侧栏「首页」）。用于「首页」导航行高亮。
    private var isHomeActive: Bool {
        showingHome || briefings.selectedDate == nil
    }

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            detail
        }
        // 校正词典共享给详情区（划选纠错）与「校正词典」面板，同一份 corrections。
        .environment(correctionsVM)
        // 记忆库状态机注入：记忆库面板从环境读取同一份 contextVM（条目 + 查询工作台）。
        .environment(contextVM)
        // 右上工具栏精简为「搜索」+「处理录音」（主 CTA）；记忆库 / 报告 / 校正 / 设置入口已迁到侧栏。
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
                    showImporter = true
                } label: {
                    Label("处理录音", systemImage: "waveform.badge.plus")
                }
                .omButton(.primary)
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
            // 显式重注入：macOS 下 sheet/窗口恢复不可靠继承 .environment(@Observable)，
            // 不注入则 sheet 读 @Environment 会触发缺失断言崩溃。
            .environment(correctionsVM)
            .environment(toastCenter)
        }
        .sheet(isPresented: $showContext) {
            // 记忆库面板从环境取 contextVM 与 toastCenter（上面 .environment 已注入）。
            // 证据回链复用波次1 地基：转跳焦点交给 handleSearchSelect（切日期 + 定位段落 + 高亮），并关闭面板。
            // 用撑满的 ZStack 蒙层托住固定尺寸面板使其居中（修 issue #14：macOS 下裸固定 frame
            // 的 sheet 会贴左上）。对齐 SpotlightView 的撑满居中做法；点蒙层空白处关闭。
            ZStack {
                Color.black.opacity(0.42).ignoresSafeArea()
                    .onTapGesture { showContext = false }
                ContextView(
                    onClose: { showContext = false },
                    onJumpToEvidence: { focus in jumpFromContext(focus) }
                )
                .environment(contextVM)
                .environment(toastCenter)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .sheet(isPresented: $showReport) {
            // 报告聚合纯逻辑：openReport() 已用当前 dates / projects / 基准日期填好 reportVM。
            // onOpenDate 接到日报选择：切到该天并关闭报告（对齐 reports.js 点日期回看当天日报）。
            // 用 NavigationStack 包一层只为给 macOS sheet 留一个「完成」关闭入口（ReportView 自身不渲染关闭按钮）。
            NavigationStack {
                ReportView(
                    viewModel: reportVM,
                    dates: briefings.dates,
                    today: reportToday(),
                    onOpenDate: { date in openDateFromReport(date) }
                )
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("完成") { showReport = false }
                            .keyboardShortcut(.cancelAction)
                    }
                }
            }
            .frame(minWidth: 560, minHeight: 520)
        }
        .sheet(isPresented: $showSettings) {
            // 设置面板：转写引擎（settingsOnboardingVM）+ 屏幕上下文（settingsVM）+ 外观 / 个人资料（@AppStorage）。
            // SettingsView 自带头部「完成」与自身的 .task 加载，这里只负责注入两个 VM 与关闭回调。
            // 关闭时重拉当前引擎名，把面板内可能的切换同步到侧栏展示。
            // 撑满的 ZStack 蒙层托住固定尺寸面板使其居中（修 issue #14：裸固定 frame 的 sheet 贴左上）。
            ZStack {
                Color.black.opacity(0.42).ignoresSafeArea()
                    .onTapGesture {
                        showSettings = false
                        Task { await loadCurrentEngine() }
                    }
                SettingsView(
                    onboarding: settingsOnboardingVM,
                    settings: settingsVM,
                    onClose: {
                        showSettings = false
                        Task { await loadCurrentEngine() }
                    }
                )
                .environment(toastCenter)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
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
            await contextVM.load()
        }
    }

    // MARK: - 侧栏

    /// 侧栏：顶部导航分区（工作区入口）+ 日报列表，底部个人资料 / 引擎。
    /// 整体走 surfacePanel 实色（比详情区 background 高一档），靠 1px 细描边分层，不用阴影。
    private var sidebar: some View {
        List {
            // 工作区导航分区：一级入口都用 OMNavRow（图标 + 文字 + hover + 选中态），
            // 「首页」回概览，其余直接触发现有 sheet 开关 / openReport()，弹层逻辑不动。
            Section {
                OMNavRow(icon: "house", title: "首页", isSelected: isHomeActive) {
                    showingHome = true
                }
                OMNavRow(icon: "chart.bar.doc.horizontal", title: "报告") {
                    openReport()
                }
                OMNavRow(icon: "brain", title: "记忆库") {
                    showContext = true
                }
                OMNavRow(icon: "character.book.closed", title: "校正词典") {
                    showCorrections = true
                }
                OMNavRow(icon: "gearshape", title: "设置") {
                    showSettings = true
                }
            } header: {
                OMGroupLabel("工作区")
            }
            .listRowSeparator(.hidden)
            .listRowInsets(EdgeInsets(top: 1, leading: Theme.Spacing.xs, bottom: 1, trailing: Theme.Spacing.xs))
            .listRowBackground(Color.clear)

            // 日报列表分区：扁平行 + omRow hover / 选中（accent 微底），去掉系统满饱和蓝选中块。
            Section {
                if briefings.dates.isEmpty {
                    Text("还没有日报")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.tertiaryText)
                        .padding(.horizontal, Theme.Spacing.sm)
                        .padding(.vertical, Theme.Spacing.xs)
                } else if visibleDates.isEmpty {
                    Text("没有匹配「\(search)」的日报")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.tertiaryText)
                        .padding(.horizontal, Theme.Spacing.sm)
                        .padding(.vertical, Theme.Spacing.xs)
                } else {
                    ForEach(visibleDates) { entry in
                        Button {
                            showingHome = false
                            Task { await briefings.select(date: entry.date) }
                        } label: {
                            sidebarRow(entry)
                        }
                        .buttonStyle(.plain)
                        .omRow(
                            isSelected: !showingHome && entry.date == briefings.selectedDate,
                            minHeight: Theme.RowHeight.dateList
                        )
                    }
                }
            } header: {
                OMGroupLabel("日报")
            }
            .listRowSeparator(.hidden)
            .listRowInsets(EdgeInsets(top: 1, leading: Theme.Spacing.xs, bottom: 1, trailing: Theme.Spacing.xs))
            .listRowBackground(Color.clear)
        }
        .listStyle(.sidebar)
        .scrollContentBackground(.hidden)
        .background(Theme.Palette.surfacePanel)
        .searchable(text: $search, placement: .sidebar, prompt: "搜索日期或内容")
        .frame(minWidth: 240)
        .safeAreaInset(edge: .bottom) { sidebarFooter }
    }

    /// 侧栏底部：个人资料 + 统计概览（克制单行）+ 当前引擎 / 重新配置。
    /// 收敛为紧凑一组，顶部一条 borderSubtle 与列表分隔，整体 surfacePanel 实色。
    private var sidebarFooter: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            OMErrorText(briefings.errorMessage)
            profileRow
            if let stats {
                statsOverview(stats)
            }
            engineRow
        }
        .padding(.horizontal, Theme.Spacing.md)
        .padding(.top, Theme.Spacing.sm)
        .padding(.bottom, Theme.Spacing.md)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            Theme.Palette.surfacePanel
                .overlay(alignment: .top) {
                    Rectangle()
                        .fill(Theme.Palette.borderSubtle)
                        .frame(height: 1)
                }
        )
    }

    /// 侧栏底部个人资料行：emoji 头像 + 昵称（纯本地 @AppStorage）。点击打开设置。
    private var profileRow: some View {
        Button {
            showSettings = true
        } label: {
            HStack(spacing: Theme.Spacing.sm) {
                ZStack {
                    Circle()
                        .fill(Theme.Palette.accent.opacity(0.12))
                        .frame(width: 26, height: 26)
                    Text(profileEmoji.isEmpty ? "🙂" : profileEmoji)
                        .font(.system(size: 14))
                }
                Text(profileName.isEmpty ? "设置个人资料" : profileName)
                    .font(Theme.Typography.label)
                    .foregroundStyle(
                        profileName.isEmpty ? Theme.Palette.secondaryText : Theme.Palette.primaryText
                    )
                    .lineLimit(1)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(Theme.Typography.caption2)
                    .foregroundStyle(Theme.Palette.tertiaryText)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    /// 侧栏底部统计概览：天 / 条 / 字收敛为一行克制的三级灰小字。
    private func statsOverview(_ stats: Stats) -> some View {
        Text("\(stats.totalDates) 天 · \(stats.totalSegments) 条 · \(stats.totalWords) 字")
            .font(Theme.Typography.caption2)
            .foregroundStyle(Theme.Palette.tertiaryText)
            .lineLimit(1)
    }

    /// 侧栏底部当前引擎行：低饱和状态点徽章 + 重新配置入口。
    private var engineRow: some View {
        HStack(spacing: Theme.Spacing.sm) {
            OMStatusBadge(currentEngine ?? "未配置", status: .neutral, dot: true)
            Spacer()
            Button("重新配置", action: onReconfigure)
                .omButton(.ghost, size: .small)
        }
    }

    private func sidebarRow(_ entry: DayEntry) -> some View {
        // 友好日期作主标题（今天/昨天/前天/星期X/M月D日），原 ISO 串作次行佐证。
        // today 基准取 reportToday()（选中日期 / 已有日期最大值），不依赖系统时钟。
        let friendly = FriendlyDate.format(date: entry.date, today: reportToday())
        return VStack(alignment: .leading, spacing: Theme.Spacing.xxs) {
            HStack(spacing: Theme.Spacing.sm) {
                Text(friendly)
                    .font(Theme.Typography.label)
                    .foregroundStyle(Theme.Palette.primaryText)
                if friendly != entry.date {
                    // ISO 日期属元数据，走三级灰（不染 accent）。
                    Text(entry.date)
                        .font(Theme.Typography.caption2)
                        .foregroundStyle(Theme.Palette.tertiaryText)
                }
            }
            Text(entry.summary.isEmpty
                 ? "\(entry.segments) 段 · \(entry.wordCount) 字"
                 : entry.summary)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
                .lineLimit(1)
        }
    }

    // MARK: - 详情区

    @ViewBuilder
    private var detail: some View {
        ZStack {
            if job.job != nil {
                ProgressPanelView(job: job, onDismiss: viewBriefingFromJob, onReconfigure: onReconfigure)
            } else if !showingHome, let briefing = briefings.selectedBriefing {
                // 仅当焦点日期与当前日报一致时透传，避免切换日期后旧焦点串到别的日报。
                BriefingDetailView(
                    briefing: briefing,
                    client: client,
                    focus: searchFocus?.date == briefing.date ? searchFocus : nil,
                    onCorrectionApplied: reloadAfterCorrections
                )
            } else {
                homeOverview
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        // 详情容器显式走 background token，让三层表面由 token 控制而非系统材质。
        .background(Theme.Palette.background)
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

    // MARK: - 首页概览（无选中日报时）

    /// 无选中日报时的详情区首页：问候 + 头像昵称、最近 7 天统计、最近几天快捷入口、拖拽上传入口。
    /// 仍承载详情区的拖拽上传（drop 绑定在 detail 容器上，本视图只提供按钮入口与提示）。
    /// 密度按 Linear 收紧：间距 lg、外边距 xl，分隔走 borderSubtle 细线。
    private var homeOverview: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
                greetingHeader
                weeklyStatsCard
                recentDaysSection
                Divider().overlay(Theme.Palette.borderSubtle)
                dropPrompt
            }
            .padding(Theme.Spacing.xl)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// 问候头：emoji 头像 + 「下午好，昵称」。昵称为空时只问候。
    private var greetingHeader: some View {
        // 问候语 hour 取本机当前小时（纯展示，不参与任何数据计算 / 测试）。
        let hour = Calendar.current.component(.hour, from: Date())
        let greeting = Greeting.text(hour: hour)
        let name = profileName.trimmingCharacters(in: .whitespaces)
        let emoji = profileEmoji.isEmpty ? "🙂" : profileEmoji
        return HStack(spacing: Theme.Spacing.md) {
            ZStack {
                Circle()
                    .fill(Theme.Palette.accent.opacity(0.12))
                    .frame(width: 44, height: 44)
                Text(emoji)
                    .font(.system(size: 24))
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xxs) {
                Text(name.isEmpty ? greeting : "\(greeting)，\(name)")
                    .font(Theme.Typography.pageTitle)
                    .tracking(Theme.Tracking.pageTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
            }
            Spacer()
        }
    }

    /// 最近 7 天统计卡：活跃天 / 段数 / 字数。基准「今天」用 reportToday()，不依赖系统时钟。
    /// 单卡内三栏 OMMetric + borderSubtle 细分隔，数字收到 metric(20)。
    private var weeklyStatsCard: some View {
        let summary = ReportAggregator.aggregate(
            dates: briefings.dates, window: 7, today: reportToday()
        )
        return VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            Text("最近 7 天")
                .font(Theme.Typography.sectionTitle)
                .tracking(Theme.Tracking.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            HStack(spacing: 0) {
                OMMetric(value: "\(summary.activeDays)", label: "活跃天")
                    .frame(maxWidth: .infinity)
                Divider().frame(height: 28).overlay(Theme.Palette.borderSubtle)
                OMMetric(value: "\(summary.totalSegments)", label: "段")
                    .frame(maxWidth: .infinity)
                Divider().frame(height: 28).overlay(Theme.Palette.borderSubtle)
                OMMetric(value: "\(summary.totalWords)", label: "字")
                    .frame(maxWidth: .infinity)
            }
        }
        .omCard()
    }

    /// 最近几天快捷入口：取已有日期里最新的至多 5 天，点击切到该天日报。
    /// 扁平行（omRow hover）+ 行间 borderSubtle 细分隔，外层单一容器描边，不再每行套卡。
    @ViewBuilder
    private var recentDaysSection: some View {
        let recent = Array(
            briefings.dates.sorted { $0.date > $1.date }.prefix(5)
        )
        if !recent.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                Text("最近")
                    .font(Theme.Typography.sectionTitle)
                    .tracking(Theme.Tracking.sectionTitle)
                    .foregroundStyle(Theme.Palette.primaryText)
                VStack(spacing: 0) {
                    ForEach(Array(recent.enumerated()), id: \.element.id) { index, entry in
                        if index > 0 {
                            Divider().overlay(Theme.Palette.borderSubtle)
                        }
                        Button {
                            showingHome = false
                            Task { await briefings.select(date: entry.date) }
                        } label: {
                            recentDayRow(entry)
                        }
                        .buttonStyle(.plain)
                        .omRow(minHeight: Theme.RowHeight.listDetail)
                    }
                }
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.Radius.lg)
                        .strokeBorder(Theme.Palette.borderSubtle, lineWidth: 1)
                )
            }
        }
    }

    private func recentDayRow(_ entry: DayEntry) -> some View {
        let friendly = FriendlyDate.format(date: entry.date, today: reportToday())
        return HStack(spacing: Theme.Spacing.md) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xxs) {
                Text(friendly)
                    .font(Theme.Typography.label)
                    .foregroundStyle(Theme.Palette.primaryText)
                Text(entry.summary.isEmpty
                     ? "\(entry.segments) 段 · \(entry.wordCount) 字"
                     : entry.summary)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .lineLimit(1)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(Theme.Typography.caption2)
                .foregroundStyle(Theme.Palette.tertiaryText)
        }
    }

    /// 空状态：引导拖入录音或用按钮选择。Linear 式克制——小图标、窄宽、居中，不铺满。
    private var dropPrompt: some View {
        VStack(spacing: Theme.Spacing.md) {
            Image(systemName: "square.and.arrow.down.on.square")
                .font(.system(size: 28, weight: .light))
                .foregroundStyle(Theme.Palette.secondaryText)

            Text("拖入录音")
                .font(Theme.Typography.cardTitle)
                .tracking(Theme.Tracking.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            Button {
                showImporter = true
            } label: {
                Label("选择录音文件", systemImage: "folder")
            }
            .omButton(.primary)
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
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
            }

            OMErrorText(briefings.errorMessage)
        }
        .frame(maxWidth: 320)
        .padding(.vertical, Theme.Spacing.xl)
        .frame(maxWidth: .infinity)
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
        // 成功跳转到目标日报时离开首页概览（清掉「首页」覆盖标记）。
        if succeeded { showingHome = false }
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

    /// 打开报告：先用当前 dates 与活跃项目算好周报/月报，再呈现面板（默认周视图）。
    /// 「今天」基准日期不读系统时钟：优先取当前选中日期，否则取已有日期里的最大值（对齐聚合器外部传入约定）。
    private func openReport() {
        let activeProjects = contextVM.projects.filter { $0.status == "active" }
        reportVM.load(dates: briefings.dates, activeProjects: activeProjects, today: reportToday())
        showReport = true
    }

    /// 报告里点某天：切到该天日报并关闭报告面板。
    private func openDateFromReport(_ date: String) {
        showingHome = false
        showReport = false
        Task { await briefings.select(date: date) }
    }

    /// 报告基准「今天」：选中日期优先，否则取已有日期的最大值，再退到空串（聚合器对非法日期安全降级）。
    private func reportToday() -> String {
        if let selected = briefings.selectedDate { return selected }
        return briefings.dates.map(\.date).max() ?? ""
    }

    /// 记忆库证据回链：先关闭记忆库面板，再复用搜索跳转（切日期 + 定位段落 + 高亮）。
    /// 焦点已由 contextVM.focus(for:) 从证据组装好（date + time_range 起点 + query），这里直接转交。
    private func jumpFromContext(_ focus: SearchFocus) {
        showContext = false
        handleSearchSelect(focus)
    }

    /// 搜索命中后：切到目标日期、记下焦点供详情区定位 + 高亮、关闭浮层。
    private func handleSearchSelect(_ focus: SearchFocus) {
        showingHome = false
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
