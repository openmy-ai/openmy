import XCTest
@testable import OpenMyKit

@MainActor
final class BriefingListViewModelTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeVM() -> BriefingListViewModel {
        BriefingListViewModel(client: APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked()))
    }

    // 行为：loadDates 拉取日期列表
    func test_loadDates() async {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/dates")
            return (200, Data(#"[{"date":"2026-06-05","segments":12,"word_count":3400,"summary":"忙"}]"#.utf8))
        }
        let vm = makeVM()
        await vm.loadDates()
        XCTAssertEqual(vm.dates.count, 1)
        XCTAssertEqual(vm.dates.first?.date, "2026-06-05")
    }

    // 行为：select 拉取该日期日报
    func test_select_loads_briefing() async {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/briefing/2026-06-05")
            return (200, Data(#"{"date":"2026-06-05","summary":"忙碌","key_events":["A"]}"#.utf8))
        }
        let vm = makeVM()
        await vm.select(date: "2026-06-05")
        XCTAssertEqual(vm.selectedBriefing?.summary, "忙碌")
        XCTAssertEqual(vm.selectedDate, "2026-06-05")
    }

    // 行为：日报缺失（404）记录错误且不崩
    func test_select_missing_briefing() async {
        MockURLProtocol.handler = { _ in (404, Data(#"{"error":"no briefing"}"#.utf8)) }
        let vm = makeVM()
        await vm.select(date: "2099-01-01")
        XCTAssertNil(vm.selectedBriefing)
        XCTAssertNotNil(vm.errorMessage)
    }
}
