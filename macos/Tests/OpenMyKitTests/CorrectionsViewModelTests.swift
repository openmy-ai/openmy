import XCTest
@testable import OpenMyKit

@MainActor
final class CorrectionsViewModelTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func makeVM() -> CorrectionsViewModel {
        CorrectionsViewModel(client: APIClient(baseURL: URL(string: "http://localhost:8420")!, session: .mocked()))
    }

    // 行为：load 填充词典列表
    func test_load_fills_corrections() async {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{"corrections":[{"wrong":"新建","right":"新疆","count":3}]}"#.utf8))
        }
        let vm = makeVM()
        await vm.load()
        XCTAssertEqual(vm.corrections.count, 1)
        XCTAssertEqual(vm.corrections[0].right, "新疆")
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：load 失败置 errorMessage，列表保持原值
    func test_load_failure_sets_error() async {
        MockURLProtocol.handler = { _ in (500, Data("{}".utf8)) }
        let vm = makeVM()
        await vm.load()
        XCTAssertNotNil(vm.errorMessage)
        XCTAssertEqual(vm.corrections, [])
    }

    // 行为：submit 成功后 reload 列表（POST 返回成功 → 紧接着 GET 拉新列表）
    func test_submit_success_reloads() async {
        // 第一次 POST /api/correct/typo 成功，第二次 GET /api/corrections 返回新列表。
        MockURLProtocol.handler = { req in
            if req.url?.path == "/api/correct/typo" {
                return (200, Data(#"{"success":true,"replaced_in_file":2,"total_corrections":1}"#.utf8))
            }
            return (200, Data(#"{"corrections":[{"wrong":"新建","right":"新疆","count":1}]}"#.utf8))
        }
        let vm = makeVM()
        let ok = await vm.submit(wrong: "新建", right: "新疆", context: "去新疆", date: "2026-06-05")
        XCTAssertTrue(ok)
        XCTAssertEqual(vm.lastResult?.replacedInFile, 2)
        XCTAssertEqual(vm.corrections.count, 1)
        XCTAssertEqual(vm.corrections[0].wrong, "新建")
        XCTAssertNil(vm.errorMessage)
    }

    // 行为：空输入本地校验拦截，不发请求
    func test_submit_empty_input_validates() async {
        MockURLProtocol.handler = { _ in XCTFail("空输入不应发请求"); return (200, Data("{}".utf8)) }
        let vm = makeVM()
        let ok = await vm.submit(wrong: "  ", right: "新疆")
        XCTAssertFalse(ok)
        XCTAssertNotNil(vm.errorMessage)
    }

    // 行为：原文与改成相同本地拦截，不发请求
    func test_submit_equal_input_validates() async {
        MockURLProtocol.handler = { _ in XCTFail("相同输入不应发请求"); return (200, Data("{}".utf8)) }
        let vm = makeVM()
        let ok = await vm.submit(wrong: "新疆", right: "新疆")
        XCTAssertFalse(ok)
        XCTAssertNotNil(vm.errorMessage)
    }

    // 行为：后端 success=false 时把 error 写入 errorMessage，不 reload
    func test_submit_backend_failure_sets_error() async {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/correct/typo")  // 只应有 POST，不应有后续 GET
            return (200, Data(#"{"success":false,"error":"内部错误"}"#.utf8))
        }
        let vm = makeVM()
        let ok = await vm.submit(wrong: "a", right: "b")
        XCTAssertFalse(ok)
        XCTAssertEqual(vm.errorMessage, "内部错误")
        XCTAssertEqual(vm.corrections, [])
    }
}
