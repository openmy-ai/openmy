import Foundation

/// 某天的原始记录：GET /api/date/{date}
/// 用于从日报下钻到逐段转写文本。
public struct DateDetail: Decodable, Equatable, Sendable {
    public let date: String
    public let segments: [TranscriptSegment]

    enum CodingKeys: String, CodingKey {
        case date, segments
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        segments = try c.decodeIfPresent([TranscriptSegment].self, forKey: .segments) ?? []
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
