import SwiftUI
import OpenMyKit

/// 设置面板：以 `.sheet` 呈现，分四个分区（TabView）把原本散落的偏好收进常驻设置。
///
/// 分区：
/// - 转写引擎：复用 `OnboardingViewModel` 展示当前引擎与可选引擎，可切换（select），
///   等于把首次配置（onboarding）收进常驻设置，随时改引擎而不必走「重新配置」回退。
/// - 屏幕上下文：用传入的 `SettingsViewModel` 展示参与模式开关与排除项编辑，
///   改动走部分字段合并（VM.update / setMode / saveExclusions），成功后弹 toast。
/// - 外观：纯本地偏好（@AppStorage），主题分段控件 + 强调色选择。
/// - 个人资料：纯本地偏好（@AppStorage），昵称输入 + 头像 emoji 选择。
///
/// 接入方式（由上层负责，本视图不改根 App）：两个 VM 由调用方在构造时传入（与 MainView 一致），
/// `ToastCenter` 从环境取（App 根已 `.environment(toastCenter)` 注入）。`onClose` 关闭整个面板。
struct SettingsView: View {
    /// 转写引擎状态机：与首次配置共用一套（providers / select）。
    @Bindable var onboarding: OnboardingViewModel
    /// 屏幕上下文设置状态机（部分字段合并 + 加载）。
    @Bindable var settings: SettingsViewModel
    /// 关闭整个面板。
    var onClose: () -> Void

    /// 全局 Toast 中心：屏幕上下文保存成功 / 引擎切换后给反馈。
    @Environment(ToastCenter.self) private var toastCenter

    /// 当前选中的分区。
    @State private var tab: Tab = .engine

    /// 设置分区。
    private enum Tab: Hashable {
        case engine, screen, appearance, profile
    }

    init(
        onboarding: OnboardingViewModel,
        settings: SettingsViewModel,
        onClose: @escaping () -> Void = {}
    ) {
        self.onboarding = onboarding
        self.settings = settings
        self.onClose = onClose
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            TabView(selection: $tab) {
                EngineSettingsSection(onboarding: onboarding, toastCenter: toastCenter)
                    .tabItem { Label("转写引擎", systemImage: "cpu") }
                    .tag(Tab.engine)

                ScreenContextSection(settings: settings, toastCenter: toastCenter)
                    .tabItem { Label("屏幕上下文", systemImage: "rectangle.on.rectangle") }
                    .tag(Tab.screen)

                AppearanceSection()
                    .tabItem { Label("外观", systemImage: "paintbrush") }
                    .tag(Tab.appearance)

                ProfileSection()
                    .tabItem { Label("个人资料", systemImage: "person.crop.circle") }
                    .tag(Tab.profile)
            }
        }
        // 弹性上限而非固定尺寸：让外层 sheet 的 ZStack 蒙层撑满父窗口、本面板居中（issue #14）。
        .frame(maxWidth: 520, maxHeight: 560)
        .task {
            if onboarding.state == nil { await onboarding.load() }
            if settings.settings == nil { await settings.load() }
        }
    }

    // MARK: - 头部

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.sm) {
            Text("设置")
                .font(Theme.Typography.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Spacer()
            Button("完成", action: onClose)
                .keyboardShortcut(.cancelAction)
        }
        .padding(Theme.Spacing.lg)
    }
}

// MARK: - 转写引擎区

/// 转写引擎分区：复用 `OnboardingViewModel` 列出可选引擎并切换。
/// 与 OnboardingView 同源数据，但这里不触发完成回调——切换后停留在设置面板。
private struct EngineSettingsSection: View {
    @Bindable var onboarding: OnboardingViewModel
    let toastCenter: ToastCenter

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.md) {
                Text("转写引擎决定录音如何转成文字。本地引擎免密钥，云端引擎更快但需要先配置密钥。")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)

                if onboarding.providers.isEmpty {
                    Text("正在读取引擎…")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                        .padding(.vertical, Theme.Spacing.md)
                } else {
                    ForEach(onboarding.providers) { provider in
                        EngineRow(provider: provider, isWorking: onboarding.isWorking) {
                            Task {
                                await onboarding.select(provider.name)
                                if onboarding.errorMessage == nil {
                                    toastCenter.show("已切换到 \(provider.label)")
                                }
                            }
                        }
                    }
                }

                OMErrorText(onboarding.errorMessage)
            }
            .padding(Theme.Spacing.lg)
        }
    }
}

/// 单个引擎行：名称 + 推荐 / 本地云端徽章 + 描述 + 选择按钮。
/// 选中态用强调色描边；未就绪（云端缺密钥）置灰不可选。
private struct EngineRow: View {
    let provider: ProviderChoice
    let isWorking: Bool
    let onSelect: () -> Void

    private var selectable: Bool { !isWorking && !provider.isActive && provider.ready }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.md) {
            VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                titleLine
                Text(provider.description)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                keyHint
            }
            Spacer(minLength: Theme.Spacing.md)
            selectButton
        }
        .omCard()
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.card)
                .strokeBorder(
                    provider.isActive ? Theme.Palette.accent : Color.clear,
                    lineWidth: provider.isActive ? 1.5 : 0
                )
        )
        .opacity(provider.ready ? 1 : 0.6)
    }

    private var titleLine: some View {
        HStack(spacing: Theme.Spacing.sm) {
            Text(provider.label)
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            if provider.isRecommended {
                OMBadge("推荐", kind: .accent)
            }
            OMBadge(provider.type == "local" ? "本地" : "云端", kind: .neutral)
        }
    }

    @ViewBuilder
    private var keyHint: some View {
        if provider.needsApiKey && !provider.ready {
            Label("需要先配置 API Key 才能使用", systemImage: "key.fill")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.warning)
        } else if provider.needsApiKey {
            Label("需要 API Key", systemImage: "key")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
        }
    }

    private var selectButton: some View {
        Button(action: onSelect) {
            if provider.isActive {
                Label("当前", systemImage: "checkmark")
            } else {
                Text("切换")
            }
        }
        .disabled(!selectable)
        .buttonStyle(.borderedProminent)
        .tint(Theme.Palette.accent)
    }
}

// MARK: - 屏幕上下文区

/// 屏幕上下文分区：参与模式（关闭 / 仅摘要 / 完整）开关 + 三类排除项编辑。
/// 改动走 `SettingsViewModel` 的部分字段合并，成功弹 toast，失败留 errorMessage。
private struct ScreenContextSection: View {
    @Bindable var settings: SettingsViewModel
    let toastCenter: ToastCenter

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
                Text("屏幕上下文会在你工作时记录看到的内容，转成文字补进当天上下文。完整模式保留截图，仅摘要只留文字概要。")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)

                if let current = settings.settings {
                    modePicker(current)
                    Divider()
                    exclusions(current)
                } else if settings.isLoading {
                    Text("正在读取设置…")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                } else {
                    Text("暂时读不到屏幕上下文设置。")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.secondaryText)
                }

                OMErrorText(settings.errorMessage)
            }
            .padding(Theme.Spacing.lg)
        }
    }

    // 参与模式分段控件。改动后调 setMode，成功提示。
    private func modePicker(_ current: ScreenContextSettings) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            Text("参与模式")
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            Picker("参与模式", selection: Binding(
                get: { current.mode },
                set: { newMode in
                    guard newMode != current.mode else { return }
                    Task {
                        let ok = await settings.setMode(newMode)
                        if ok { toastCenter.show("已更新屏幕上下文模式") }
                    }
                }
            )) {
                Text("关闭").tag(ScreenContextSettings.Mode.off)
                Text("仅摘要").tag(ScreenContextSettings.Mode.summaryOnly)
                Text("完整").tag(ScreenContextSettings.Mode.full)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .disabled(settings.isLoading)

            Text(modeHint(current.mode))
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
        }
    }

    private func modeHint(_ mode: ScreenContextSettings.Mode) -> String {
        switch mode {
        case .off: return "已关闭，不记录任何屏幕内容。"
        case .summaryOnly: return "只保留文字概要，不保存截图。"
        case .full: return "保留截图与文字，上下文最完整。"
        }
    }

    // 三类排除项：应用 / 域名 / 窗口关键词。各自一个换行分隔的多行编辑框，失焦保存。
    @ViewBuilder
    private func exclusions(_ current: ScreenContextSettings) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            Text("排除项")
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Text("命中的应用、网站或窗口标题不会被记录。每行一个。")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)

            ExclusionEditor(
                title: "排除应用",
                placeholder: "例如：微信",
                values: current.excludeApps,
                disabled: settings.isLoading
            ) { list in
                Task {
                    let ok = await settings.saveExclusions(apps: list)
                    if ok { toastCenter.show("已更新排除应用") }
                }
            }

            ExclusionEditor(
                title: "排除域名",
                placeholder: "例如：mail.example.com",
                values: current.excludeDomains,
                disabled: settings.isLoading
            ) { list in
                Task {
                    let ok = await settings.saveExclusions(domains: list)
                    if ok { toastCenter.show("已更新排除域名") }
                }
            }

            ExclusionEditor(
                title: "排除窗口关键词",
                placeholder: "例如：密码",
                values: current.excludeWindowKeywords,
                disabled: settings.isLoading
            ) { list in
                Task {
                    let ok = await settings.saveExclusions(windowKeywords: list)
                    if ok { toastCenter.show("已更新窗口关键词") }
                }
            }
        }
    }
}

/// 单类排除项编辑框：换行分隔的字符串列表，本地编辑、失焦时回传清洗后的数组。
/// 只有内容相对原始值发生变化才回调保存，避免无谓的网络请求。
private struct ExclusionEditor: View {
    let title: String
    let placeholder: String
    let values: [String]
    let disabled: Bool
    let onCommit: ([String]) -> Void

    /// 编辑中的多行文本（换行分隔）。
    @State private var text: String
    /// 上次提交对应的规范化数组，用于判断是否真的改了。
    @State private var committed: [String]

    init(
        title: String,
        placeholder: String,
        values: [String],
        disabled: Bool,
        onCommit: @escaping ([String]) -> Void
    ) {
        self.title = title
        self.placeholder = placeholder
        self.values = values
        self.disabled = disabled
        self.onCommit = onCommit
        _text = State(initialValue: values.joined(separator: "\n"))
        _committed = State(initialValue: values)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(title)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)

            TextEditor(text: $text)
                .font(.system(.body, design: .monospaced))
                .frame(height: 72)
                .padding(Theme.Spacing.xs)
                .background(Theme.Palette.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.card))
                .disabled(disabled)
                .overlay(alignment: .topLeading) {
                    if text.isEmpty {
                        Text(placeholder)
                            .font(.system(.body, design: .monospaced))
                            .foregroundStyle(Theme.Palette.secondaryText)
                            .padding(Theme.Spacing.sm)
                            .allowsHitTesting(false)
                    }
                }
                .onChange(of: text) { _, _ in /* 仅本地编辑，提交在失焦时 */ }
                .onSubmit { commit() }

            HStack {
                Spacer()
                Button("保存") { commit() }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .disabled(disabled || normalized == committed)
            }
        }
        // 外部数据变化（重新加载 / 合并返回）时同步本地编辑框。
        .onChange(of: values) { _, newValues in
            if newValues != committed {
                committed = newValues
                text = newValues.joined(separator: "\n")
            }
        }
    }

    /// 当前文本规范化为数组：按行拆分、去空白、丢弃空行。
    private var normalized: [String] {
        text
            .split(whereSeparator: \.isNewline)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
    }

    private func commit() {
        let list = normalized
        guard list != committed else { return }
        committed = list
        onCommit(list)
    }
}

// MARK: - 外观区

/// 外观分区：主题（跟随系统 / 浅色 / 深色）分段控件 + 强调色选择。纯本地偏好（@AppStorage）。
private struct AppearanceSection: View {
    @AppStorage(PreferenceKeys.appAppearance) private var appearanceRaw = AppAppearance.default.rawValue
    @AppStorage(PreferenceKeys.accent) private var accentRaw = AccentColorChoice.default.rawValue

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    Text("主题")
                        .font(Theme.Typography.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    Picker("主题", selection: $appearanceRaw) {
                        Text("跟随系统").tag(AppAppearance.system.rawValue)
                        Text("浅色").tag(AppAppearance.light.rawValue)
                        Text("深色").tag(AppAppearance.dark.rawValue)
                    }
                    .pickerStyle(.segmented)
                    .labelsHidden()
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    Text("强调色")
                        .font(Theme.Typography.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    accentSwatches
                }
            }
            .padding(Theme.Spacing.lg)
        }
    }

    // 强调色色板：每个选项一个圆点，选中态加描边。
    private var accentSwatches: some View {
        HStack(spacing: Theme.Spacing.md) {
            ForEach(AccentColorChoice.allCases, id: \.self) { choice in
                let selected = AccentColorChoice.parse(accentRaw) == choice
                Button {
                    accentRaw = choice.rawValue
                } label: {
                    Circle()
                        .fill(color(for: choice))
                        .frame(width: 26, height: 26)
                        .overlay(
                            Circle()
                                .strokeBorder(
                                    Theme.Palette.primaryText.opacity(selected ? 0.8 : 0),
                                    lineWidth: selected ? 2 : 0
                                )
                        )
                        .padding(2)
                }
                .buttonStyle(.plain)
                .help(label(for: choice))
            }
            Spacer()
        }
    }

    private func color(for choice: AccentColorChoice) -> Color {
        switch choice {
        case .blue: return .blue
        case .purple: return .purple
        case .pink: return .pink
        case .orange: return .orange
        case .green: return .green
        case .graphite: return .gray
        }
    }

    private func label(for choice: AccentColorChoice) -> String {
        switch choice {
        case .blue: return "蓝色"
        case .purple: return "紫色"
        case .pink: return "粉色"
        case .orange: return "橙色"
        case .green: return "绿色"
        case .graphite: return "石墨色"
        }
    }
}

// MARK: - 个人资料区

/// 个人资料分区：昵称输入 + 头像 emoji 选择。纯本地偏好（@AppStorage）。
private struct ProfileSection: View {
    @AppStorage(PreferenceKeys.profileName) private var name = ""
    @AppStorage(PreferenceKeys.profileEmoji) private var emoji = ""

    /// 头像可选 emoji 集合。
    private let emojiChoices = ["😀", "🧑‍💻", "🦊", "🐼", "🚀", "🌙", "🌊", "🍀", "🎧", "📚"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    Text("昵称")
                        .font(Theme.Typography.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    TextField("怎么称呼你", text: $name)
                        .textFieldStyle(.roundedBorder)
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    Text("头像")
                        .font(Theme.Typography.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    emojiGrid
                }
            }
            .padding(Theme.Spacing.lg)
        }
    }

    // emoji 网格：选中态加强调色背景圈。
    private var emojiGrid: some View {
        LazyVGrid(
            columns: Array(repeating: GridItem(.flexible(), spacing: Theme.Spacing.sm), count: 5),
            spacing: Theme.Spacing.sm
        ) {
            ForEach(emojiChoices, id: \.self) { choice in
                let selected = emoji == choice
                Button {
                    emoji = selected ? "" : choice
                } label: {
                    Text(choice)
                        .font(.title2)
                        .frame(width: 44, height: 44)
                        .background(
                            Circle()
                                .fill(selected ? Theme.Palette.accent.opacity(0.18) : Color.clear)
                        )
                        .overlay(
                            Circle()
                                .strokeBorder(
                                    selected ? Theme.Palette.accent : Color.clear,
                                    lineWidth: selected ? 1.5 : 0
                                )
                        )
                }
                .buttonStyle(.plain)
            }
        }
    }
}
