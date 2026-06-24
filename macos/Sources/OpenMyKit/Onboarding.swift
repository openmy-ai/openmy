import Foundation

/// onboarding 状态：GET /api/onboarding
public struct OnboardingState: Decodable, Equatable, Sendable {
    public let stage: String
    public let completed: Bool
    public let recommendedProvider: String
    public let currentProvider: String
    public let headline: String
    public let nextStep: String
    /// 按 local/cloud 分组的可选引擎。
    public let choices: [String: [ProviderChoice]]

    /// 扁平的引擎列表，本地在前、云端在后，UI 直接渲染。
    public var allProviders: [ProviderChoice] {
        (choices["local"] ?? []) + (choices["cloud"] ?? [])
    }

    enum CodingKeys: String, CodingKey {
        case stage, completed, headline, choices
        case recommendedProvider = "recommended_provider"
        case currentProvider = "current_provider"
        case nextStep = "next_step"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        stage = try c.decode(String.self, forKey: .stage)
        completed = try c.decodeIfPresent(Bool.self, forKey: .completed) ?? false
        recommendedProvider = try c.decodeIfPresent(String.self, forKey: .recommendedProvider) ?? ""
        currentProvider = try c.decodeIfPresent(String.self, forKey: .currentProvider) ?? ""
        headline = try c.decodeIfPresent(String.self, forKey: .headline) ?? ""
        nextStep = try c.decodeIfPresent(String.self, forKey: .nextStep) ?? ""
        choices = try c.decodeIfPresent([String: [ProviderChoice]].self, forKey: .choices) ?? [:]
    }
}

/// 一个可选的 STT 引擎。
public struct ProviderChoice: Decodable, Equatable, Sendable, Identifiable {
    public let name: String
    public let label: String
    public let description: String
    public let type: String
    public let ready: Bool
    public let isActive: Bool
    public let isRecommended: Bool
    public let needsApiKey: Bool

    public var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name, label, description, type, ready
        case isActive = "is_active"
        case isRecommended = "is_recommended"
        case needsApiKey = "needs_api_key"
    }
}
