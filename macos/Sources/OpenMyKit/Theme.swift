#if canImport(SwiftUI)
import SwiftUI
#if canImport(AppKit)
import AppKit
#endif

/// OpenMy 设计系统：集中管理颜色、间距、圆角、字号等设计 token，
/// 以及卡片、徽章、按钮等可复用样式。设计语言对齐 shadcn/ui（neutral 灰阶 +
/// 语义层级 + 统一圆角），让深浅模式都有清晰的表面层次，避免“层次全平”。
///
/// 所有视图 `import OpenMyKit` 后通过 `Theme.xxx` 取 token，
/// 用 `.omCard()` 套卡片样式、`.omButton(.primary)` 套统一按钮样式，
/// 不再各自硬编码间距、圆角、字号、按钮，杜绝风格漂移。
public enum Theme {

    // MARK: - 间距

    /// 间距刻度（4 的倍数，对齐 Tailwind spacing 基刻度）。
    public enum Spacing {
        /// 2
        public static let xxs: CGFloat = 2
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

    /// 圆角刻度（对齐 shadcn `--radius: 0.625rem` = 10pt 体系）。
    public enum Radius {
        /// 2：极小标记
        public static let xs: CGFloat = 2
        /// 6：小元素 / 内嵌
        public static let sm: CGFloat = 6
        /// 8：按钮 / 输入框
        public static let md: CGFloat = 8
        /// 10：卡片
        public static let lg: CGFloat = 10
        /// 14：大容器 / sheet
        public static let xl: CGFloat = 14
        /// 胶囊：徽章 / 标签
        public static let pill: CGFloat = 999

        /// 兼容旧名（= lg 10）。
        public static let card: CGFloat = 10
        /// 兼容旧名（= xl 14）。
        public static let container: CGFloat = 14
    }

    // MARK: - 颜色

    /// 语义颜色，深浅模式各一套精确值（对齐 shadcn neutral 调色板）。
    /// hex 以 0xRRGGBBAA 表示，含 alpha。
    public enum Palette {
        // 表面层级（背景 → 卡片 → 弹层，明度递进，撑起纵深）
        /// 页面背景。
        public static let background = Color(omLight: 0xFFFFFFFF, omDark: 0x0A0A0AFF)
        /// 卡片 / 面板背景。
        public static let card = Color(omLight: 0xFFFFFFFF, omDark: 0x171717FF)
        /// 弹层 / sheet 背景。
        public static let popover = Color(omLight: 0xFFFFFFFF, omDark: 0x1C1C1CFF)
        /// 弱化底色（次级区块 / 占位）。
        public static let muted = Color(omLight: 0xF5F5F5FF, omDark: 0x262626FF)
        /// 强调底色（hover / 选中行）。
        public static let accentSurface = Color(omLight: 0xF0F0F0FF, omDark: 0x404040FF)

        // 文字
        /// 主文字。
        public static let primaryText = Color(omLight: 0x0A0A0AFF, omDark: 0xFAFAFAFF)
        /// 次要文字（muted-foreground）。
        public static let secondaryText = Color(omLight: 0x737373FF, omDark: 0xA1A1A1FF)

        // 描边
        /// 通用描边。
        public static let border = Color(omLight: 0xE5E5E5FF, omDark: 0xFFFFFF1F)
        /// 输入框描边。
        public static let input = Color(omLight: 0xE5E5E5FF, omDark: 0xFFFFFF26)
        /// 聚焦环。
        public static let ring = Color(omLight: 0x737373FF, omDark: 0xA1A1A1FF)

        // 按钮主色（shadcn primary：浅色=近黑底白字，深色反转=浅底黑字）
        /// 主按钮底。
        public static let primary = Color(omLight: 0x171717FF, omDark: 0xE5E5E5FF)
        /// 主按钮文字。
        public static let primaryForeground = Color(omLight: 0xFAFAFAFF, omDark: 0x171717FF)
        /// 次按钮底。
        public static let secondary = Color(omLight: 0xF1F1F1FF, omDark: 0x2A2A2AFF)
        /// 次按钮文字。
        public static let secondaryForeground = Color(omLight: 0x171717FF, omDark: 0xFAFAFAFF)

        // 语义状态
        /// 强调 / 品牌（链接、选中、关键操作）。
        public static let accent = Color(omLight: 0x2563EBFF, omDark: 0x60A5FAFF)
        /// 失败 / 危险。
        public static let danger = Color(omLight: 0xDC2626FF, omDark: 0xFF6568FF)
        /// 成功（步骤完成）。
        public static let success = Color(omLight: 0x15803DFF, omDark: 0x4ADE80FF)
        /// 警告（需要注意，例如缺 API Key）。
        public static let warning = Color(omLight: 0xB45309FF, omDark: 0xFBBF24FF)

        /// 兼容旧名（= card）。
        public static let cardBackground = card
    }

    // MARK: - 字体

    /// 语义字体，精确 size + weight（mac 用 SF Pro，密度对齐原生）。
    public enum Typography {
        /// 页面大标题。
        public static let pageTitle = Font.system(size: 26, weight: .bold)
        /// 区块标题。
        public static let sectionTitle = Font.system(size: 18, weight: .semibold)
        /// 卡片标题。
        public static let cardTitle = Font.system(size: 14, weight: .semibold)
        /// 正文。
        public static let body = Font.system(size: 13, weight: .regular)
        /// 按钮 / 标签（中等字重）。
        public static let label = Font.system(size: 13, weight: .medium)
        /// 次要说明。
        public static let caption = Font.system(size: 12, weight: .regular)
        /// 更小的辅助说明。
        public static let caption2 = Font.system(size: 11, weight: .regular)
        /// 数值（统计大数字）。
        public static let metric = Font.system(size: 24, weight: .semibold)
    }
}

// MARK: - 颜色工具：深浅模式精确 hex

extension Color {
    /// 按系统外观切换的动态颜色，浅色 / 深色各传一个 0xRRGGBBAA。
    /// 对齐 shadcn 的 light/dark 两套精确值，而非依赖系统语义色。
    init(omLight light: UInt32, omDark dark: UInt32) {
        #if canImport(AppKit)
        self = Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
            return NSColor(omRGBA: isDark ? dark : light)
        })
        #else
        self = Color(omRGBA: light)
        #endif
    }

    /// 从 0xRRGGBBAA 构造（无外观切换时的兜底）。
    init(omRGBA rgba: UInt32) {
        self = Color(
            .sRGB,
            red: Double((rgba >> 24) & 0xFF) / 255,
            green: Double((rgba >> 16) & 0xFF) / 255,
            blue: Double((rgba >> 8) & 0xFF) / 255,
            opacity: Double(rgba & 0xFF) / 255
        )
    }
}

#if canImport(AppKit)
extension NSColor {
    /// 从 0xRRGGBBAA 构造 sRGB 颜色。
    convenience init(omRGBA rgba: UInt32) {
        self.init(
            srgbRed: CGFloat((rgba >> 24) & 0xFF) / 255,
            green: CGFloat((rgba >> 16) & 0xFF) / 255,
            blue: CGFloat((rgba >> 8) & 0xFF) / 255,
            alpha: CGFloat(rgba & 0xFF) / 255
        )
    }
}
#endif

// MARK: - 统一按钮样式（shadcn 变体）

/// 按钮变体，对齐 shadcn：default / secondary / outline / ghost / destructive。
public enum OMButtonVariant {
    /// 主操作：实底高对比。
    case primary
    /// 次操作：弱底。
    case secondary
    /// 描边：透明底 + 边框。
    case outline
    /// 幽灵：透明底，hover 才有底（图标 / 文字按钮）。
    case ghost
    /// 危险：红底。
    case destructive
}

/// 按钮尺寸。
public enum OMButtonSize {
    /// 常规（高 30）。
    case regular
    /// 紧凑（高 26）。
    case small
    /// 图标（28×28 正方）。
    case icon
}

/// 统一按钮样式：固定圆角(md=8)、字号(label=13 medium)、高度、内边距，
/// 按变体决定底色 / 文字 / 边框，按下与禁用有一致反馈。
public struct OMButtonStyle: ButtonStyle {
    let variant: OMButtonVariant
    let size: OMButtonSize
    @Environment(\.isEnabled) private var isEnabled

    public init(variant: OMButtonVariant = .primary, size: OMButtonSize = .regular) {
        self.variant = variant
        self.size = size
    }

    private var height: CGFloat {
        switch size {
        case .regular: return 30
        case .small: return 26
        case .icon: return 28
        }
    }

    private var hPadding: CGFloat {
        switch size {
        case .regular: return Theme.Spacing.md
        case .small: return Theme.Spacing.sm
        case .icon: return 0
        }
    }

    private var foreground: Color {
        switch variant {
        case .primary: return Theme.Palette.primaryForeground
        case .secondary: return Theme.Palette.secondaryForeground
        case .outline, .ghost: return Theme.Palette.primaryText
        case .destructive: return Color(omRGBA: 0xFAFAFAFF)
        }
    }

    private var background: Color {
        switch variant {
        case .primary: return Theme.Palette.primary
        case .secondary: return Theme.Palette.secondary
        case .destructive: return Theme.Palette.danger
        case .outline, .ghost: return .clear
        }
    }

    private var borderColor: Color {
        switch variant {
        case .outline: return Theme.Palette.border
        default: return .clear
        }
    }

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.Typography.label)
            .foregroundStyle(foreground)
            .frame(height: height)
            .frame(minWidth: size == .icon ? height : nil)
            .padding(.horizontal, hPadding)
            .background(background)
            // 按下 / hover 反馈：透明变体叠 accentSurface，实底变体压暗一层。
            .background(
                (variant == .outline || variant == .ghost)
                    ? Theme.Palette.accentSurface.opacity(configuration.isPressed ? 1 : 0)
                    : Color.black.opacity(configuration.isPressed ? 0.16 : 0)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .strokeBorder(borderColor, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
            .opacity(isEnabled ? 1 : 0.45)
            .contentShape(Rectangle())
    }
}

// MARK: - 可复用样式修饰符

/// 卡片容器样式：统一内边距、背景、圆角与细描边。
public struct CardModifier: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .padding(Theme.Spacing.md)
            .background(Theme.Palette.card)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.lg)
                    .strokeBorder(Theme.Palette.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.lg))
    }
}

/// 区块容器样式：左对齐铺满。
public struct SectionModifier: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

extension View {
    /// 套用统一卡片样式（内边距 + 背景 + 圆角 + 描边）。
    public func omCard() -> some View {
        modifier(CardModifier())
    }

    /// 套用区块容器样式（左对齐铺满）。
    public func omSection() -> some View {
        modifier(SectionModifier())
    }

    /// 套用统一按钮样式。例：`Button("保存") {}.omButton(.primary)`。
    public func omButton(_ variant: OMButtonVariant = .primary, size: OMButtonSize = .regular) -> some View {
        buttonStyle(OMButtonStyle(variant: variant, size: size))
    }
}

// MARK: - 可复用组件

/// 小徽章（标签 / 推荐 / 本地云端标记）。统一样式。
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
            .font(Theme.Typography.caption2)
            .padding(.horizontal, Theme.Spacing.sm)
            .padding(.vertical, Theme.Spacing.xxs)
            .foregroundStyle(kind == .accent ? Theme.Palette.accent : Theme.Palette.secondaryText)
            .background(kind == .accent ? Theme.Palette.accent.opacity(0.14) : Theme.Palette.muted)
            .clipShape(Capsule())
    }
}

/// 统计数值组件：大数字 + 小标签竖排，用于日报头部统计。
public struct OMMetric: View {
    private let value: String
    private let label: String

    public init(value: String, label: String) {
        self.value = value
        self.label = label
    }

    public var body: some View {
        VStack(spacing: Theme.Spacing.xxs) {
            Text(value).font(Theme.Typography.metric)
            Text(label).font(Theme.Typography.caption).foregroundStyle(Theme.Palette.secondaryText)
        }
    }
}

/// 错误提示文字组件：统一红色小字。`nil` 时不渲染。
public struct OMErrorText: View {
    private let message: String?

    public init(_ message: String?) {
        self.message = message
    }

    public var body: some View {
        if let message {
            Text(message)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.danger)
        }
    }
}

#endif
