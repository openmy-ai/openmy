import Foundation

/// 屏幕上下文设置：对接 GET/POST /api/settings/screen-context。
///
/// 对齐后端 `ScreenContextSettings.to_dict`（src/openmy/services/screen_recognition/settings.py）：
/// enabled / participation_mode / capture_interval_seconds / screenshot_retention_hours /
/// exclude_apps / exclude_domains / exclude_window_keywords / summary_only_apps / retention_days。
///
/// lenient 解码：缺字段降级默认值；mode 非法值归一到 summary_only（与后端 from_dict 一致）。
/// 保留 `rawDictionary`（原始 JSON 字典），供需要回传"部分字段合并"时取未建模字段。
public struct ScreenContextSettings: Decodable, Equatable, Sendable {
    /// 参与模式：off / summary_only / full。
    public enum Mode: String, CaseIterable, Sendable {
        case off
        case summaryOnly = "summary_only"
        case full

        /// 解析后端字符串，非法值归一到 summary_only（对齐后端 from_dict）。
        public static func parse(_ raw: String?) -> Mode {
            let v = (raw ?? "").trimmingCharacters(in: .whitespaces).lowercased()
            return Mode(rawValue: v) ?? .summaryOnly
        }
    }

    /// 是否启用。后端 mode==off 时强制为 false。
    public let enabled: Bool
    /// 参与模式。
    public let mode: Mode
    /// 截图采集间隔（秒）。
    public let captureIntervalSeconds: Int
    /// 截图保留时长（小时）。
    public let screenshotRetentionHours: Int
    /// 排除的应用名列表。
    public let excludeApps: [String]
    /// 排除的域名列表。
    public let excludeDomains: [String]
    /// 排除的窗口标题关键词列表。
    public let excludeWindowKeywords: [String]
    /// 仅摘要的应用名列表（默认含微信等）。
    public let summaryOnlyApps: [String]
    /// 事件保留天数。
    public let retentionDays: Int

    /// 原始字典：保留后端返回的全部字段，供回传部分字段合并时取未建模值。
    public let rawDictionary: [String: AnyDecodableValue]

    enum CodingKeys: String, CodingKey {
        case enabled
        case participationMode = "participation_mode"
        case captureIntervalSeconds = "capture_interval_seconds"
        case screenshotRetentionHours = "screenshot_retention_hours"
        case excludeApps = "exclude_apps"
        case excludeDomains = "exclude_domains"
        case excludeWindowKeywords = "exclude_window_keywords"
        case summaryOnlyApps = "summary_only_apps"
        case retentionDays = "retention_days"
    }

    public init(
        enabled: Bool = true,
        mode: Mode = .summaryOnly,
        captureIntervalSeconds: Int = 0,
        screenshotRetentionHours: Int = 0,
        excludeApps: [String] = [],
        excludeDomains: [String] = [],
        excludeWindowKeywords: [String] = [],
        summaryOnlyApps: [String] = [],
        retentionDays: Int = 0,
        rawDictionary: [String: AnyDecodableValue] = [:]
    ) {
        self.enabled = enabled
        self.mode = mode
        self.captureIntervalSeconds = captureIntervalSeconds
        self.screenshotRetentionHours = screenshotRetentionHours
        self.excludeApps = excludeApps
        self.excludeDomains = excludeDomains
        self.excludeWindowKeywords = excludeWindowKeywords
        self.summaryOnlyApps = summaryOnlyApps
        self.retentionDays = retentionDays
        self.rawDictionary = rawDictionary
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let parsedMode = Mode.parse(try c.decodeIfPresent(String.self, forKey: .participationMode))
        var en = try c.decodeIfPresent(Bool.self, forKey: .enabled) ?? true
        // 对齐后端：mode==off 强制 enabled=false。
        if parsedMode == .off { en = false }
        enabled = en
        mode = parsedMode
        captureIntervalSeconds = try c.decodeIfPresent(Int.self, forKey: .captureIntervalSeconds) ?? 0
        screenshotRetentionHours = try c.decodeIfPresent(Int.self, forKey: .screenshotRetentionHours) ?? 0
        excludeApps = try c.decodeIfPresent([String].self, forKey: .excludeApps) ?? []
        excludeDomains = try c.decodeIfPresent([String].self, forKey: .excludeDomains) ?? []
        excludeWindowKeywords = try c.decodeIfPresent([String].self, forKey: .excludeWindowKeywords) ?? []
        summaryOnlyApps = try c.decodeIfPresent([String].self, forKey: .summaryOnlyApps) ?? []
        retentionDays = try c.decodeIfPresent(Int.self, forKey: .retentionDays) ?? 0

        // 保留原始字典：单独用动态键容器再解一遍，留作回传合并的兜底。
        if let dynamic = try? decoder.container(keyedBy: AnyDecodableValue.DynamicKey.self) {
            var dict: [String: AnyDecodableValue] = [:]
            for key in dynamic.allKeys {
                if let v = try? dynamic.decode(AnyDecodableValue.self, forKey: key) {
                    dict[key.stringValue] = v
                }
            }
            rawDictionary = dict
        } else {
            rawDictionary = [:]
        }
    }
}

/// 任意 JSON 值的最小可解码包装，仅用于保留 ScreenContextSettings 未建模字段。
/// 支持 bool / int / double / string / 字符串数组 / null，其它形态降级为 null。
public enum AnyDecodableValue: Decodable, Equatable, Sendable {
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case stringArray([String])
    case null

    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() {
            self = .null
        } else if let v = try? c.decode(Bool.self) {
            self = .bool(v)
        } else if let v = try? c.decode(Int.self) {
            self = .int(v)
        } else if let v = try? c.decode(Double.self) {
            self = .double(v)
        } else if let v = try? c.decode(String.self) {
            self = .string(v)
        } else if let v = try? c.decode([String].self) {
            self = .stringArray(v)
        } else {
            self = .null
        }
    }

    /// 任意字符串键，供动态键容器解析原始字典。
    struct DynamicKey: CodingKey {
        var stringValue: String
        var intValue: Int? { nil }
        init?(stringValue: String) { self.stringValue = stringValue }
        init?(intValue: Int) { nil }
    }
}
