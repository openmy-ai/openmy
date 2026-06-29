import Foundation
import Observation

/// 校正系统状态机：持有词典列表，负责加载与提交。
/// 像 ToastCenter 一样供多视图共享（环境注入）：侧栏校正词典、划选纠错、新增校正都读同一份 corrections。
///
/// 提交成功后自动 reload 列表，保证侧栏与设置面板即时刷新（对齐 Web refreshCorrectionsFeed）。
@MainActor
@Observable
public final class CorrectionsViewModel {
    /// 当前校正词典（wrong → right）。
    public private(set) var corrections: [Correction] = []
    /// 最近一次提交结果，供调用方判断成功并取替换次数。
    public private(set) var lastResult: CorrectionResult?
    /// 错误信息（加载/提交异常，或后端 success=false 的原因）。
    public private(set) var errorMessage: String?

    private let client: APIClient

    public init(client: APIClient) {
        self.client = client
    }

    /// 加载校正词典。失败时 errorMessage 置位，corrections 保持原值。
    public func load() async {
        errorMessage = nil
        do {
            corrections = try await client.corrections()
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 提交一条校正。返回是否成功（供视图触发 toast / 重载日报）。
    ///
    /// - 空输入校验在本地完成（wrong/right trim 后非空且不相等），不发请求，与 Web 一致。
    /// - 后端 success=false 时把 error 写入 errorMessage，返回 false。
    /// - 成功后 reload 列表并把结果存入 lastResult。
    @discardableResult
    public func submit(
        wrong: String,
        right: String,
        context: String = "",
        date: String? = nil,
        syncVocab: Bool = true
    ) async -> Bool {
        errorMessage = nil
        let w = wrong.trimmingCharacters(in: .whitespacesAndNewlines)
        let r = right.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !w.isEmpty, !r.isEmpty else {
            errorMessage = "原文和改成内容都不能为空"
            return false
        }
        guard w != r else {
            errorMessage = "原文和改成内容相同"
            return false
        }
        do {
            let result = try await client.submitCorrection(
                wrong: w, right: r,
                context: context.trimmingCharacters(in: .whitespacesAndNewlines),
                date: date, syncVocab: syncVocab
            )
            lastResult = result
            guard result.success else {
                errorMessage = result.error ?? "保存失败"
                return false
            }
            await load()
            return true
        } catch {
            errorMessage = String(describing: error)
            return false
        }
    }
}
