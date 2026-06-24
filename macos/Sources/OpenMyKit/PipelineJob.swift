import Foundation

/// 管线任务：GET /api/pipeline/jobs/{id}
public struct PipelineJob: Decodable, Equatable, Sendable, Identifiable {
    public let jobId: String
    public let kind: String
    /// queued / running / paused / succeeded / partial / failed / cancelled
    public let status: String
    public let currentStep: String
    public let error: String
    public let steps: [PipelineStep]
    public let canPause: Bool
    public let canSkip: Bool
    public let progressPct: Int

    public var id: String { jobId }

    /// 是否已进入终态。
    public var isTerminal: Bool {
        ["succeeded", "partial", "failed", "cancelled"].contains(status)
    }

    enum CodingKeys: String, CodingKey {
        case kind, status, steps, error
        case jobId = "job_id"
        case currentStep = "current_step"
        case canPause = "can_pause"
        case canSkip = "can_skip"
        case progressPct = "progress_pct"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        jobId = try c.decode(String.self, forKey: .jobId)
        kind = try c.decodeIfPresent(String.self, forKey: .kind) ?? ""
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? "queued"
        currentStep = try c.decodeIfPresent(String.self, forKey: .currentStep) ?? ""
        error = try c.decodeIfPresent(String.self, forKey: .error) ?? ""
        steps = try c.decodeIfPresent([PipelineStep].self, forKey: .steps) ?? []
        canPause = try c.decodeIfPresent(Bool.self, forKey: .canPause) ?? false
        canSkip = try c.decodeIfPresent(Bool.self, forKey: .canSkip) ?? false
        progressPct = try c.decodeIfPresent(Int.self, forKey: .progressPct) ?? 0
    }
}

/// 任务的一个阶段步骤。
public struct PipelineStep: Decodable, Equatable, Sendable, Identifiable {
    public let name: String
    public let label: String
    /// pending / running / done / failed / skipped
    public let status: String
    public let resultSummary: String

    public var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name, label, status
        case resultSummary = "result_summary"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decode(String.self, forKey: .name)
        label = try c.decodeIfPresent(String.self, forKey: .label) ?? name
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? "pending"
        resultSummary = try c.decodeIfPresent(String.self, forKey: .resultSummary) ?? ""
    }
}

/// 任务控制动作。
public enum JobAction: String, Sendable {
    case pause, resume, cancel, skip
}
