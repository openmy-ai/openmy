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

    /// 选中某天，拉取其日报。
    public func select(date: String) async {
        errorMessage = nil
        selectedDate = date
        do {
            selectedBriefing = try await client.briefing(date: date)
        } catch {
            selectedBriefing = nil
            errorMessage = String(describing: error)
        }
    }
}
