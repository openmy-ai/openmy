import Foundation

/// 一条校正记录：GET /api/corrections 列表项。
/// 对齐 Web 侧栏校正词典：wrong → right，count 是累计替换次数。
/// 缺字段全部安全降级，避免后端老数据少字段时整列表解码失败。
public struct Correction: Decodable, Equatable, Sendable, Identifiable {
    /// 原文（识别错的词）。
    public let wrong: String
    /// 改成（正确的词）。
    public let right: String
    /// 上下文（提交时携带的句子，可能为空）。
    public let context: String
    /// 累计替换/命中次数。
    public let count: Int
    /// 首次记录时间（后端字符串，可能为空）。
    public let firstSeen: String
    /// 最近更新时间（后端字符串，可能为空）。
    public let lastUpdated: String

    /// wrong→right 组合作为稳定标识（同一对纠错只会有一条）。
    public var id: String { "\(wrong)→\(right)" }

    enum CodingKeys: String, CodingKey {
        case wrong, right, context, count
        case firstSeen = "first_seen"
        case lastUpdated = "last_updated"
    }

    public init(
        wrong: String,
        right: String,
        context: String = "",
        count: Int = 0,
        firstSeen: String = "",
        lastUpdated: String = ""
    ) {
        self.wrong = wrong
        self.right = right
        self.context = context
        self.count = count
        self.firstSeen = firstSeen
        self.lastUpdated = lastUpdated
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        wrong = try c.decodeIfPresent(String.self, forKey: .wrong) ?? ""
        right = try c.decodeIfPresent(String.self, forKey: .right) ?? ""
        context = try c.decodeIfPresent(String.self, forKey: .context) ?? ""
        count = try c.decodeIfPresent(Int.self, forKey: .count) ?? 0
        firstSeen = try c.decodeIfPresent(String.self, forKey: .firstSeen) ?? ""
        lastUpdated = try c.decodeIfPresent(String.self, forKey: .lastUpdated) ?? ""
    }
}

/// 提交校正结果：POST /api/correct/typo 返回。
/// success=false 时 error 给出原因（wrong/right 空或相等）。
public struct CorrectionResult: Decodable, Equatable, Sendable {
    /// 是否成功。
    public let success: Bool
    /// 本次在当天文件里替换的次数。
    public let replacedInFile: Int
    /// 当前校正词典总条数。
    public let totalCorrections: Int
    /// 失败原因（success=false 时有值）。
    public let error: String?

    enum CodingKeys: String, CodingKey {
        case success, error
        case replacedInFile = "replaced_in_file"
        case totalCorrections = "total_corrections"
    }

    public init(
        success: Bool,
        replacedInFile: Int = 0,
        totalCorrections: Int = 0,
        error: String? = nil
    ) {
        self.success = success
        self.replacedInFile = replacedInFile
        self.totalCorrections = totalCorrections
        self.error = error
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        success = try c.decodeIfPresent(Bool.self, forKey: .success) ?? false
        replacedInFile = try c.decodeIfPresent(Int.self, forKey: .replacedInFile) ?? 0
        totalCorrections = try c.decodeIfPresent(Int.self, forKey: .totalCorrections) ?? 0
        error = try c.decodeIfPresent(String.self, forKey: .error)
    }
}

extension APIClient {
    /// 校正词典列表：GET /api/corrections。文件不存在时后端返回 {corrections:[]}。
    public func corrections() async throws -> [Correction] {
        struct Wrapper: Decodable { let corrections: [Correction] }
        let wrapper: Wrapper = try await get("/api/corrections")
        return wrapper.corrections
    }

    /// 提交一条校正：POST /api/correct/typo。
    /// 对齐 Web submitTypoCorrection：默认 syncVocab=true 同步词表。
    /// wrong/right 空或相等时后端返回 success=false + error，这里不抛错，交回调用方提示。
    public func submitCorrection(
        wrong: String,
        right: String,
        context: String = "",
        date: String? = nil,
        syncVocab: Bool = true
    ) async throws -> CorrectionResult {
        var body: [String: Any] = [
            "wrong": wrong,
            "right": right,
            "context": context,
            "sync_vocab": syncVocab,
        ]
        if let date { body["date"] = date }
        return try await post("/api/correct/typo", body: body)
    }
}
