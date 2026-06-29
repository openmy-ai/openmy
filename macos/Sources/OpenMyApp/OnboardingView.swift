import SwiftUI
import OpenMyKit

/// 首次配置：选 STT 引擎。这是唯一需要用户决定的一步。
struct OnboardingView: View {
    @Bindable var vm: OnboardingViewModel
    var onDone: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
            header

            ScrollView {
                VStack(spacing: Theme.Spacing.sm) {
                    ForEach(vm.providers) { provider in
                        EngineChoiceRow(
                            provider: provider,
                            isWorking: vm.isWorking,
                            activeLabel: "已选",
                            selectLabel: "选这个"
                        ) {
                            Task {
                                await vm.select(provider.name)
                                if vm.completed { onDone() }
                            }
                        }
                    }
                }
                // 顶部留内衬，避免第一张推荐卡片被标题区压住/裁切。
                .padding(.top, Theme.Spacing.sm)
            }
            // 滚动内容上下各留边距，第一张和最后一张卡片不贴边。
            .contentMargins(.vertical, Theme.Spacing.sm, for: .scrollContent)
            .scrollClipDisabled(false)

            OMErrorText(vm.errorMessage)
        }
        .padding(Theme.Spacing.xxl)
        .task { if vm.state == nil { await vm.load() } }
    }

    // 页头：大标题 + 下一步说明。
    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            Text(vm.state?.headline ?? "选择转写引擎")
                .font(Theme.Typography.pageTitle)
                .tracking(Theme.Tracking.pageTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            if let next = vm.state?.nextStep, !next.isEmpty {
                Text(next)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.secondaryText)
            }
        }
        .omSection()
    }
}
