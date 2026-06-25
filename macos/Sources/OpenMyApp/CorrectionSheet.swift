import SwiftUI
import OpenMyKit

/// 共享纠错表单：原文 wrong / 改成 right / 可选上下文 context 三个输入框 + 提交/取消。
/// 「划选纠错」和「新增校正」共用同一张表单——前者预填 wrong/context，后者三框留空。
///
/// 自身不直接调后端：绑定外部 CorrectionsViewModel（环境共享那一份），
/// 提交成功后通过 onSubmitted 回调把结果交回调用方，由上层弹 toast + 重载当天日报（对齐 Web）。
struct CorrectionSheet: View {
    /// 共享校正状态机（与侧栏词典同一实例）。
    @Bindable var viewModel: CorrectionsViewModel
    /// 当前日期：提交时随 body 带上，后端据此替换当天文件。可空（无当前日报时仅入词典）。
    var currentDate: String?
    /// 提交成功回调：带回结果，供上层 toast「已保存校正：wrong → right」并重载日报。
    var onSubmitted: (CorrectionResult) -> Void
    /// 取消/关闭回调。
    var onCancel: () -> Void

    /// 三个输入框的本地状态。wrong/context 可由初始化预填（划选场景）。
    @State private var wrong: String
    @State private var right: String
    @State private var context: String
    /// 提交进行中：禁用按钮防重复提交。
    @State private var submitting = false

    /// - Parameters:
    ///   - prefillWrong: 划选场景预填的原文（选中的文字）。
    ///   - prefillContext: 划选场景预填的上下文（命中句子）。
    init(
        viewModel: CorrectionsViewModel,
        currentDate: String?,
        prefillWrong: String = "",
        prefillContext: String = "",
        onSubmitted: @escaping (CorrectionResult) -> Void,
        onCancel: @escaping () -> Void
    ) {
        self.viewModel = viewModel
        self.currentDate = currentDate
        self.onSubmitted = onSubmitted
        self.onCancel = onCancel
        _wrong = State(initialValue: prefillWrong)
        _right = State(initialValue: "")
        _context = State(initialValue: prefillContext)
    }

    /// 提交可用：原文与改成都非空且不相等（本地校验，与 VM 一致）。
    private var canSubmit: Bool {
        let w = wrong.trimmingCharacters(in: .whitespacesAndNewlines)
        let r = right.trimmingCharacters(in: .whitespacesAndNewlines)
        return !w.isEmpty && !r.isEmpty && w != r
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            Text("纠错")
                .font(Theme.Typography.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            field(label: "原文", text: $wrong, placeholder: "识别错的词", focusOnAppear: wrong.isEmpty)
            field(label: "改成", text: $right, placeholder: "正确的词", focusOnAppear: !wrong.isEmpty)
            field(label: "上下文", text: $context, placeholder: "可选，这句话里出现的", focusOnAppear: false)

            OMErrorText(viewModel.errorMessage)

            HStack(spacing: Theme.Spacing.md) {
                Spacer()
                Button("取消", role: .cancel) { onCancel() }
                    .keyboardShortcut(.cancelAction)
                Button("保存") { submit() }
                    .keyboardShortcut(.defaultAction)
                    .buttonStyle(.borderedProminent)
                    .disabled(!canSubmit || submitting)
            }
        }
        .padding(Theme.Spacing.xl)
        .frame(width: 380)
    }

    private func field(
        label: String,
        text: Binding<String>,
        placeholder: String,
        focusOnAppear: Bool
    ) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(label)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
            TextField(placeholder, text: text)
                .textFieldStyle(.roundedBorder)
                .onSubmit { if canSubmit { submit() } }
        }
    }

    private func submit() {
        guard !submitting else { return }
        submitting = true
        Task {
            let ok = await viewModel.submit(
                wrong: wrong,
                right: right,
                context: context,
                date: currentDate
            )
            submitting = false
            if ok, let result = viewModel.lastResult {
                onSubmitted(result)
            }
        }
    }
}
