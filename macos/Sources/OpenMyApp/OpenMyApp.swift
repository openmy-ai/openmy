import SwiftUI
import OpenMyKit

/// OpenMy macOS 原生前端入口。
/// 架构：Swift 壳通过 localhost:8420 对接现有 Python 后端，任务控制全部复用后端接口。
@main
struct OpenMyApp: App {
    @State private var root = RootViewModel()
    /// 全局 Toast 中心，注入环境供所有界面复用。
    @State private var toastCenter = ToastCenter()
    /// 外观偏好（@AppStorage）：真正应用到根 Scene，让设置里的主题/强调色生效。
    @AppStorage(PreferenceKeys.appAppearance) private var appearanceRaw = AppAppearance.default.rawValue

    var body: some Scene {
        WindowGroup {
            RootView(root: root)
                .frame(minWidth: 880, minHeight: 560)
                // 单一品牌色：根 .tint 指向主题强调色（Linear 靛蓝），让所有走 .tint 的
                // 原生控件（ProgressView 转圈、TextField 光标/选区、searchable 选中等）与
                // 主题化 UI（按钮/选中行/徽章/进度条/波形）统一，避免首屏蓝+靛蓝双色。
                .tint(Theme.Palette.accent)
                .preferredColorScheme(AppAppearance.parse(appearanceRaw).colorScheme)
                .toastHost()
                // .environment 必须在最外层（最后应用）：toastHost 的浮层也读
                // @Environment(ToastCenter)，注入若在 toastHost 之内层，浮层读不到会崩溃。
                .environment(toastCenter)
        }
        .defaultSize(width: 1080, height: 720)

        // 菜单栏常驻入口
        MenuBarExtra("OpenMy", systemImage: "waveform") {
            Button("打开主窗口") {
                NSApp.activate(ignoringOtherApps: true)
            }
            .keyboardShortcut("o")
            Divider()
            Button("退出 OpenMy") { NSApp.terminate(nil) }
                .keyboardShortcut("q")
        }
    }
}

/// 根状态：决定展示首次配置还是主界面。
@MainActor
@Observable
final class RootViewModel {
    enum Phase { case loading, onboarding, ready }
    var phase: Phase = .loading

    let client = APIClient()
    let onboarding: OnboardingViewModel

    init() {
        onboarding = OnboardingViewModel(client: client)
    }

    func bootstrap() async {
        await onboarding.load()
        phase = onboarding.completed ? .ready : .onboarding
    }

    func onboardingFinished() {
        phase = .ready
    }

    /// 从主界面回到首次配置（重新选引擎）。
    func reconfigure() async {
        await onboarding.load()
        phase = .onboarding
    }
}

struct RootView: View {
    @Bindable var root: RootViewModel

    var body: some View {
        Group {
            switch root.phase {
            case .loading:
                loadingView
            case .onboarding:
                OnboardingView(vm: root.onboarding, onDone: root.onboardingFinished)
            case .ready:
                MainView(client: root.client, onReconfigure: { Task { await root.reconfigure() } })
            }
        }
        .task { await root.bootstrap() }
    }

    /// 启动连接后端时的过渡画面。Linear 式减重：品牌波形缩到 28pt、去掉脉冲动画，
    /// 容器走 background token，弱化为克制的过渡而非视觉焦点。
    private var loadingView: some View {
        VStack(spacing: Theme.Spacing.md) {
            Image(systemName: "waveform")
                .font(.system(size: 28, weight: .light))
                .foregroundStyle(Theme.Palette.accent)
            ProgressView()
                .controlSize(.small)
            Text("正在连接 OpenMy…")
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.secondaryText)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.Palette.background)
    }
}

// MARK: - 外观偏好 → SwiftUI 映射（在 App 层做，因为 OpenMyKit 不依赖 SwiftUI 颜色）

extension AppAppearance {
    /// 映射到根 Scene 的 preferredColorScheme：system 返回 nil（跟随系统）。
    var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

// 强调色不再单独可选：全 app 统一使用 Theme.Palette.accent（Linear 靛蓝）作为唯一品牌色，
// 根 .tint 已指向它，无需再把 AccentColorChoice 映射成 SwiftUI Color。
// AccentColorChoice 仍保留在 OpenMyKit 仅供持久化键兼容。
