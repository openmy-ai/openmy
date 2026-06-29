import Foundation

/// 本地偏好键名（@AppStorage 用）。
///
/// 个人资料与外观在 Web 是纯 localStorage、无后端接口，Swift 用 @AppStorage 本地存。
/// 键名集中在此，避免视图各自硬编码字符串导致漂移或错配。视图侧：
/// `@AppStorage(PreferenceKeys.profileName) var name = ""`。
public enum PreferenceKeys {
    /// 个人资料：显示名字。
    public static let profileName = "openmy.profile.name"
    /// 个人资料：头像 emoji。
    public static let profileEmoji = "openmy.profile.emoji"

    /// 外观：主题（见 AppAppearance.rawValue：system / light / dark）。
    public static let appAppearance = "openmy.appearance.theme"
    /// 外观：强调色（见 AccentColorChoice.rawValue）。
    public static let accent = "openmy.appearance.accent"
    /// 外观：界面语言（如 "zh" / "en"，默认空＝跟随系统）。
    public static let language = "openmy.appearance.language"
}

/// 外观主题选项。rawValue 为持久化字符串，对齐 Web 的 system/light/dark。
public enum AppAppearance: String, CaseIterable, Sendable {
    case system
    case light
    case dark

    /// 默认跟随系统。
    public static let `default`: AppAppearance = .system

    /// 从持久化字符串解析（非法值回退 system）。
    public static func parse(_ raw: String?) -> AppAppearance {
        AppAppearance(rawValue: raw ?? "") ?? .system
    }
}

/// 强调色选项。rawValue 为持久化字符串。
public enum AccentColorChoice: String, CaseIterable, Sendable {
    case blue
    case purple
    case pink
    case orange
    case green
    case graphite

    /// 默认蓝色。
    public static let `default`: AccentColorChoice = .blue

    /// 从持久化字符串解析（非法值回退 blue）。
    public static func parse(_ raw: String?) -> AccentColorChoice {
        AccentColorChoice(rawValue: raw ?? "") ?? .blue
    }
}
