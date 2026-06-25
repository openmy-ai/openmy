import Foundation

/// 任务与步骤状态到中文文案的映射。
///
/// 纯逻辑、可测试，从视图里抽出来集中维护，避免每个视图各写一套
/// switch，也避免出现 `interrupted` 直接显示英文原值的问题。
public enum JobStatusText {

    /// 任务整体状态文案。未知状态回退为原值（不丢信息）。
    public static func job(_ status: String) -> String {
        switch status {
        case "queued": return "排队中"
        case "running": return "处理中"
        case "paused": return "已暂停"
        case "succeeded": return "已完成"
        case "partial": return "部分完成"
        case "failed": return "失败"
        case "cancelled": return "已取消"
        case "interrupted": return "已中断"
        default: return status
        }
    }

    /// 单个步骤状态文案。
    public static func step(_ status: String) -> String {
        switch status {
        case "pending": return "等待中"
        case "running": return "进行中"
        case "done": return "已完成"
        case "failed": return "失败"
        case "skipped": return "已跳过"
        default: return status
        }
    }
}
