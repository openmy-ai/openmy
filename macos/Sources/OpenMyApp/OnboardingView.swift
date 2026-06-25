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
                VStack(spacing: Theme.Spacing.md) {
                    ForEach(vm.providers) { provider in
                        ProviderRow(provider: provider, isWorking: vm.isWorking) {
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

private struct ProviderRow: View {
    let provider: ProviderChoice
    let isWorking: Bool
    let onSelect: () -> Void

    // 云端缺 Key 等未就绪状态不可选，避免选了又失败。
    private var selectable: Bool { !isWorking && !provider.isActive && provider.ready }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.md) {
            VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                titleLine
                Text(provider.description)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.secondaryText)
                keyHint
            }
            Spacer(minLength: Theme.Spacing.md)
            selectButton
        }
        .omCard()
        .overlay(
            // 当前选中的引擎用强调色描边，给出明确的“已选”视觉。
            RoundedRectangle(cornerRadius: Theme.Radius.card)
                .strokeBorder(
                    provider.isActive ? Theme.Palette.accent : Color.clear,
                    lineWidth: provider.isActive ? 1.5 : 0
                )
        )
        .opacity(provider.ready ? 1 : 0.6)
    }

    // 标题行：名称 + 推荐徽章 + 本地/云端标记。
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

    // API Key 状态提示。
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

    // 选择按钮。当前选中显示对勾态。
    private var selectButton: some View {
        Button(action: onSelect) {
            if provider.isActive {
                Label("已选", systemImage: "checkmark")
            } else {
                Text("选这个")
            }
        }
        .disabled(!selectable)
        .buttonStyle(.borderedProminent)
        .tint(Theme.Palette.accent)
    }
}
