#if canImport(SwiftUI)
import SwiftUI

/// OpenMy 设计系统：集中管理颜色、间距、圆角、字号等设计 token，
/// 以及卡片、区块、徽章等可复用的视图样式。
///
/// 所有视图 `import OpenMyKit` 后通过 `Theme.xxx` 取 token，
/// 通过 `.omCard()` / `.omSection()` 等修饰符套用统一样式，
/// 避免每个视图各自硬编码间距和圆角导致风格漂移。
public enum Theme {

    // MARK: - 间距

    /// 间距刻度。统一的 4 的倍数刻度，避免散落的魔法数字。
    public enum Spacing {
        /// 4
        public static let xs: CGFloat = 4
        /// 8
        public static let sm: CGFloat = 8
        /// 12
        public static let md: CGFloat = 12
        /// 16
        public static let lg: CGFloat = 16
        /// 20
        public static let xl: CGFloat = 20
        /// 28
        public static let xxl: CGFloat = 28
    }

    // MARK: - 圆角

    /// 圆角刻度。
    public enum Radius {
        /// 8：小卡片 / 徽章
        public static let card: CGFloat = 10
        /// 12：拖拽高亮框 / 大容器
        public static let container: CGFloat = 12
        /// 胶囊：标签
        public static let pill: CGFloat = 999
    }

    // MARK: - 颜色

    /// 语义颜色。基于系统语义色，保证浅色 / 深色模式自动适配。
    public enum Palette {
        /// 主强调色（跟随系统 accent / tint）。
        public static let accent = Color.accentColor
        /// 卡片背景：半透明四级填充，浅色深色都不刺眼。
        public static let cardBackground = Color(nsColor: .quaternaryLabelColor).opacity(0.4)
        /// 主文字。
        public static let primaryText = Color.primary
        /// 次要文字。
        public static let secondaryText = Color.secondary
        /// 成功（步骤完成）。
        public static let success = Color.green
        /// 失败 / 错误。
        public static let danger = Color.red
        /// 警告（需要注意，例如缺 API Key）。
        public static let warning = Color.orange
    }

    // MARK: - 字体

    /// 语义字体。集中定义层级，视图不直接写 `.font(.headline)` 等散落调用。
    public enum Typography {
        /// 页面大标题。
        public static let pageTitle = Font.largeTitle.bold()
        /// 区块标题。
        public static let sectionTitle = Font.title3.bold()
        /// 卡片标题。
        public static let cardTitle = Font.headline
        /// 正文。
        public static let body = Font.body
        /// 次要说明。
        public static let caption = Font.caption
        /// 数值（统计大数字）。
        public static let metric = Font.title3.bold()
    }
}

// MARK: - 可复用样式修饰符

/// 卡片容器样式：统一内边距、背景与圆角。
public struct CardModifier: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .padding(Theme.Spacing.md)
            .background(Theme.Palette.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.card))
    }
}

/// 区块容器样式：标题 + 内容的标准纵向布局间距。
public struct SectionModifier: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

extension View {
    /// 套用统一卡片样式（内边距 + 背景 + 圆角）。
    public func omCard() -> some View {
        modifier(CardModifier())
    }

    /// 套用区块容器样式（左对齐铺满）。
    public func omSection() -> some View {
        modifier(SectionModifier())
    }
}

// MARK: - 可复用组件

/// 小徽章（标签 / 推荐 / 本地云端标记）。视图层直接复用，统一样式。
public struct OMBadge: View {
    public enum Kind {
        /// 强调（推荐）。
        case accent
        /// 中性（本地 / 云端等说明）。
        case neutral
    }

    private let text: String
    private let kind: Kind

    public init(_ text: String, kind: Kind = .neutral) {
        self.text = text
        self.kind = kind
    }

    public var body: some View {
        Text(text)
            .font(.caption2)
            .padding(.horizontal, Theme.Spacing.sm)
            .padding(.vertical, Theme.Spacing.xs / 2)
            .foregroundStyle(kind == .accent ? Theme.Palette.accent : Theme.Palette.secondaryText)
            .background(kind == .accent ? Theme.Palette.accent.opacity(0.18) : Color.clear)
            .clipShape(Capsule())
    }
}

/// 统计数值组件：大数字 + 小标签的竖排，用于日报头部统计。
public struct OMMetric: View {
    private let value: String
    private let label: String

    public init(value: String, label: String) {
        self.value = value
        self.label = label
    }

    public var body: some View {
        VStack(spacing: Theme.Spacing.xs / 2) {
            Text(value).font(Theme.Typography.metric)
            Text(label).font(Theme.Typography.caption).foregroundStyle(Theme.Palette.secondaryText)
        }
    }
}

/// 错误提示文字组件：统一红色小字样式。`nil` 时不渲染。
public struct OMErrorText: View {
    private let message: String?

    public init(_ message: String?) {
        self.message = message
    }

    public var body: some View {
        if let message {
            Text(message)
                .font(.footnote)
                .foregroundStyle(Theme.Palette.danger)
        }
    }
}

#endif
