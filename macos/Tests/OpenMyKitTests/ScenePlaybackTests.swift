import XCTest
@testable import OpenMyKit

final class ScenePlaybackTests: XCTestCase {

    private func ref(start: Double, end: Double, duration: Double) -> AudioRef {
        AudioRef(chunkId: "c", offsetStart: start, offsetEnd: end, durationSeconds: duration)
    }

    // sceneStart 即 offsetStart
    func test_sceneStart_is_offsetStart() {
        XCTAssertEqual(ScenePlayback.sceneStart(ref(start: 3.5, end: 12, duration: 60)), 3.5)
    }

    // 正常区间：sceneEnd 取 offsetEnd
    func test_sceneEnd_uses_offsetEnd_when_valid() {
        XCTAssertEqual(ScenePlayback.sceneEnd(ref(start: 3.5, end: 12, duration: 60)), 12)
        XCTAssertEqual(ScenePlayback.sceneDuration(ref(start: 3.5, end: 12, duration: 60)), 8.5, accuracy: 1e-9)
    }

    // offsetEnd <= offsetStart 时用 duration 兜底为整段
    func test_sceneEnd_falls_back_to_duration() {
        let r = ref(start: 5, end: 0, duration: 60)
        XCTAssertEqual(ScenePlayback.sceneEnd(r), 60)
        XCTAssertEqual(ScenePlayback.sceneDuration(r), 55, accuracy: 1e-9)
    }

    // offsetEnd == offsetStart 也算无效，走兜底
    func test_sceneEnd_equal_offsets_falls_back() {
        let r = ref(start: 5, end: 5, duration: 30)
        XCTAssertEqual(ScenePlayback.sceneEnd(r), 30)
    }

    // 绝对时间映射成场景内进度，并钳制
    func test_progress_mapping_and_clamp() {
        let r = ref(start: 10, end: 20, duration: 60)
        XCTAssertEqual(ScenePlayback.progress(in: r, absoluteTime: 15), 5, accuracy: 1e-9)
        // 越过起点之前钳为 0
        XCTAssertEqual(ScenePlayback.progress(in: r, absoluteTime: 8), 0, accuracy: 1e-9)
        // 越过终点钳为 sceneDuration
        XCTAssertEqual(ScenePlayback.progress(in: r, absoluteTime: 25), 10, accuracy: 1e-9)
    }

    // 场景进度反映射回绝对时间
    func test_absoluteTime_from_progress() {
        let r = ref(start: 10, end: 20, duration: 60)
        XCTAssertEqual(ScenePlayback.absoluteTime(in: r, sceneProgress: 5), 15, accuracy: 1e-9)
        // 超界进度被钳制
        XCTAssertEqual(ScenePlayback.absoluteTime(in: r, sceneProgress: 100), 20, accuracy: 1e-9)
        XCTAssertEqual(ScenePlayback.absoluteTime(in: r, sceneProgress: -5), 10, accuracy: 1e-9)
    }

    // 边界判定：到/越过终点为真
    func test_reachedEnd() {
        let r = ref(start: 10, end: 20, duration: 60)
        XCTAssertFalse(ScenePlayback.reachedEnd(r, absoluteTime: 19.9))
        XCTAssertTrue(ScenePlayback.reachedEnd(r, absoluteTime: 20))
        XCTAssertTrue(ScenePlayback.reachedEnd(r, absoluteTime: 21))
    }

    // 比例换算成场景进度
    func test_sceneProgress_from_fraction() {
        let r = ref(start: 10, end: 20, duration: 60)
        XCTAssertEqual(ScenePlayback.sceneProgress(in: r, fraction: 0.5), 5, accuracy: 1e-9)
        XCTAssertEqual(ScenePlayback.sceneProgress(in: r, fraction: 2), 10, accuracy: 1e-9)
        XCTAssertEqual(ScenePlayback.sceneProgress(in: r, fraction: -1), 0, accuracy: 1e-9)
    }
}
