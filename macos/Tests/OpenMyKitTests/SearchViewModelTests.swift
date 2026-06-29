import XCTest
@testable import OpenMyKit

@MainActor
final class SearchViewModelTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeVM() -> SearchViewModel {
        SearchViewModel(client: APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked()))
    }

    /// 三条命中：两天，前两条同一天。
    private func threeHitsHandler() {
        MockURLProtocol.handler = { _ in
            let json = """
            [{"date":"2026-06-05","time":"00:01","context":"a<mark>x</mark>","raw_context":"ax"},
             {"date":"2026-06-05","time":"00:09","context":"b<mark>x</mark>","raw_context":"bx"},
             {"date":"2026-06-06","time":"00:02","context":"c<mark>x</mark>","raw_context":"cx"}]
            """
            return (200, Data(json.utf8))
        }
    }

    // 行为：搜索填充结果并默认选中第一条
    func test_search_fills_results() async {
        threeHitsHandler()
        let vm = makeVM()
        vm.query = "x"
        await vm.search()
        XCTAssertEqual(vm.results.count, 3)
        XCTAssertEqual(vm.selectedIndex, 0)
        XCTAssertEqual(vm.selectedResult?.time, "00:01")
    }

    // 行为：空 query 清空结果，不发请求
    func test_empty_query_clears() async {
        MockURLProtocol.handler = { _ in XCTFail("不应发请求"); return (200, Data("[]".utf8)) }
        let vm = makeVM()
        vm.query = "   "
        await vm.search()
        XCTAssertEqual(vm.results, [])
        XCTAssertEqual(vm.selectedIndex, -1)
    }

    // 行为：按日期分组保持首次出现顺序
    func test_grouped_by_date_preserves_order() async {
        threeHitsHandler()
        let vm = makeVM()
        vm.query = "x"
        await vm.search()
        let groups = vm.groupedByDate
        XCTAssertEqual(groups.count, 2)
        XCTAssertEqual(groups[0].date, "2026-06-05")
        XCTAssertEqual(groups[0].results.count, 2)
        XCTAssertEqual(groups[1].date, "2026-06-06")
        XCTAssertEqual(groups[1].results.count, 1)
    }

    // 行为：上下移动选中项，取模回环（对齐 Web spotlight）
    func test_move_selection_wraps() async {
        threeHitsHandler()
        let vm = makeVM()
        vm.query = "x"
        await vm.search()
        XCTAssertEqual(vm.selectedIndex, 0)

        vm.moveSelection(1)
        XCTAssertEqual(vm.selectedIndex, 1)
        vm.moveSelection(1)
        XCTAssertEqual(vm.selectedIndex, 2)
        vm.moveSelection(1)  // 到底回环到首项
        XCTAssertEqual(vm.selectedIndex, 0)

        vm.moveSelection(-1)  // 到顶回环到末项
        XCTAssertEqual(vm.selectedIndex, 2)
    }

    // 行为：无结果时移动选中项保持 -1
    func test_move_selection_no_results() {
        let vm = makeVM()
        vm.moveSelection(1)
        XCTAssertEqual(vm.selectedIndex, -1)
        XCTAssertNil(vm.selectedResult)
    }

    // 行为：clear 重置全部状态
    func test_clear_resets() async {
        threeHitsHandler()
        let vm = makeVM()
        vm.query = "x"
        await vm.search()
        vm.clear()
        XCTAssertEqual(vm.query, "")
        XCTAssertEqual(vm.results, [])
        XCTAssertEqual(vm.selectedIndex, -1)
    }

    // 行为：搜索出错时清空结果并记录错误
    func test_search_error() async {
        MockURLProtocol.handler = { _ in (500, Data("{}".utf8)) }
        let vm = makeVM()
        vm.query = "x"
        await vm.search()
        XCTAssertEqual(vm.results, [])
        XCTAssertEqual(vm.selectedIndex, -1)
        XCTAssertNotNil(vm.errorMessage)
    }
}
