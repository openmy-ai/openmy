import Foundation

/// 某天的原始记录：GET /api/date/{date}
/// 用于从日报下钻到逐段转写文本；scenes 供音频回放/波形/字幕复核。
public struct DateDetail: Decodable, Equatable, Sendable {
    public let date: String
    public let segments: [TranscriptSegment]
    /// 场景列表，缺失降级为空。每个场景可关联一段 chunk 音频。
    public let scenes: [TranscriptScene]

    enum CodingKeys: String, CodingKey {
        case date, segments, scenes
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        segments = try c.decodeIfPresent([TranscriptSegment].self, forKey: .segments) ?? []
        // scenes 是后端对象 {scenes:[...], stats:{...}}（不改后端：网页版 data.scenes.scenes 依赖此形状）。
        // 解信封取内层数组；字段缺失 / null / 空对象 / 无内层数组时安全降级为空。
        let scenesEnvelope = (try? c.decodeIfPresent(ScenesEnvelope.self, forKey: .scenes)) ?? nil
        scenes = scenesEnvelope?.scenes ?? []
    }
}

/// 后端 GET /api/date/{date} 的 scenes 字段是对象 {scenes:[...], stats:{...}}（网页版 data.scenes.scenes 依赖此形状）。
/// 此信封只取内层 scenes 数组；内层缺失 / 异型时降级为空，绝不让外层 DateDetail 解码崩溃。
private struct ScenesEnvelope: Decodable {
    let scenes: [TranscriptScene]
    enum CodingKeys: String, CodingKey { case scenes }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        scenes = ((try? c.decodeIfPresent([TranscriptScene].self, forKey: .scenes)) ?? nil) ?? []
    }
}

/// 一个场景：时间区间 + 文本 + 角色/摘要，可关联一段 chunk 音频用于回放。
/// 命名为 TranscriptScene 以避免与 SwiftUI.Scene 在 App 层冲突。
public struct TranscriptScene: Decodable, Equatable, Sendable, Identifiable {
    public let sceneId: String
    public let timeStart: String
    public let timeEnd: String
    public let text: String
    public let roleCategory: String
    public let summary: String
    /// 关联音频引用；缺失（无音频）时为 nil。
    public let audioRef: AudioRef?

    public var id: String { sceneId }

    enum CodingKeys: String, CodingKey {
        case sceneId = "scene_id"
        case timeStart = "time_start"
        case timeEnd = "time_end"
        case text, role, summary
        case audioRef = "audio_ref"
    }

    /// role 是嵌套对象 {category, ...}，这里只取 category。
    enum RoleKeys: String, CodingKey {
        case category
    }

    public init(
        sceneId: String,
        timeStart: String,
        timeEnd: String,
        text: String,
        roleCategory: String,
        summary: String,
        audioRef: AudioRef?
    ) {
        self.sceneId = sceneId
        self.timeStart = timeStart
        self.timeEnd = timeEnd
        self.text = text
        self.roleCategory = roleCategory
        self.summary = summary
        self.audioRef = audioRef
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        sceneId = try c.decodeIfPresent(String.self, forKey: .sceneId) ?? ""
        timeStart = try c.decodeIfPresent(String.self, forKey: .timeStart) ?? ""
        timeEnd = try c.decodeIfPresent(String.self, forKey: .timeEnd) ?? ""
        text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        summary = try c.decodeIfPresent(String.self, forKey: .summary) ?? ""
        audioRef = try c.decodeIfPresent(AudioRef.self, forKey: .audioRef)
        if let role = try? c.nestedContainer(keyedBy: RoleKeys.self, forKey: .role) {
            roleCategory = try role.decodeIfPresent(String.self, forKey: .category) ?? ""
        } else {
            roleCategory = ""
        }
    }
}

/// 场景的音频引用：定位到某个 chunk 文件内的一段区间。
public struct AudioRef: Decodable, Equatable, Sendable {
    public let chunkId: String
    /// 场景在 chunk 内的起点（秒）。
    public let offsetStart: Double
    /// 场景在 chunk 内的终点（秒）。<= offsetStart 时按整段（durationSeconds）兜底。
    public let offsetEnd: Double
    /// chunk 总时长（秒），offsetEnd 无效时的兜底依据。
    public let durationSeconds: Double
    /// 语音子区间（相对 chunk 起点的秒数对），用于波形高亮等；可缺失。
    public let speechSegments: [[Double]]

    enum CodingKeys: String, CodingKey {
        case chunkId = "chunk_id"
        case offsetStart = "offset_start"
        case offsetEnd = "offset_end"
        case durationSeconds = "duration_seconds"
        case speechSegments = "speech_segments"
    }

    public init(
        chunkId: String,
        offsetStart: Double,
        offsetEnd: Double,
        durationSeconds: Double,
        speechSegments: [[Double]] = []
    ) {
        self.chunkId = chunkId
        self.offsetStart = offsetStart
        self.offsetEnd = offsetEnd
        self.durationSeconds = durationSeconds
        self.speechSegments = speechSegments
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        chunkId = try c.decodeIfPresent(String.self, forKey: .chunkId) ?? ""
        offsetStart = try c.decodeIfPresent(Double.self, forKey: .offsetStart) ?? 0
        offsetEnd = try c.decodeIfPresent(Double.self, forKey: .offsetEnd) ?? 0
        durationSeconds = try c.decodeIfPresent(Double.self, forKey: .durationSeconds) ?? 0
        speechSegments = try c.decodeIfPresent([[Double]].self, forKey: .speechSegments) ?? []
    }
}

/// 一段转写：时间标记 + 文本。
public struct TranscriptSegment: Decodable, Equatable, Sendable {
    public let time: String
    public let text: String
    public let preview: String

    enum CodingKeys: String, CodingKey {
        case time, text, preview
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        time = try c.decodeIfPresent(String.self, forKey: .time) ?? ""
        text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        preview = try c.decodeIfPresent(String.self, forKey: .preview) ?? ""
    }
}
