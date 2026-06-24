import Foundation
import Observation

/// 驱动四阶段进度面板的任务状态机。
///
/// 可测核心：start / refresh / 控制动作。定时轮询循环（startPolling）是薄胶水，由视图驱动。
@MainActor
@Observable
public final class JobViewModel {
    public private(set) var job: PipelineJob?
    public private(set) var errorMessage: String?

    private let client: APIClient
    private var pollingTask: Task<Void, Never>?

    public init(client: APIClient) {
        self.client = client
    }

    /// 当前是否有任务在进行（非终态）。
    public var isActive: Bool {
        guard let job else { return false }
        return !job.isTerminal
    }

    /// 是否可跳过当前步骤（由后端计算，仅蒸馏 running 时为真）。
    public var canSkip: Bool { job?.canSkip ?? false }
    /// 是否可暂停。
    public var canPause: Bool { job?.canPause ?? false }

    /// 创建并启动一次转写任务。
    public func start(audioFiles: [String], targetDate: String? = nil) async {
        errorMessage = nil
        do {
            job = try await client.createJob(audioFiles: audioFiles, targetDate: targetDate)
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 拉取当前任务最新状态。无任务则忽略。
    public func refresh() async {
        guard let id = job?.jobId else { return }
        do {
            job = try await client.job(id: id)
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 清空当前任务（终态后让界面回到日报浏览）。
    public func clear() {
        stopPolling()
        job = nil
        errorMessage = nil
    }

    public func pause() async { await act(.pause) }
    public func resume() async { await act(.resume) }
    public func cancel() async { await act(.cancel) }
    public func skip() async { await act(.skip) }

    private func act(_ action: JobAction) async {
        guard let id = job?.jobId else { return }
        do {
            job = try await client.jobAction(id: id, action: action)
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 视图侧调用：循环轮询直到任务进入终态。
    /// ponytail: 轮询足够；后端无 SSE，等轮询明显不够再换。
    public func startPolling(intervalSeconds: Double = 2.0) {
        pollingTask?.cancel()
        pollingTask = Task { [weak self] in
            while let self, await self.isActive {
                try? await Task.sleep(for: .seconds(intervalSeconds))
                if Task.isCancelled { break }
                await self.refresh()
            }
        }
    }

    public func stopPolling() {
        pollingTask?.cancel()
        pollingTask = nil
    }
}
