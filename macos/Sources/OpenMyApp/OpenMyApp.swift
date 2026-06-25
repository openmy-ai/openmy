import SwiftUI
import OpenMyKit

/// OpenMy macOS 原生前端入口。
/// 架构：Swift 壳通过 localhost:8420 对接现有 Python 后端，任务控制全部复用后端接口。
@main
struct OpenMyApp: App {
    @State private var root = RootViewModel()

    var body: some Scene {
        WindowGroup {
            RootView(root: root)
                .frame(minWidth: 880, minHeight: 560)
        }

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

    /// 启动连接后端时的过渡画面。
    private var loadingView: some View {
        VStack(spacing: Theme.Spacing.lg) {
            Image(systemName: "waveform")
                .font(.system(size: 44, weight: .light))
                .foregroundStyle(Theme.Palette.accent)
                .symbolEffect(.pulse)
            ProgressView()
                .controlSize(.small)
            Text("正在连接 OpenMy…")
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.secondaryText)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
