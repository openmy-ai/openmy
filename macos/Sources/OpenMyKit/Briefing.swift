import Foundation

/// 日报：GET /api/briefing/{date} → daily_briefing.json
public struct Briefing: Decodable, Equatable, Sendable {
    public let date: String
    public let summary: String
    public let keyEvents: [String]
    public let todosOpen: [String]
    public let insights: [Insight]
    public let timeBlocks: [TimeBlock]
    public let totalWords: Int
    public let totalScenes: Int
    public let voiceHours: Double

    public struct Insight: Decodable, Equatable, Sendable {
        public let topic: String
        public let content: String
    }

    public struct TimeBlock: Decodable, Equatable, Sendable {
        public let period: String
        public let summary: String
    }

    enum CodingKeys: String, CodingKey {
        case date, summary, insights
        case keyEvents = "key_events"
        case todosOpen = "todos_open"
        case timeBlocks = "time_blocks"
        case totalWords = "total_words"
        case totalScenes = "total_scenes"
        case voiceHours = "voice_hours"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        summary = try c.decodeIfPresent(String.self, forKey: .summary) ?? ""
        keyEvents = try c.decodeIfPresent([String].self, forKey: .keyEvents) ?? []
        todosOpen = try c.decodeIfPresent([String].self, forKey: .todosOpen) ?? []
        insights = try c.decodeIfPresent([Insight].self, forKey: .insights) ?? []
        timeBlocks = try c.decodeIfPresent([TimeBlock].self, forKey: .timeBlocks) ?? []
        totalWords = try c.decodeIfPresent(Int.self, forKey: .totalWords) ?? 0
        totalScenes = try c.decodeIfPresent(Int.self, forKey: .totalScenes) ?? 0
        voiceHours = try c.decodeIfPresent(Double.self, forKey: .voiceHours) ?? 0
    }
}
