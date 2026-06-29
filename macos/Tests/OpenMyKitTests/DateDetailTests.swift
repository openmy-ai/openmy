import XCTest
@testable import OpenMyKit

/// 钉住 GET /api/date/{date} 的解码——尤其 scenes 字段是后端**对象**形状
/// {scenes:[...], stats:{...}}，而非裸数组（issue #13 回归防护）。
final class DateDetailTests: XCTestCase {

    private func decode(_ json: String) throws -> DateDetail {
        try JSONDecoder().decode(DateDetail.self, from: Data(json.utf8))
    }

    // 行为：scenes 是后端对象形状 {scenes:[...], stats:{...}}，取出内层数组
    func test_decodes_scenes_from_object_shape() throws {
        let json = """
        {
          "date": "2026-06-25",
          "segments": [{"time": "09:00", "text": "hi", "preview": "hi"}],
          "scenes": {
            "scenes": [
              {"scene_id": "s1", "time_start": "09:00", "time_end": "09:30",
               "text": "hello", "role": {"category": "me"}, "summary": "sum"}
            ],
            "stats": {"role_distribution": {"me": 1}}
          }
        }
        """
        let d = try decode(json)
        XCTAssertEqual(d.date, "2026-06-25")
        XCTAssertEqual(d.segments.count, 1)
        XCTAssertEqual(d.scenes.count, 1)
        XCTAssertEqual(d.scenes[0].sceneId, "s1")
        XCTAssertEqual(d.scenes[0].roleCategory, "me")
    }

    // 行为：scenes 字段缺失 → 空，整体不崩
    func test_scenes_missing_degrades_to_empty() throws {
        let d = try decode(#"{"date":"2026-06-25","segments":[]}"#)
        XCTAssertTrue(d.scenes.isEmpty)
    }

    // 行为：scenes 为 null → 空
    func test_scenes_null_degrades_to_empty() throws {
        let d = try decode(#"{"date":"2026-06-25","scenes":null}"#)
        XCTAssertTrue(d.scenes.isEmpty)
    }

    // 行为：scenes 空对象（无内层数组）→ 空
    func test_scenes_empty_object_degrades_to_empty() throws {
        let d = try decode(#"{"date":"2026-06-25","scenes":{}}"#)
        XCTAssertTrue(d.scenes.isEmpty)
    }

    // 行为：scenes 对象只有 stats、无内层 scenes 数组 → 空
    func test_scenes_object_without_inner_array_degrades_to_empty() throws {
        let d = try decode(#"{"date":"2026-06-25","scenes":{"stats":{"role_distribution":{}}}}"#)
        XCTAssertTrue(d.scenes.isEmpty)
    }

    // 行为：date 必填，缺失则抛错（守住契约）
    func test_missing_date_throws() {
        XCTAssertThrowsError(try decode(#"{"segments":[]}"#))
    }
}
