import SwiftUI
import OpenMyKit

/// 引擎选择行（「转写引擎」设置与「首次配置」共用）。
///
/// 名称 + 推荐 / 本地云端语义徽章 + 描述 + 缺密钥提示 + 选择按钮。
/// 视觉对齐 Linear 的扁平行：选中态用 `selectedSurface` 微底 + 左缘 2pt accent 指示条，
/// 不再整圈 1.5pt 描边；hover 叠 `rowHover` 微底；未就绪（云端缺密钥）整行置灰不可选。
///
/// 两个调用点仅按钮文案不同（「当前 / 切换」对「已选 / 选这个」），故文案由
/// `activeLabel` / `selectLabel` 传入，其余样式与行为完全一致，保证两处风格统一。
struct EngineChoiceRow: View {
    let provider: ProviderChoice
    let isWorking: Bool
    /// 当前已选引擎的按钮文案（如「当前」/「已选」）。
    let activeLabel: String
    /// 可切换引擎的按钮文案（如「切换」/「选这个」）。
    let selectLabel: String
    let onSelect: () -> Void

    @State private var hovering = false

    /// 工作中、已是当前、未就绪都不可选，避免选了又失败。
    private var selectable: Bool { !isWorking && !provider.isActive && provider.ready }

    /// 行底：选中走 accent 微底，hover 走中性微底，否则透明。
    private var rowBackground: Color {
        if provider.isActive { return Theme.Palette.selectedSurface }
        return hovering ? Theme.Palette.rowHover : .clear
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.md) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                titleLine
                Text(provider.description)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.secondaryText)
                keyHint
            }
            Spacer(minLength: Theme.Spacing.md)
            selectButton
        }
        // 行密度对齐 Linear：垂直 ≈10（sm+xxs）/ 水平 12。
        .padding(.vertical, Theme.Spacing.sm + Theme.Spacing.xxs)
        .padding(.horizontal, Theme.Spacing.md)
        .background(rowBackground)
        // 左缘 2pt accent 指示条，仅选中可见（随圆角裁切）。
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(provider.isActive ? Theme.Palette.accent : Color.clear)
                .frame(width: 2)
        }
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.lg))
        .opacity(provider.ready ? 1 : 0.6)
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
        .animation(.easeOut(duration: 0.12), value: hovering)
    }

    // 标题行：名称 + 推荐徽章（accent）+ 本地 / 云端标记（neutral），均走语义徽章。
    private var titleLine: some View {
        HStack(spacing: Theme.Spacing.sm) {
            Text(provider.label)
                .font(Theme.Typography.cardTitle)
                .tracking(Theme.Tracking.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            if provider.isRecommended {
                OMStatusBadge("推荐", status: .accent)
            }
            OMStatusBadge(provider.type == "local" ? "本地" : "云端", status: .neutral)
        }
    }

    // API Key 状态：缺密钥用低饱和 warning 徽章，需密钥但已就绪用中性徽章；
    // 去掉原先 `key.fill` 实色图标的喧染。
    @ViewBuilder
    private var keyHint: some View {
        if provider.needsApiKey && !provider.ready {
            OMStatusBadge("需要先配置 API Key 才能使用", status: .warning)
        } else if provider.needsApiKey {
            OMStatusBadge("需要 API Key", status: .neutral)
        }
    }

    // 选择按钮：当前选中显示对勾态（ghost），否则可切换（primary）。文案由调用方传入。
    private var selectButton: some View {
        Button(action: onSelect) {
            if provider.isActive {
                Label(activeLabel, systemImage: "checkmark")
            } else {
                Text(selectLabel)
            }
        }
        .omButton(provider.isActive ? .ghost : .primary, size: .small)
        .disabled(!selectable)
    }
}
