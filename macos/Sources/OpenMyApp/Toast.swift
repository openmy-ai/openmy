import SwiftUI
import OpenMyKit

/// 单条 Toast 气泡。实色弹层表面 + 1px 描边分层，底部居中浮层用，深浅模式自适应。
struct ToastBubble: View {
    let message: ToastMessage

    var body: some View {
        Text(message.text)
            .font(Theme.Typography.body)
            .foregroundStyle(Theme.Palette.primaryText)
            .multilineTextAlignment(.leading)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, Theme.Spacing.lg)
            .padding(.vertical, Theme.Spacing.md)
            .background(Theme.Palette.popover)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .strokeBorder(Theme.Palette.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
            .shadow(color: .black.opacity(0.22), radius: 6, y: 2)
            // 上限约 360，过长文案换行而非横铺整窗。
            .frame(maxWidth: 360)
    }
}

/// Toast 浮层：把环境里的 ToastCenter 当前消息叠在内容底部居中。
struct ToastHostModifier: ViewModifier {
    @Environment(ToastCenter.self) private var toastCenter

    func body(content: Content) -> some View {
        content
            .overlay(alignment: .bottom) {
                VStack(spacing: Theme.Spacing.sm) {
                    ForEach(toastCenter.toasts) { message in
                        ToastBubble(message: message)
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                            .onTapGesture { toastCenter.dismiss(message.id) }
                    }
                }
                .padding(.bottom, Theme.Spacing.xxl)
                .animation(.spring(duration: 0.3), value: toastCenter.toasts)
            }
    }
}

extension View {
    /// 在内容底部挂载全局 Toast 浮层。需先在环境注入 ToastCenter。
    func toastHost() -> some View {
        modifier(ToastHostModifier())
    }
}
