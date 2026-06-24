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
            Divider()
            Button("退出") { NSApp.terminate(nil) }
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
}

struct RootView: View {
    @Bindable var root: RootViewModel

    var body: some View {
        Group {
            switch root.phase {
            case .loading:
                ProgressView("正在连接 OpenMy…")
            case .onboarding:
                OnboardingView(vm: root.onboarding, onDone: root.onboardingFinished)
            case .ready:
                MainView(client: root.client)
            }
        }
        .task { await root.bootstrap() }
    }
}
