import SwiftUI
import OpenMyKit

/// 校正词典面板：以 `.sheet` 呈现，列出全部校正（wrong → right + 累计次数 + 上下文）。
/// 顶部「新增校正」按钮打开共享的 `CorrectionSheet`（三框留空）；词典为空时给空状态提示。
///
/// 数据来自环境里共享的 `CorrectionsViewModel`（与划选纠错、设置面板新增校正读同一份 corrections）。
/// 接入方式（由上层负责，本视图不改根 App）：
/// 与 `ToastCenter` 一样在 App 根 `.environment(correctionsVM)` 注入一份共享实例，
/// 本面板通过 `@Environment(CorrectionsViewModel.self)` 取用，提交后 VM 内部 `await load()` 自动刷新列表。
///
/// 提交成功后弹 toast「已保存校正：wrong → right」（toast 同样取自环境的 `ToastCenter`），
/// 当天日报的重载由调用方在更外层据 `currentDate` 触发，本面板只负责词典本身。
struct CorrectionsView: View {
    /// 共享校正状态机（与侧栏划选纠错、设置面板同一实例）。
    @Environment(CorrectionsViewModel.self) private var viewModel
    /// 全局 Toast 中心：提交成功后给反馈。
    @Environment(ToastCenter.self) private var toastCenter

    /// 当前日报日期：新增校正提交时随 body 带上，供后端替换当天文件。可空（无当前日报时仅入词典）。
    var currentDate: String?
    /// 关闭整个面板。
    var onClose: () -> Void

    /// 「新增校正」表单是否呈现。
    @State private var showAddSheet = false

    init(currentDate: String? = nil, onClose: @escaping () -> Void = {}) {
        self.currentDate = currentDate
        self.onClose = onClose
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
            header

            OMErrorText(viewModel.errorMessage)

            if viewModel.corrections.isEmpty {
                emptyState
            } else {
                list
            }
        }
        .padding(Theme.Spacing.xl)
        .frame(width: 460, height: 520)
        .task { await viewModel.load() }
        .sheet(isPresented: $showAddSheet) {
            CorrectionSheet(
                viewModel: viewModel,
                currentDate: currentDate,
                onSubmitted: { result in
                    showAddSheet = false
                    toastCenter.show(toastText(for: result))
                },
                onCancel: { showAddSheet = false }
            )
        }
    }

    // MARK: - 头部

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.sm) {
            Text("校正词典")
                .font(Theme.Typography.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            if !viewModel.corrections.isEmpty {
                OMBadge("\(viewModel.corrections.count) 条")
            }
            Spacer()
            Button {
                showAddSheet = true
            } label: {
                Label("新增校正", systemImage: "plus")
            }
            .buttonStyle(.borderedProminent)
            Button("关闭", role: .cancel) { onClose() }
                .keyboardShortcut(.cancelAction)
        }
    }

    // MARK: - 列表

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.sm) {
                ForEach(viewModel.corrections) { correction in
                    row(correction)
                }
            }
        }
    }

    private func row(_ correction: Correction) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            HStack(spacing: Theme.Spacing.sm) {
                Text(correction.wrong)
                    .font(Theme.Typography.cardTitle)
                    .foregroundStyle(Theme.Palette.danger)
                Image(systemName: "arrow.right")
                    .font(.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                Text(correction.right)
                    .font(Theme.Typography.cardTitle)
                    .foregroundStyle(Theme.Palette.success)
                Spacer()
                if correction.count > 0 {
                    OMBadge("\(correction.count) 次")
                }
            }

            if !correction.context.isEmpty {
                Text(correction.context)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .omCard()
    }

    // MARK: - 空状态

    private var emptyState: some View {
        VStack(spacing: Theme.Spacing.md) {
            Image(systemName: "character.book.closed")
                .font(.system(size: 36, weight: .light))
                .foregroundStyle(Theme.Palette.secondaryText)
            Text("还没有校正记录")
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Text("识别错的词改对一次，下次就会自动替换。点「新增校正」加第一条。")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(Theme.Spacing.xl)
    }

    // MARK: - 辅助

    /// 提交成功的 toast 文案，拼成「已保存校正：wrong → right」。
    ///
    /// `CorrectionSheet` 的回调只回传 `CorrectionResult`，不含本次输入的 wrong/right。
    /// 提交成功时 VM 已 `await load()` 刷新列表，故取 `lastUpdated` 最新的那条作为本次提交项；
    /// 拿不到（极少数老数据缺 lastUpdated）则退化为通用文案，不冒充具体内容。
    private func toastText(for result: CorrectionResult) -> String {
        _ = result
        if let latest = viewModel.corrections
            .filter({ !$0.lastUpdated.isEmpty })
            .max(by: { $0.lastUpdated < $1.lastUpdated }) {
            return "已保存校正：\(latest.wrong) → \(latest.right)"
        }
        return "已保存校正"
    }
}

#if DEBUG
// 预览用真实 VM，未连后端时 load() 失败 -> corrections 为空，呈现空状态。
// 列表样式无法在不改 VM(corrections 为 private(set)) 的前提下灌假数据，
// 故这里只验证空状态与整体布局；列表行样式由 row(_:) 的实现保证。
#Preview {
    CorrectionsView(currentDate: "2026-06-24")
        .environment(CorrectionsViewModel(client: APIClient()))
        .environment(ToastCenter(autoDismissSeconds: 0))
}
#endif
