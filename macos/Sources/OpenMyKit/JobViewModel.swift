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
    /// 正在上传音频（拿 file_path 阶段），对齐 Web 的 uploadingHomeFiles 状态。
    public private(set) var isUploading: Bool = false

    private let client: APIClient
    private var pollingTask: Task<Void, Never>?
    /// 上次启动的输入，供 retry() 用同样的文件重建任务。
    private var lastInput: StartInput?
    /// 上传成功后落地的后端路径。retry 时复用，避免把文件重复传进 inbox。
    private var uploadedPaths: [String] = []
    private var uploadedSourceFile: String?
    private var uploadedSourceSize: Int?

    /// 一次启动的输入来源：直接给后端路径，或本地待上传的文件 URL。
    private enum StartInput {
        case paths(audioFiles: [String], targetDate: String?)
        case uploads(urls: [URL], targetDate: String?)
    }

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

    /// 目标日期（从任务读出）。
    public var targetDate: String? { job?.targetDate }
    /// 源音频文件名。
    public var sourceFile: String { job?.sourceFile ?? "" }
    /// 预估剩余秒数。
    public var etaSeconds: Int? { job?.etaSeconds }
    /// 实时日志行。
    public var logLines: [String] { job?.logLines ?? [] }

    /// 创建并启动一次转写任务（音频已在后端可见，直接给路径）。
    public func start(audioFiles: [String], targetDate: String? = nil) async {
        lastInput = .paths(audioFiles: audioFiles, targetDate: targetDate)
        errorMessage = nil
        do {
            job = try await client.createJob(audioFiles: audioFiles, targetDate: targetDate)
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 上传本地文件后再建任务。对齐 Web：先逐个 upload 拿 file_path，再用这些路径建任务。
    /// 任一文件上传失败则中止并记录错误，不建任务。
    public func start(uploading urls: [URL], targetDate: String? = nil) async {
        lastInput = .uploads(urls: urls, targetDate: targetDate)
        uploadedPaths = []
        errorMessage = nil
        guard !urls.isEmpty else { return }

        isUploading = true
        defer { isUploading = false }

        var filePaths: [String] = []
        var firstFilename: String?
        var firstSize: Int?
        do {
            for url in urls {
                let result = try await client.upload(fileURL: url)
                filePaths.append(result.filePath)
                if firstFilename == nil {
                    firstFilename = result.filename
                    firstSize = result.sizeBytes
                }
            }
            // 记住已上传路径，retry 时复用，不再重复上传。
            uploadedPaths = filePaths
            uploadedSourceFile = firstFilename
            uploadedSourceSize = firstSize
            job = try await client.createJob(
                audioFiles: filePaths,
                targetDate: targetDate,
                sourceFile: firstFilename,
                sourceSizeBytes: firstSize
            )
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 用上次同样的输入重建任务。失败或从未启动则忽略。
    public func retry() async {
        guard let input = lastInput else { return }
        switch input {
        case let .paths(audioFiles, targetDate):
            await start(audioFiles: audioFiles, targetDate: targetDate)
        case let .uploads(urls, targetDate):
            // 文件已上传过则直接复用后端路径重建任务，避免在 inbox 产生重复副本；
            // 上传本身没成功（没有落地路径）才重新走上传流程。
            if !uploadedPaths.isEmpty {
                errorMessage = nil
                do {
                    job = try await client.createJob(
                        audioFiles: uploadedPaths,
                        targetDate: targetDate,
                        sourceFile: uploadedSourceFile,
                        sourceSizeBytes: uploadedSourceSize
                    )
                } catch {
                    errorMessage = String(describing: error)
                }
            } else {
                await start(uploading: urls, targetDate: targetDate)
            }
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
