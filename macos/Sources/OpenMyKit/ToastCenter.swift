import Foundation
import Observation

/// 一条 Toast 消息。id 用于 SwiftUI 列表 diff 与手动消除。
public struct ToastMessage: Identifiable, Equatable, Sendable {
    public let id: UUID
    public let text: String

    public init(id: UUID = UUID(), text: String) {
        self.id = id
        self.text = text
    }
}

/// 全局 Toast 中心。后续所有波次共用：调 show(_:) 弹一条，自动消失。
///
/// 自动消失用计数令牌而非 Timer，避免单测依赖真实时钟：
/// 每条消息排一个延时任务，到点时只有令牌仍匹配才移除（防止被 dismiss/replace 误删后又被旧任务移除）。
@MainActor
@Observable
public final class ToastCenter {
    /// 当前在屏的 Toast 列表（按加入顺序）。
    public private(set) var toasts: [ToastMessage] = []

    /// 每条消息的自动消失延时（秒）。0 或负数表示不自动消失（测试用）。
    public let autoDismissSeconds: Double

    public init(autoDismissSeconds: Double = 3.0) {
        self.autoDismissSeconds = autoDismissSeconds
    }

    /// 弹一条 Toast。返回消息 id，便于调用方手动消除。
    @discardableResult
    public func show(_ text: String) -> UUID {
        let message = ToastMessage(text: text)
        toasts.append(message)
        scheduleDismiss(message.id)
        return message.id
    }

    /// 手动消除一条。
    public func dismiss(_ id: UUID) {
        toasts.removeAll { $0.id == id }
    }

    /// 清空所有。
    public func clear() {
        toasts.removeAll()
    }

    private func scheduleDismiss(_ id: UUID) {
        guard autoDismissSeconds > 0 else { return }
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(self?.autoDismissSeconds ?? 3.0))
            self?.dismiss(id)
        }
    }
}
