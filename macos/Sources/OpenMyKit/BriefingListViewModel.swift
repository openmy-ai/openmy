import Foundation
import Observation

/// 驱动日报浏览（日期列表 + 详情）的状态机。
@MainActor
@Observable
public final class BriefingListViewModel {
    public private(set) var dates: [DayEntry] = []
    public private(set) var selectedDate: String?
    public private(set) var selectedBriefing: Briefing?
    public private(set) var errorMessage: String?

    private let client: APIClient
    /// 选择序号：只有最新一次选择的响应允许写入，防止快速切换时过期响应覆盖。
    private var selectionToken = 0

    public init(client: APIClient) {
        self.client = client
    }

    /// 拉取已处理日期列表。
    public func loadDates() async {
        errorMessage = nil
        do {
            dates = try await client.dates()
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 选中某天，拉取其日报。快速切换时只有最新一次的响应生效。
    public func select(date: String) async {
        errorMessage = nil
        selectedDate = date
        selectionToken += 1
        let token = selectionToken
        do {
            let result = try await client.briefing(date: date)
            guard token == selectionToken else { return }  // 已被更新的选择取代，丢弃
            selectedBriefing = result
        } catch {
            guard token == selectionToken else { return }
            selectedBriefing = nil
            errorMessage = String(describing: error)
        }
    }
}
