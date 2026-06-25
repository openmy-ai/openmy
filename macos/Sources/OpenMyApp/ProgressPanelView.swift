import SwiftUI
import OpenMyKit

/// 四阶段进度面板：实时显示转写 / 清洗 / 场景切分 / 蒸馏，并提供暂停 / 继续 / 取消 / 跳过。
struct ProgressPanelView: View {
    @Bindable var job: JobViewModel
    /// 终态后点击「查看日报」回调：清空任务并刷新日报列表。
    var onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
            header

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
        }
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
            if job.job?.isTerminal == true {
                // 终态：回到日报浏览
                Button("查看日报", action: onDismiss)
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
            } else {
                if job.job?.status == "paused" {
                    Button("继续") { Task { await job.resume() } }
                        .buttonStyle(.borderedProminent)
                } else if job.canPause {
                    Button("暂停") { Task { await job.pause() } }
                        .buttonStyle(.bordered)
                }
                if job.canSkip {
                    Button("跳过这步") { Task { await job.skip() } }
                        .buttonStyle(.bordered)
                }
                Spacer()
                Button("取消", role: .destructive) { Task { await job.cancel() } }
                    .buttonStyle(.bordered)
            }
        }
        .controlSize(.regular)
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
