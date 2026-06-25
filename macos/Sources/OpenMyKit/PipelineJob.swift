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
    /// 预估剩余秒数。后端可能不给（预估中）。
    public let etaSeconds: Int?
    /// 源音频文件名（首页卡片标题用）。
    public let sourceFile: String
    /// 目标日期（YYYY-MM-DD）。context 类任务可能无日期。
    public let targetDate: String?
    /// 实时日志行（首页只取最近几条）。
    public let logLines: [String]

    public var id: String { jobId }

    /// 是否已进入终态。interrupted 是后端重启恢复未完成任务时的终态。
    public var isTerminal: Bool {
        ["succeeded", "partial", "failed", "cancelled", "interrupted"].contains(status)
    }

    enum CodingKeys: String, CodingKey {
        case kind, status, steps, error
        case jobId = "job_id"
        case currentStep = "current_step"
        case canPause = "can_pause"
        case canSkip = "can_skip"
        case progressPct = "progress_pct"
        case etaSeconds = "eta_seconds"
        case sourceFile = "source_file"
        case targetDate = "target_date"
        case logLines = "log_lines"
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
        etaSeconds = try c.decodeIfPresent(Int.self, forKey: .etaSeconds)
        sourceFile = try c.decodeIfPresent(String.self, forKey: .sourceFile) ?? ""
        // target_date 可能为空字符串，归一化为 nil 让视图判空一致。
        let rawTargetDate = try c.decodeIfPresent(String.self, forKey: .targetDate)
        targetDate = (rawTargetDate?.isEmpty == false) ? rawTargetDate : nil
        logLines = try c.decodeIfPresent([String].self, forKey: .logLines) ?? []
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
