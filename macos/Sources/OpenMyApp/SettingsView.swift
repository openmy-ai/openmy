import SwiftUI
import OpenMyKit

/// 设置面板：以 `.sheet` 呈现，分四个分区把原本散落的偏好收进常驻设置。
///
/// 分区导航改用左侧栏（`OMNavRow`，对齐 Linear「侧栏即主导航」），右侧为内容区：
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
            Divider().overlay(Theme.Palette.borderSubtle)
            HStack(spacing: 0) {
                sidebar
                Divider().overlay(Theme.Palette.borderSubtle)
                content
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        // 弹性上限而非固定尺寸：让外层 sheet 的 ZStack 蒙层撑满父窗口、本面板居中（issue #14）。
        .frame(maxWidth: 560, maxHeight: 560)
        // 弹层表面：popover 实色底 + 1px 描边 + 圆角，靠底色差分层；弹层级允许阴影。
        .background(Theme.Palette.popover)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.xl))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.xl)
                .strokeBorder(Theme.Palette.border, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.28), radius: 16, y: 4)
        .task {
            if onboarding.state == nil { await onboarding.load() }
            if settings.settings == nil { await settings.load() }
        }
    }

    // MARK: - 头部

    private var header: some View {
        OMSectionHeader("设置") {
            Button("完成", action: onClose)
                .omButton(.ghost)
                .keyboardShortcut(.cancelAction)
        }
        .padding(.horizontal, Theme.Spacing.lg)
        .padding(.top, Theme.Spacing.lg)
    }

    // MARK: - 左侧栏导航

    /// 侧栏：surfacePanel 实色底，4 个分区用 `OMNavRow`（hover + 选中态）。
    private var sidebar: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xxs) {
            OMNavRow(icon: "cpu", title: "转写引擎", isSelected: tab == .engine) { tab = .engine }
            OMNavRow(icon: "rectangle.on.rectangle", title: "屏幕上下文", isSelected: tab == .screen) { tab = .screen }
            OMNavRow(icon: "paintbrush", title: "外观", isSelected: tab == .appearance) { tab = .appearance }
            OMNavRow(icon: "person.crop.circle", title: "个人资料", isSelected: tab == .profile) { tab = .profile }
            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.sm)
        .frame(width: 196)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(Theme.Palette.surfacePanel)
    }

    // MARK: - 内容区

    @ViewBuilder
    private var content: some View {
        switch tab {
        case .engine:
            EngineSettingsSection(onboarding: onboarding, toastCenter: toastCenter)
        case .screen:
            ScreenContextSection(settings: settings, toastCenter: toastCenter)
        case .appearance:
            AppearanceSection()
        case .profile:
            ProfileSection()
        }
    }
}

// MARK: - 自定义胶囊分段控件

/// 替换原生 `.pickerStyle(.segmented)`：`muted` 底容器 + 段按钮，
/// 选中段 `card` 底 + accent 文字 + 细描边（高 26、圆角 6），贴合 Linear 克制风格。
private struct OMSegmented<Value: Hashable>: View {
    @Binding var selection: Value
    let options: [(Value, String)]
    var disabled: Bool = false

    var body: some View {
        HStack(spacing: Theme.Spacing.xxs) {
            ForEach(options.indices, id: \.self) { index in
                let option = options[index]
                let isSelected = selection == option.0
                Button {
                    if selection != option.0 { selection = option.0 }
                } label: {
                    Text(option.1)
                        .font(Theme.Typography.label)
                        .foregroundStyle(isSelected ? Theme.Palette.accent : Theme.Palette.secondaryText)
                        .frame(maxWidth: .infinity)
                        .frame(height: 26)
                        .background(isSelected ? Theme.Palette.card : Color.clear)
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.Radius.sm)
                                .strokeBorder(isSelected ? Theme.Palette.borderSubtle : Color.clear, lineWidth: 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.sm))
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(Theme.Spacing.xxs)
        .background(Theme.Palette.muted)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .opacity(disabled ? 0.5 : 1)
        .disabled(disabled)
        .animation(.easeOut(duration: 0.12), value: selection)
    }
}

// MARK: - 转写引擎区

/// 转写引擎分区：复用 `OnboardingViewModel` 列出可选引擎并切换。
/// 与 OnboardingView 同源数据，行也共用 `EngineChoiceRow`；这里不触发完成回调——切换后停留在设置面板。
private struct EngineSettingsSection: View {
    @Bindable var onboarding: OnboardingViewModel
    let toastCenter: ToastCenter

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.md) {
                OMSectionHeader("转写引擎")
                Text("本地引擎免密钥；云端更快，但需要密钥。")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.tertiaryText)

                if onboarding.providers.isEmpty {
                    Text("正在读取引擎…")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.tertiaryText)
                        .padding(.vertical, Theme.Spacing.md)
                } else {
                    VStack(spacing: Theme.Spacing.sm) {
                        ForEach(onboarding.providers) { provider in
                            EngineChoiceRow(
                                provider: provider,
                                isWorking: onboarding.isWorking,
                                activeLabel: "当前",
                                selectLabel: "切换"
                            ) {
                                Task {
                                    await onboarding.select(provider.name)
                                    if onboarding.errorMessage == nil {
                                        toastCenter.show("已切换到 \(provider.label)")
                                    }
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

// MARK: - 屏幕上下文区

/// 屏幕上下文分区：参与模式（关闭 / 仅摘要 / 完整）开关 + 三类排除项编辑。
/// 改动走 `SettingsViewModel` 的部分字段合并，成功弹 toast，失败留 errorMessage。
private struct ScreenContextSection: View {
    @Bindable var settings: SettingsViewModel
    let toastCenter: ToastCenter

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
                OMSectionHeader("屏幕上下文")
                Text("工作时记录屏幕内容，补进当天上下文。")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.tertiaryText)

                if let current = settings.settings {
                    modePicker(current)
                    Divider().overlay(Theme.Palette.borderSubtle)
                    exclusions(current)
                } else if settings.isLoading {
                    Text("正在读取设置…")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.tertiaryText)
                } else {
                    Text("暂时读不到屏幕上下文设置。")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.tertiaryText)
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
                .tracking(Theme.Tracking.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            OMSegmented(
                selection: Binding(
                    get: { current.mode },
                    set: { newMode in
                        guard newMode != current.mode else { return }
                        Task {
                            let ok = await settings.setMode(newMode)
                            if ok { toastCenter.show("已更新屏幕上下文模式") }
                        }
                    }
                ),
                options: [
                    (ScreenContextSettings.Mode.off, "关闭"),
                    (ScreenContextSettings.Mode.summaryOnly, "仅摘要"),
                    (ScreenContextSettings.Mode.full, "完整"),
                ],
                disabled: settings.isLoading
            )

            Text(modeHint(current.mode))
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.tertiaryText)
        }
    }

    private func modeHint(_ mode: ScreenContextSettings.Mode) -> String {
        switch mode {
        case .off: return "不记录屏幕内容"
        case .summaryOnly: return "只存文字概要，不留截图"
        case .full: return "保留截图与文字"
        }
    }

    // 三类排除项：应用 / 域名 / 窗口关键词。各自一个换行分隔的多行编辑框，失焦保存。
    @ViewBuilder
    private func exclusions(_ current: ScreenContextSettings) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            Text("排除项")
                .font(Theme.Typography.cardTitle)
                .tracking(Theme.Tracking.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Text("匹配到的不记录，每行一个。")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.tertiaryText)

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
    /// 仅驱动聚焦环视觉（不参与数据流）。
    @FocusState private var focused: Bool

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

            // 纳入设计系统：muted 底 + 1px input 描边 + Radius.md，聚焦时换 accent 边 + 2px 聚焦环。
            TextEditor(text: $text)
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.primaryText)
                .scrollContentBackground(.hidden)
                .focused($focused)
                .frame(height: 72)
                .padding(.horizontal, Theme.Spacing.sm)
                .padding(.vertical, Theme.Spacing.xs)
                .background(Theme.Palette.muted)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.Radius.md)
                        .strokeBorder(focused ? Theme.Palette.accent : Theme.Palette.input, lineWidth: 1)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.Radius.md + 1)
                        .stroke(Theme.Palette.ring, lineWidth: focused ? 2 : 0)
                        .padding(-1.5)
                )
                .disabled(disabled)
                .overlay(alignment: .topLeading) {
                    if text.isEmpty {
                        Text(placeholder)
                            .font(Theme.Typography.body)
                            .foregroundStyle(Theme.Palette.tertiaryText)
                            .padding(.horizontal, Theme.Spacing.md)
                            .padding(.vertical, Theme.Spacing.sm)
                            .allowsHitTesting(false)
                    }
                }
                .onChange(of: text) { _, _ in /* 仅本地编辑，提交在失焦时 */ }
                .onSubmit { commit() }
                .animation(.easeOut(duration: 0.12), value: focused)

            HStack {
                Spacer()
                Button("保存") { commit() }
                    .omButton(.secondary, size: .small)
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

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
                OMSectionHeader("外观")

                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    Text("主题")
                        .font(Theme.Typography.cardTitle)
                        .tracking(Theme.Tracking.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    OMSegmented(
                        selection: $appearanceRaw,
                        options: [
                            (AppAppearance.system.rawValue, "跟随系统"),
                            (AppAppearance.light.rawValue, "浅色"),
                            (AppAppearance.dark.rawValue, "深色"),
                        ]
                    )
                }

                // 强调色选择器已移除（spec §5.4.2）：全 app 统一使用单一品牌色
                // Theme.Palette.accent（Linear 靛蓝），不再提供多强调色切换，避免与
                // 主题化 UI 产生双色不一致。AccentColorChoice 持久化键保留以兼容旧数据。
            }
            .padding(Theme.Spacing.lg)
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
            VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
                OMSectionHeader("个人资料")

                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    Text("昵称")
                        .font(Theme.Typography.cardTitle)
                        .tracking(Theme.Tracking.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    OMTextField("怎么称呼你", text: $name)
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    Text("头像")
                        .font(Theme.Typography.cardTitle)
                        .tracking(Theme.Tracking.cardTitle)
                        .foregroundStyle(Theme.Palette.primaryText)
                    emojiGrid
                }
            }
            .padding(Theme.Spacing.lg)
        }
    }

    // emoji 网格：选中态加强调色背景圈 + 描边。
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
                                .fill(selected ? Theme.Palette.selectedSurface : Color.clear)
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
