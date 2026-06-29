#if canImport(SwiftUI)
import SwiftUI
#if canImport(AppKit)
import AppKit
#endif

/// OpenMy 设计系统：集中管理颜色、间距、圆角、字号等设计 token，
/// 以及卡片、徽章、按钮等可复用样式。设计语言对齐 Linear（密度与克制）：
/// 暗色用三层实色表面递进（背景 → 卡片 → 弹层）+ 极细低透明描边分层，
/// 不靠阴影；唯一品牌色为 Linear 靛蓝，元数据一律走灰阶；四级灰阶承载信息密度。
///
/// 所有视图 `import OpenMyKit` 后通过 `Theme.xxx` 取 token，
/// 用 `.omCard()` 套卡片样式、`.omButton(.primary)` 套统一按钮样式、
/// `.omRow()` 套列表行 hover/选中样式，不再各自硬编码间距、圆角、字号、按钮，
/// 杜绝风格漂移。
public enum Theme {

    // MARK: - 间距

    /// 间距刻度（4 的倍数，对齐 Tailwind / Linear 的 4px 基刻度）。
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
        /// 6：小元素 / 内嵌 / 列表行
        public static let sm: CGFloat = 6
        /// 8：按钮 / 输入框
        public static let md: CGFloat = 8
        /// 10：卡片
        public static let lg: CGFloat = 10
        /// 14：大容器 / sheet
        public static let xl: CGFloat = 14
        /// 12：命令面板 / 弹层（比 xl 收一档，更贴近 Linear 的弹层圆角）。
        public static let panel: CGFloat = 12
        /// 胶囊：徽章 / 标签
        public static let pill: CGFloat = 999

        /// 兼容旧名（= lg 10）。
        public static let card: CGFloat = 10
        /// 兼容旧名（= xl 14）。
        public static let container: CGFloat = 14
    }

    // MARK: - 行高（布局参照，不参与 Spacing/Radius 体系）

    /// 列表 / 导航行高建议常量，对齐 Linear 的 28–40 行密度。
    /// 仅作布局参照，视图按需取用。
    public enum RowHeight {
        /// 侧栏导航行（Linear 28–32）。
        public static let nav: CGFloat = 30
        /// 侧栏日报列表行。
        public static let dateList: CGFloat = 32
        /// 通用列表行（单行）。
        public static let list: CGFloat = 34
        /// 列表行（含副标题）。
        public static let listDetail: CGFloat = 40
        /// 校正词典行。
        public static let correction: CGFloat = 38
    }

    // MARK: - 颜色

    /// 语义颜色，深浅模式各一套精确值。
    /// 暗色采用 Linear 实测的更深更冷分层（`08→0F→16→19→1F`），
    /// hex 以 0xRRGGBBAA 表示，含 alpha。
    public enum Palette {
        // 表面层级（背景 → 侧栏 → 卡片 → 弹层，实色递进，靠底色差 + 细描边撑纵深）
        /// 窗口最底背景。
        public static let background = Color(omLight: 0xFFFFFFFF, omDark: 0x08090AFF)
        /// 侧栏 / 导航面板（比内容区略高一档）。
        public static let surfacePanel = Color(omLight: 0xF7F8F8FF, omDark: 0x0F1011FF)
        /// 弱化底色（次级区块 / skeleton 占位 / 分段控件轨道）。
        public static let muted = Color(omLight: 0xF0F1F2FF, omDark: 0x16181AFF)
        /// 卡片 / 列表容器背景。
        public static let card = Color(omLight: 0xFFFFFFFF, omDark: 0x191A1BFF)
        /// 弹层 / sheet / 菜单背景。
        public static let popover = Color(omLight: 0xFFFFFFFF, omDark: 0x1F2023FF)

        // 交互底色（半透明叠加，跟随表面层级自适应）
        /// 行 / 侧栏项 hover 微底（黑 3% / 白 4%）。
        public static let rowHover = Color(omLight: 0x00000008, omDark: 0xFFFFFF0A)
        /// 选中态底（accent 微底，靛蓝 ~12% / 14%）。
        public static let selectedSurface = Color(omLight: 0x5E6AD21F, omDark: 0x7C8AFF24)
        /// 透明按钮按下态底（黑 6% / 白 8% 叠加，克制减重）。
        public static let accentSurface = Color(omLight: 0x0000000F, omDark: 0xFFFFFF14)

        // 文字（四级灰阶承载信息密度）
        /// 主文（真正重要内容）。
        public static let primaryText = Color(omLight: 0x08090AFF, omDark: 0xF7F8F8FF)
        /// 强次文（标题旁活跃辅助，第四级，可选）。
        public static let brightText = Color(omLight: 0x2C2E33FF, omDark: 0xD0D6E0FF)
        /// 次文（承载大量辅助信息，冷灰）。
        public static let secondaryText = Color(omLight: 0x5A5F6BFF, omDark: 0x8A8F98FF)
        /// 三级最弱（时间戳 / 占位 / 分组头）。
        public static let tertiaryText = Color(omLight: 0x8A8F98FF, omDark: 0x62666DFF)

        // 描边（压到 Linear 的 2%–8%）
        /// 行内极细分隔（黑 3% / 白 2%）。
        public static let borderMicro = Color(omLight: 0x00000008, omDark: 0xFFFFFF05)
        /// 次级分隔 / 列表分隔线（黑 6% / 白 5%）。
        public static let borderSubtle = Color(omLight: 0x0000000F, omDark: 0xFFFFFF0D)
        /// 通用描边。
        public static let border = Color(omLight: 0xE8E9EBFF, omDark: 0xFFFFFF14)
        /// 输入框描边。
        public static let input = Color(omLight: 0xE8E9EBFF, omDark: 0xFFFFFF1F)
        /// 聚焦环（accent 靛蓝 40%，对齐 Linear focus ring）。
        public static let ring = Color(omLight: 0x5E6AD266, omDark: 0x7C8AFF66)

        // 按钮主色（shadcn primary：浅色=近黑底白字，深色反转=浅底黑字，保持高对比单色）
        /// 主按钮底。
        public static let primary = Color(omLight: 0x171717FF, omDark: 0xE5E5E5FF)
        /// 主按钮文字。
        public static let primaryForeground = Color(omLight: 0xFAFAFAFF, omDark: 0x171717FF)
        /// 次按钮底（暗色轻调以贴合新表面）。
        public static let secondary = Color(omLight: 0xF1F1F1FF, omDark: 0x232425FF)
        /// 次按钮文字。
        public static let secondaryForeground = Color(omLight: 0x171717FF, omDark: 0xFAFAFAFF)

        // 强调色（Linear 靛蓝，全 app 唯一品牌色，克制使用）
        /// 唯一品牌色（选中 / 焦点 / 品牌标记 / 拖拽提示 / 进度填充 / 搜索命中）。
        /// 暗色取更亮的 `#7C8AFF` 保证暗底文字对比。
        public static let accent = Color(omLight: 0x5E6AD2FF, omDark: 0x7C8AFFFF)
        /// 强调色 hover 态（Linear accent.hover）。
        public static let accentHover = Color(omLight: 0x828FFFFF, omDark: 0x939DFFFF)
        /// 强调色按下态（Linear accent.active）。
        public static let accentActive = Color(omLight: 0x4B57C8FF, omDark: 0x4B57C8FF)

        // 语义状态（低饱和：同色 14% 底 + 同色文字 / 状态点，不做满饱和实色块）
        /// 失败 / 危险。
        public static let danger = Color(omLight: 0xDC2626FF, omDark: 0xE5484DFF)
        /// 成功（步骤完成）。
        public static let success = Color(omLight: 0x16A34AFF, omDark: 0x3FB950FF)
        /// 警告（需要注意，例如缺 API Key）。
        public static let warning = Color(omLight: 0xB45309FF, omDark: 0xE0A23CFF)

        /// 兼容旧名（= card）。
        public static let cardBackground = card
    }

    // MARK: - 字体

    /// 语义字体，精确 size + weight（mac 用 SF Pro，密度对齐 Linear）。
    /// 标题的字距（tracking）见 `Theme.Tracking`，需在 `Text` 上链式施加。
    public enum Typography {
        /// 页面大标题（配合 `Tracking.pageTitle`）。
        public static let pageTitle = Font.system(size: 22, weight: .semibold)
        /// 区块标题（配合 `Tracking.sectionTitle`）。
        public static let sectionTitle = Font.system(size: 15, weight: .semibold)
        /// 卡片标题（配合 `Tracking.cardTitle`）。
        public static let cardTitle = Font.system(size: 14, weight: .semibold)
        /// 正文（密集 UI 主力）。
        public static let body = Font.system(size: 13, weight: .regular)
        /// 内容正文（Linear 14 内容档，可选）。
        public static let bodyLarge = Font.system(size: 14, weight: .regular)
        /// 按钮 / 标签（中等字重）。
        public static let label = Font.system(size: 13, weight: .medium)
        /// 次要说明。
        public static let caption = Font.system(size: 12, weight: .regular)
        /// 更小的辅助说明 / 徽章 / 标签（medium 更清晰）。
        public static let caption2 = Font.system(size: 11, weight: .medium)
        /// 数值（统计大数字，配合 `Tracking.metric`）。
        public static let metric = Font.system(size: 20, weight: .semibold)
    }

    // MARK: - 字距

    /// 标题字距常量（SwiftUI `Font` 无内建 tracking，需在 `Text` 上链式施加）。
    /// 用法：`Text(title).font(Theme.Typography.sectionTitle).tracking(Theme.Tracking.sectionTitle)`，
    /// 或便捷修饰 `Text(title).omTitle(Theme.Typography.sectionTitle, tracking: Theme.Tracking.sectionTitle)`。
    /// 正文 `body` / `caption` 不加 tracking（保持 0）。
    public enum Tracking {
        /// 页面大标题（-0.4，Linear 式收紧）。
        public static let pageTitle: CGFloat = -0.4
        /// 区块标题（-0.2）。
        public static let sectionTitle: CGFloat = -0.2
        /// 卡片标题（-0.1）。
        public static let cardTitle: CGFloat = -0.1
        /// 数值（-0.4）。
        public static let metric: CGFloat = -0.4
    }
}

// MARK: - 颜色工具：深浅模式精确 hex

extension Color {
    /// 按系统外观切换的动态颜色，浅色 / 深色各传一个 0xRRGGBBAA。
    /// 对齐 Linear 的 light/dark 两套精确值，而非依赖系统语义色。
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

// MARK: - 标题字距便捷修饰

extension Text {
    /// 一次施加字体 + 字距，避免标题漏加 tracking。
    /// 例：`Text(t).omTitle(Theme.Typography.sectionTitle, tracking: Theme.Tracking.sectionTitle)`。
    public func omTitle(_ font: Font, tracking: CGFloat) -> some View {
        self.font(font).tracking(tracking)
    }
}

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
    /// 幽灵危险：透明底 + 红字，行内低调的破坏操作（移除 / 拒绝），比红实底克制。
    case ghostDanger
    /// 危险：红底，用于 sheet / 弹层级的破坏主操作。
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
/// 按变体决定底色 / 文字 / 边框，按下、hover 与禁用有一致反馈。
public struct OMButtonStyle: ButtonStyle {
    let variant: OMButtonVariant
    let size: OMButtonSize
    @Environment(\.isEnabled) private var isEnabled

    public init(variant: OMButtonVariant = .primary, size: OMButtonSize = .regular) {
        self.variant = variant
        self.size = size
    }

    public func makeBody(configuration: Configuration) -> some View {
        // 用内嵌 View 承载 @State，让 hover 态可驱动刷新（ButtonStyle 结构体自身的
        // @State 不参与视图更新）。签名与变体 / 尺寸映射保持不变。
        OMButtonStyleBody(
            configuration: configuration,
            variant: variant,
            size: size,
            isEnabled: isEnabled
        )
    }
}

/// `OMButtonStyle` 的实际渲染体：承载 hover 态并按变体叠加底色。
private struct OMButtonStyleBody: View {
    let configuration: ButtonStyleConfiguration
    let variant: OMButtonVariant
    let size: OMButtonSize
    let isEnabled: Bool
    @State private var hovering = false

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
        case .ghostDanger: return Theme.Palette.danger
        case .destructive: return Color(omRGBA: 0xFAFAFAFF)
        }
    }

    private var background: Color {
        switch variant {
        case .primary: return Theme.Palette.primary
        case .secondary: return Theme.Palette.secondary
        case .destructive: return Theme.Palette.danger
        case .outline, .ghost, .ghostDanger: return .clear
        }
    }

    private var borderColor: Color {
        switch variant {
        case .outline: return Theme.Palette.border
        default: return .clear
        }
    }

    /// 透明 / 弱底变体走 hover 微底 + 按下 accentSurface；实底变体走按下压暗。
    private var isOverlayVariant: Bool {
        variant == .outline || variant == .ghost || variant == .ghostDanger || variant == .secondary
    }

    /// 叠在变体底色之上、标签之下的交互高亮层。
    private var overlayTint: Color {
        if isOverlayVariant {
            if configuration.isPressed { return Theme.Palette.accentSurface }
            return hovering ? Theme.Palette.rowHover : .clear
        }
        // 实底变体：按下压暗一层（由 0.16 降到 0.08）。
        return Color.black.opacity(configuration.isPressed ? 0.08 : 0)
    }

    var body: some View {
        configuration.label
            .font(Theme.Typography.label)
            .foregroundStyle(foreground)
            .frame(height: height)
            .frame(minWidth: size == .icon ? height : nil)
            .padding(.horizontal, hPadding)
            // 底色 + 交互高亮同层（ZStack 让高亮在底色之上、标签之下），
            // 实底变体按下也能正确压暗。
            .background(
                ZStack {
                    background
                    overlayTint
                }
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .strokeBorder(borderColor, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
            .opacity(isEnabled ? 1 : 0.45)
            .contentShape(Rectangle())
            .onHover { hovering = $0 }
            .animation(.easeOut(duration: 0.12), value: hovering)
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

/// 列表行 hover / 选中高亮修饰符：扁平行（无描边）+ hover 微底 + 选中 accent 微底。
/// 行间分隔交给调用方用 `Divider().overlay(Theme.Palette.borderSubtle)` 或纯间距，
/// 不再每行套卡片。选中态优先级高于 hover。
public struct RowHighlightModifier: ViewModifier {
    @State private var hovering = false
    private let isSelected: Bool
    private let minHeight: CGFloat

    public init(isSelected: Bool, minHeight: CGFloat) {
        self.isSelected = isSelected
        self.minHeight = minHeight
    }

    private var rowBackground: Color {
        if isSelected { return Theme.Palette.selectedSurface }
        return hovering ? Theme.Palette.rowHover : .clear
    }

    public func body(content: Content) -> some View {
        content
            .padding(.horizontal, Theme.Spacing.md)
            .padding(.vertical, Theme.Spacing.sm)
            .frame(maxWidth: .infinity, minHeight: minHeight, alignment: .leading)
            .background(rowBackground)
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.sm))
            .contentShape(Rectangle())
            .onHover { hovering = $0 }
            .animation(.easeOut(duration: 0.12), value: hovering)
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

    /// 套用列表行 hover / 选中样式（扁平行 + 微底高亮）。
    /// 例：`HStack { ... }.omRow(isSelected: isCurrent)`。
    public func omRow(isSelected: Bool = false, minHeight: CGFloat = 34) -> some View {
        modifier(RowHighlightModifier(isSelected: isSelected, minHeight: minHeight))
    }
}

// MARK: - 输入框样式

/// 纳入设计系统的扁平输入框样式：`muted` 底 + 1px `input` 边 + `Radius.md` 圆角。
/// 用法：`TextField("…", text: $x).textFieldStyle(OMTextFieldStyle())`，
/// 替换所有 `.textFieldStyle(.roundedBorder)`。聚焦环见 `OMTextField`（带 @FocusState）。
public struct OMTextFieldStyle: TextFieldStyle {
    public init() {}

    public func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .textFieldStyle(.plain)
            .font(Theme.Typography.body)
            .foregroundStyle(Theme.Palette.primaryText)
            .padding(.horizontal, Theme.Spacing.md)
            .padding(.vertical, Theme.Spacing.sm)
            .background(Theme.Palette.muted)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .strokeBorder(Theme.Palette.input, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
    }
}

/// 视图封装的输入框：在 `OMTextFieldStyle` 基础上加聚焦态——
/// 聚焦时描边换 `accent` 并叠 2px 半透明聚焦环 `ring`。
public struct OMTextField: View {
    private let titleKey: String
    @Binding private var text: String
    @FocusState private var focused: Bool

    public init(_ titleKey: String, text: Binding<String>) {
        self.titleKey = titleKey
        self._text = text
    }

    public var body: some View {
        TextField(titleKey, text: $text)
            .textFieldStyle(.plain)
            .font(Theme.Typography.body)
            .foregroundStyle(Theme.Palette.primaryText)
            .focused($focused)
            .padding(.horizontal, Theme.Spacing.md)
            .padding(.vertical, Theme.Spacing.sm)
            .background(Theme.Palette.muted)
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .strokeBorder(focused ? Theme.Palette.accent : Theme.Palette.input, lineWidth: 1)
            )
            // 聚焦环：略向外 1.5pt，仅聚焦时可见。
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.md + 1)
                    .stroke(Theme.Palette.ring, lineWidth: focused ? 2 : 0)
                    .padding(-1.5)
            )
            .animation(.easeOut(duration: 0.12), value: focused)
    }
}

// MARK: - 可复用组件

/// 区块标题 + 可选 trailing 操作槽。
/// 标题 `sectionTitle(15 semibold)` + 负字距 + `primaryText`，trailing 放 ghost 小按钮。
/// 不再给每个区块套圆角填充块——标题下直接接列表 / 内容。
public struct OMSectionHeader<Trailing: View>: View {
    private let title: String
    private let trailing: Trailing

    public init(_ title: String, @ViewBuilder trailing: () -> Trailing) {
        self.title = title
        self.trailing = trailing()
    }

    public var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.sm) {
            Text(title)
                .font(Theme.Typography.sectionTitle)
                .tracking(Theme.Tracking.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Spacer(minLength: Theme.Spacing.sm)
            trailing
        }
        .padding(.bottom, Theme.Spacing.sm)
    }
}

extension OMSectionHeader where Trailing == EmptyView {
    /// 无 trailing 操作的区块标题。
    public init(_ title: String) {
        self.init(title) { EmptyView() }
    }
}

/// 轻量分组标签（侧栏分组头 / 区块小标题）。
/// `caption2(11 medium)` + `tertiaryText` + 正字距。
public struct OMGroupLabel: View {
    private let text: String

    public init(_ text: String) {
        self.text = text
    }

    public var body: some View {
        Text(text)
            .font(Theme.Typography.caption2)
            .tracking(0.3)
            .foregroundStyle(Theme.Palette.tertiaryText)
            .padding(.vertical, Theme.Spacing.xs)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// 侧栏导航行：SF Symbol 图标 + 标题 + 可选行尾快捷键提示，带 hover / 选中态。
/// 选中：`selectedSurface` 底 + 标题 `primaryText` + 图标染 `accent`；
/// hover：`rowHover` 底 + 标题转 `primaryText`；默认：透明底 + `secondaryText`。
public struct OMNavRow: View {
    private let icon: String
    private let title: String
    private let isSelected: Bool
    private let shortcut: String?
    private let action: () -> Void
    @State private var hovering = false

    public init(
        icon: String,
        title: String,
        isSelected: Bool = false,
        shortcut: String? = nil,
        action: @escaping () -> Void
    ) {
        self.icon = icon
        self.title = title
        self.isSelected = isSelected
        self.shortcut = shortcut
        self.action = action
    }

    private var titleColor: Color {
        if isSelected { return Theme.Palette.primaryText }
        return hovering ? Theme.Palette.primaryText : Theme.Palette.secondaryText
    }

    private var iconColor: Color {
        isSelected ? Theme.Palette.accent : titleColor
    }

    private var rowBackground: Color {
        if isSelected { return Theme.Palette.selectedSurface }
        return hovering ? Theme.Palette.rowHover : .clear
    }

    public var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: icon)
                    .font(.system(size: 13))
                    .frame(width: 16)
                    .foregroundStyle(iconColor)
                Text(title)
                    .font(Theme.Typography.label)
                    .foregroundStyle(titleColor)
                Spacer(minLength: Theme.Spacing.sm)
                if let shortcut {
                    Text(shortcut)
                        .font(Theme.Typography.caption2)
                        .foregroundStyle(Theme.Palette.tertiaryText)
                }
            }
            // 水平内边距 ~10（sm + xxs）。
            .padding(.horizontal, Theme.Spacing.sm + Theme.Spacing.xxs)
            .frame(height: Theme.RowHeight.nav)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(rowBackground)
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.sm))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
        .animation(.easeOut(duration: 0.12), value: hovering)
    }
}

/// 语义状态徽章（低饱和）：同色 14% 底 + 同色文字，或状态点 + 文字。
/// 配色映射：success/warning/danger/accent 各取对应 Palette，neutral 走 `secondaryText` + `muted` 底。
/// `dot: true` 时前置实心圆并省略填充底（Linear 更常见的状态点样式）。
public struct OMStatusBadge: View {
    public enum Status {
        case success, warning, danger, accent, neutral
    }

    private let text: String
    private let status: Status
    private let dot: Bool

    public init(_ text: String, status: Status = .neutral, dot: Bool = false) {
        self.text = text
        self.status = status
        self.dot = dot
    }

    private var color: Color {
        switch status {
        case .success: return Theme.Palette.success
        case .warning: return Theme.Palette.warning
        case .danger: return Theme.Palette.danger
        case .accent: return Theme.Palette.accent
        case .neutral: return Theme.Palette.secondaryText
        }
    }

    private var backgroundFill: Color {
        if dot { return .clear }
        return status == .neutral ? Theme.Palette.muted : color.opacity(0.14)
    }

    public var body: some View {
        HStack(spacing: Theme.Spacing.xs) {
            if dot {
                Circle()
                    .fill(color)
                    .frame(width: 6, height: 6)
            }
            Text(text)
                .font(Theme.Typography.caption2)
                .foregroundStyle(color)
        }
        .padding(.horizontal, Theme.Spacing.sm)
        .padding(.vertical, Theme.Spacing.xxs)
        .background(backgroundFill)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.sm))
    }
}

/// 小徽章（标签 / 推荐 / 本地云端标记）。统一样式。
/// 向后兼容保留；新代码优先用 `OMStatusBadge`。
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
            Text(value)
                .font(Theme.Typography.metric)
                .tracking(Theme.Tracking.metric)
                .foregroundStyle(Theme.Palette.primaryText)
            Text(label)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
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
