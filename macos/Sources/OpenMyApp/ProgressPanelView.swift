import SwiftUI
import OpenMyKit

/// 四阶段进度面板：实时显示转写 / 清洗 / 场景切分 / 蒸馏，并提供暂停 / 取消 / 跳过。
struct ProgressPanelView: View {
    @Bindable var job: JobViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack {
                Text("处理进度").font(.title2).bold()
                Spacer()
                Text(statusText).font(.subheadline).foregroundStyle(.secondary)
            }

            if let steps = job.job?.steps {
                VStack(spacing: 10) {
                    ForEach(steps) { step in
                        StepRow(step: step)
                    }
                }
            }

            controls

            if let err = job.errorMessage {
                Text(err).font(.footnote).foregroundStyle(.red)
            }
            Spacer()
        }
        .padding(28)
        .onDisappear { job.stopPolling() }
    }

    private var controls: some View {
        HStack(spacing: 12) {
            if job.canPause {
                Button("暂停") { Task { await job.pause() } }
            }
            if job.canSkip {
                Button("跳过这步") { Task { await job.skip() } }
            }
            if job.isActive {
                Button("取消", role: .destructive) { Task { await job.cancel() } }
            }
        }
    }

    private var statusText: String {
        switch job.job?.status {
        case "queued": return "排队中"
        case "running": return "处理中"
        case "paused": return "已暂停"
        case "succeeded": return "已完成"
        case "partial": return "部分完成"
        case "failed": return "失败"
        case "cancelled": return "已取消"
        default: return job.job?.status ?? ""
        }
    }
}

private struct StepRow: View {
    let step: PipelineStep

    var body: some View {
        HStack(spacing: 12) {
            icon
            VStack(alignment: .leading, spacing: 2) {
                Text(step.label).font(.headline)
                if !step.resultSummary.isEmpty {
                    Text(step.resultSummary).font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer()
            if step.status == "running" {
                ProgressView().controlSize(.small)
            }
        }
        .padding(12)
        .background(.quaternary.opacity(0.4))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var icon: some View {
        Group {
            switch step.status {
            case "done": Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
            case "running": Image(systemName: "circle.dotted").foregroundStyle(.tint)
            case "failed": Image(systemName: "xmark.circle.fill").foregroundStyle(.red)
            case "skipped": Image(systemName: "forward.circle.fill").foregroundStyle(.secondary)
            default: Image(systemName: "circle").foregroundStyle(.secondary)
            }
        }
        .font(.title3)
    }
}
