import Foundation

/// 某天 meta 四分区：GET /api/date/{date}/meta（对应后端 get_date_meta_payload，直接回传 meta dict）。
/// 对齐 daily.js renderMetaPanels 的四组：events(发生)/intents(打算)/facts(记住)/decisions(决定)。
/// 每类项可能是字符串或对象（含 time/summary/what/task/content/decision/fact/intent 等异型键），
/// 这里按 lenient 抽成可显示文本 + 可选时间。实测常为空，全部缺失降级空数组。
public struct DateMeta: Decodable, Equatable, Sendable {
    public let events: [MetaEntry]
    public let intents: [MetaEntry]
    public let facts: [MetaEntry]
    public let decisions: [MetaEntry]

    enum CodingKeys: String, CodingKey {
        case events, intents, facts, decisions
    }

    public init(
        events: [MetaEntry] = [], intents: [MetaEntry] = [],
        facts: [MetaEntry] = [], decisions: [MetaEntry] = []
    ) {
        self.events = events
        self.intents = intents
        self.facts = facts
        self.decisions = decisions
    }

    public init(from decoder: Decoder) throws {
        // meta 可能整体缺失/非字典，此时 keyedContainer 失败，全降级空。
        guard let c = try? decoder.container(keyedBy: CodingKeys.self) else {
            events = []; intents = []; facts = []; decisions = []
            return
        }
        events = DateMeta.decodeEntries(c, forKey: .events)
        intents = DateMeta.decodeEntries(c, forKey: .intents)
        facts = DateMeta.decodeEntries(c, forKey: .facts)
        decisions = DateMeta.decodeEntries(c, forKey: .decisions)
    }

    private static func decodeEntries(
        _ c: KeyedDecodingContainer<CodingKeys>, forKey key: CodingKeys
    ) -> [MetaEntry] {
        guard let items = try? c.decodeIfPresent([MetaEntry].self, forKey: key) else { return [] }
        // 丢弃既无文本又无时间的空壳项。
        return items.filter { !$0.text.isEmpty || !$0.time.isEmpty }
    }
}

/// meta 单项：抽出可显示文本 + 可选时间 + 可选项目/主题标签。
/// 文本候选键对齐 daily.js：summary/what/task/content/decision/fact/intent；项也可能是裸字符串。
public struct MetaEntry: Decodable, Equatable, Sendable {
    /// 可显示文本，已按候选键抽取，缺则空串。
    public let text: String
    /// 时间标记，如 "16:50"，缺则空串。
    public let time: String
    /// 项目/主题标签（project || topic），缺则空串。
    public let project: String

    private static let textKeys = [
        "summary", "what", "task", "content", "decision", "fact", "intent",
    ]

    public init(text: String, time: String = "", project: String = "") {
        self.text = text
        self.time = time
        self.project = project
    }

    public init(from decoder: Decoder) throws {
        // 裸字符串项：整段当文本。
        if let single = try? decoder.singleValueContainer(),
           let s = try? single.decode(String.self) {
            text = s
            time = ""
            project = ""
            return
        }
        guard let c = try? decoder.container(keyedBy: DynamicKey.self) else {
            text = ""; time = ""; project = ""
            return
        }
        func str(_ k: String) -> String {
            guard let key = DynamicKey(stringValue: k) else { return "" }
            return ((try? c.decodeIfPresent(String.self, forKey: key)) ?? "") ?? ""
        }
        var resolvedText = ""
        for key in MetaEntry.textKeys {
            let v = str(key)
            if !v.isEmpty { resolvedText = v; break }
        }
        text = resolvedText
        time = str("time")
        let proj = str("project")
        project = proj.isEmpty ? str("topic") : proj
    }

    /// 任意字符串键（动态解码用）。
    struct DynamicKey: CodingKey {
        var stringValue: String
        var intValue: Int? { nil }
        init?(stringValue: String) { self.stringValue = stringValue }
        init?(intValue: Int) { nil }
    }
}

extension APIClient {
    /// 某天 meta 四分区：GET /api/date/{date}/meta。
    public func dateMeta(date: String) async throws -> DateMeta {
        try await get("/api/date/\(date)/meta")
    }
}
