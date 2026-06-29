import Foundation

/// 角色配色归一化键：把后端 role.category（中英混杂、口径不一）归到有限枚举，供视图取色。
/// 对齐 daily.js normalizeRoleKey 的映射，并补充 uncertain/other 两类（Web 端归 '' 的统一兜底）。
public enum RoleColorKey: String, CaseIterable, Sendable, Equatable {
    case ai
    case merchant
    case pet
    case `self`
    case interpersonal
    case uncertain
    case other

    /// 从原始 category 字符串归一化。空/无法识别归 other；显式不确定归 uncertain。
    public static func from(_ raw: String) -> RoleColorKey {
        let normalized = raw.trimmingCharacters(in: .whitespaces).lowercased()
        guard !normalized.isEmpty else { return .other }

        if normalized == "ai" || normalized.contains("ai助手") || normalized == "助手" {
            return .ai
        }
        if normalized == "merchant" || containsAny(normalized, ["商家", "服务员", "客服"]) {
            return .merchant
        }
        if normalized == "pet" || normalized.contains("宠物") {
            return .pet
        }
        if normalized == "self" || containsAny(normalized, ["自己", "自言自语", "备忘"]) {
            return .self
        }
        if normalized == "interpersonal"
            || containsAny(normalized, ["伴侣", "家人", "朋友", "同事", "聊天", "人际"]) {
            return .interpersonal
        }
        if normalized == "uncertain" || containsAny(normalized, ["不确定", "未知", "无法识别"]) {
            return .uncertain
        }
        return .other
    }

    private static func containsAny(_ haystack: String, _ needles: [String]) -> Bool {
        needles.contains { haystack.contains($0) }
    }
}
