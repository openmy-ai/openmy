import Foundation
import Observation

/// 报告视图模型：持有周报（最近7天）与月报（最近30天）两套聚合结果。
/// 纯聚合无网络：数据由调用方（如 BriefingListViewModel）从 GET /api/dates、GET /api/context 取好后传入，
/// 「今天」基准日期也由外部传入，避免依赖系统时钟（对齐 ReportAggregator 设计）。
@MainActor
@Observable
public final class ReportViewModel {
    /// 周报窗口天数。
    public static let weeklyWindow = 7
    /// 月报窗口天数。
    public static let monthlyWindow = 30

    /// 周报聚合结果（load 前为 nil）。
    public private(set) var weekly: ReportSummary?
    /// 月报聚合结果（load 前为 nil）。
    public private(set) var monthly: ReportSummary?
    /// 活跃项目标题列表（取自 GET /api/context active_projects），供视图直接展示。
    public private(set) var activeProjects: [String] = []

    public init() {}

    /// 用同一批 dates 算周报与月报两套；activeProjects 直接透传项目标题。
    /// - Parameters:
    ///   - dates: 全部日期条目。
    ///   - activeProjects: 活跃项目（取 title，空 title 丢弃）。
    ///   - today: 基准「今天」日期字符串（"yyyy-MM-dd"）。
    public func load(dates: [DayEntry], activeProjects: [Project], today: String) {
        weekly = ReportAggregator.aggregate(dates: dates, window: Self.weeklyWindow, today: today)
        monthly = ReportAggregator.aggregate(dates: dates, window: Self.monthlyWindow, today: today)
        self.activeProjects = activeProjects.map { $0.title }.filter { !$0.isEmpty }
    }

    /// 单独算某个窗口的聚合（视图需要任意窗口时用）。不改变已存的 weekly/monthly。
    public func compute(dates: [DayEntry], window: Int, today: String) -> ReportSummary {
        ReportAggregator.aggregate(dates: dates, window: window, today: today)
    }
}
