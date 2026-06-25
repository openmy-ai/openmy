import SwiftUI
import OpenMyKit

/// 四阶段进度面板：实时显示转写 / 清洗 / 场景切分 / 蒸馏，并提供暂停 / 继续 / 取消 / 跳过。
struct ProgressPanelView: View {
    @Bindable var job: JobViewModel
    /// 终态后点击「查看日报 / 返回」回调：由调用方负责跳到目标日期日报或清空任务。
    var onDismiss: () -> Void
    /// 失败态点击「去选转写引擎」时回到首次配置（重新选引擎）。
    var onReconfigure: () -> Void = {}

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
            header

            metaRow

            if isTerminalFailure {
                failureBanner
            }

            if let steps = job.job?.steps, !steps.isEmpty {
                stepTimeline(steps)
            }

            controls

            OMErrorText(job.errorMessage)

            Spacer()
        }
        .padding(Theme.Spacing.xxl)
        .onDisappear { job.stopPolling() }
    }

    // MARK: - 头部：标题 + 状态徽章 + 总进度条

    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.md) {
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.md) {
                Text("处理进度").font(Theme.Typography.sectionTitle)
                statusBadge
                Spacer()
                if let pct = job.job?.progressPct {
                    Text("\(pct)%")
                        .font(Theme.Typography.metric)
                        .foregroundStyle(Theme.Palette.accent)
                        .monospacedDigit()
                }
            }

            ProgressView(value: Double(job.job?.progressPct ?? 0), total: 100)
                .tint(progressTint)

            // 进行中（非终态）显示预估剩余时间，对齐 Web 首页卡片。
            if job.job?.isTerminal == false {
                Label(etaText, systemImage: "clock")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .monospacedDigit()
            }
        }
        .omSection()
    }

    // MARK: - 元信息：源文件名 + 目标日期

    /// 源文件名与目标日期一行展示，对齐 Web `源文件 · 日期` 格式。无信息则不渲染。
    @ViewBuilder
    private var metaRow: some View {
        let parts = [sourceFileName, job.targetDate].compactMap { $0 }
        if !parts.isEmpty {
            HStack(spacing: Theme.Spacing.sm) {
                Image(systemName: "waveform")
                    .font(.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                Text(parts.joined(separator: " · "))
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
            }
        }
    }

    /// 源文件名（空串归一为 nil，让 metaRow 判空一致）。
    private var sourceFileName: String? {
        let name = job.sourceFile
        return name.isEmpty ? nil : name
    }

    /// 预估剩余时间文案，1:1 对齐 Web `formatEtaSeconds`：
    /// nil 或 <=0 → 预估中…；<60 → N 秒；否则 m:ss。
    private var etaText: String {
        guard let seconds = job.etaSeconds, seconds > 0 else { return "预估中…" }
        if seconds < 60 { return "\(seconds) 秒" }
        let minutes = seconds / 60
        let remain = seconds % 60
        return String(format: "%d:%02d", minutes, remain)
    }

    // MARK: - 失败态红条

    /// 失败 / 取消 / 中断时的红色提示条，显示后端 error（无则给兜底文案）。
    private var failureBanner: some View {
        let detail = job.job?.error ?? ""
        return HStack(alignment: .top, spacing: Theme.Spacing.sm) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(Theme.Palette.danger)
            Text(detail.isEmpty ? "处理失败，请重试。" : detail)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.primaryText)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.md)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.Palette.danger.opacity(0.12))
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.card))
        .omSection()
    }

    @ViewBuilder
    private var statusBadge: some View {
        if let status = job.job?.status {
            OMBadge(JobStatusText.job(status), kind: isTerminalFailure ? .neutral : .accent)
        }
    }

    /// 失败 / 取消 / 中断时进度条转为危险色，否则用强调色。
    private var progressTint: Color {
        isTerminalFailure ? Theme.Palette.danger : Theme.Palette.accent
    }

    private var isTerminalFailure: Bool {
        guard let status = job.job?.status else { return false }
        return ["failed", "cancelled", "interrupted"].contains(status)
    }

    // MARK: - 步骤时间线

    private func stepTimeline(_ steps: [PipelineStep]) -> some View {
        VStack(spacing: 0) {
            ForEach(Array(steps.enumerated()), id: \.element.id) { index, step in
                StepRow(step: step, isLast: index == steps.count - 1)
            }
        }
        .omSection()
    }

    // MARK: - 控制按钮

    @ViewBuilder
    private var controls: some View {
        HStack(spacing: Theme.Spacing.md) {
            if isTerminalFailure {
                // 失败终态：重试 + 去重新选转写引擎，外加回到日报浏览。
                Button("重试") { Task { await job.retry() } }
                    .omButton(.primary)
                Button("去选转写引擎", action: onReconfigure)
                    .omButton(.secondary)
                Spacer()
                Button("返回", action: onDismiss)
                    .omButton(.secondary)
            } else if job.job?.isTerminal == true {
                // 成功终态：onDismiss 由 MainView 注入，内部读 target_date 跳转到对应日报。
                Button("查看日报", action: onDismiss)
                    .omButton(.primary)
            } else {
                if job.job?.status == "paused" {
                    Button("继续") { Task { await job.resume() } }
                        .omButton(.primary)
                } else if job.canPause {
                    Button("暂停") { Task { await job.pause() } }
                        .omButton(.primary)
                }
                if job.canSkip {
                    Button("跳过这步") { Task { await job.skip() } }
                        .omButton(.secondary)
                }
                Spacer()
                Button("取消", role: .destructive) { Task { await job.cancel() } }
                    .omButton(.destructive)
            }
        }
    }
}

// MARK: - 单个步骤行（时间线样式）

private struct StepRow: View {
    let step: PipelineStep
    /// 是否为最后一步：决定是否绘制向下连接线。
    let isLast: Bool

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.md) {
            timelineRail
            content
        }
    }

    /// 左侧时间线：状态圆点 + 向下连接线。
    private var timelineRail: some View {
        VStack(spacing: 0) {
            indicator
            if !isLast {
                Rectangle()
                    .fill(Theme.Palette.secondaryText.opacity(0.25))
                    .frame(width: 1.5)
                    .frame(maxHeight: .infinity)
            }
        }
        .frame(width: 22)
    }

    @ViewBuilder
    private var indicator: some View {
        Group {
            switch step.status {
            case "done":
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(Theme.Palette.success)
            case "running":
                ProgressView().controlSize(.small)
            case "failed":
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(Theme.Palette.danger)
            case "skipped":
                Image(systemName: "forward.circle.fill")
                    .foregroundStyle(Theme.Palette.secondaryText)
            default:
                Image(systemName: "circle")
                    .foregroundStyle(Theme.Palette.secondaryText.opacity(0.5))
            }
        }
        .font(.title3)
        .frame(width: 22, height: 22)
    }

    /// 右侧内容卡片：标题 + 状态文案 + 结果摘要。
    private var content: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            HStack(spacing: Theme.Spacing.sm) {
                Text(step.label)
                    .font(Theme.Typography.cardTitle)
                    .foregroundStyle(titleColor)
                Spacer()
                Text(JobStatusText.step(step.status))
                    .font(Theme.Typography.caption)
                    .foregroundStyle(statusColor)
            }
            if !step.resultSummary.isEmpty {
                Text(step.resultSummary)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .omCard()
        .padding(.bottom, isLast ? 0 : Theme.Spacing.sm)
    }

    /// 进行中的步骤标题用主文字色突出，其余次要色，已完成保持主色。
    private var titleColor: Color {
        switch step.status {
        case "running", "done", "failed": return Theme.Palette.primaryText
        default: return Theme.Palette.secondaryText
        }
    }

    private var statusColor: Color {
        switch step.status {
        case "done": return Theme.Palette.success
        case "running": return Theme.Palette.accent
        case "failed": return Theme.Palette.danger
        default: return Theme.Palette.secondaryText
        }
    }
}
