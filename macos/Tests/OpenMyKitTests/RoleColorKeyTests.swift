import XCTest
@testable import OpenMyKit

final class RoleColorKeyTests: XCTestCase {

    // 行为：英文枚举键直接归类
    func test_english_keys() {
        XCTAssertEqual(RoleColorKey.from("ai"), .ai)
        XCTAssertEqual(RoleColorKey.from("merchant"), .merchant)
        XCTAssertEqual(RoleColorKey.from("pet"), .pet)
        XCTAssertEqual(RoleColorKey.from("self"), .self)
        XCTAssertEqual(RoleColorKey.from("interpersonal"), .interpersonal)
    }

    // 行为：中文关键词归类
    func test_chinese_keywords() {
        XCTAssertEqual(RoleColorKey.from("服务员"), .merchant)
        XCTAssertEqual(RoleColorKey.from("客服小姐"), .merchant)
        XCTAssertEqual(RoleColorKey.from("我家宠物狗"), .pet)
        XCTAssertEqual(RoleColorKey.from("自言自语"), .self)
        XCTAssertEqual(RoleColorKey.from("和同事聊天"), .interpersonal)
        XCTAssertEqual(RoleColorKey.from("家人"), .interpersonal)
    }

    // 行为：大小写无关
    func test_case_insensitive() {
        XCTAssertEqual(RoleColorKey.from("AI"), .ai)
        XCTAssertEqual(RoleColorKey.from("Merchant"), .merchant)
    }

    // 行为：空串归 other
    func test_empty_is_other() {
        XCTAssertEqual(RoleColorKey.from(""), .other)
        XCTAssertEqual(RoleColorKey.from("   "), .other)
    }

    // 行为：显式不确定归 uncertain
    func test_uncertain() {
        XCTAssertEqual(RoleColorKey.from("uncertain"), .uncertain)
        XCTAssertEqual(RoleColorKey.from("无法识别"), .uncertain)
        XCTAssertEqual(RoleColorKey.from("未知角色"), .uncertain)
    }

    // 行为：无法识别的非空字符串归 other
    func test_unknown_is_other() {
        XCTAssertEqual(RoleColorKey.from("外星人"), .other)
    }

    // 行为：枚举有 7 个 case，rawValue 稳定供视图取色
    func test_raw_values_stable() {
        XCTAssertEqual(RoleColorKey.allCases.count, 7)
        XCTAssertEqual(RoleColorKey.`self`.rawValue, "self")
        XCTAssertEqual(RoleColorKey.interpersonal.rawValue, "interpersonal")
    }
}
