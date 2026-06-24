import SwiftUI
import OpenMyKit

/// 主界面：左侧日期列表，右侧日报 / 进行中的任务进度。
struct MainView: View {
    let client: APIClient
    @State private var briefings: BriefingListViewModel
    @State private var job: JobViewModel
    @State private var isDropTargeted = false
    @State private var dropNote: String?

    init(client: APIClient) {
        self.client = client
        _briefings = State(initialValue: BriefingListViewModel(client: client))
        _job = State(initialValue: JobViewModel(client: client))
    }

    var body: some View {
        NavigationSplitView {
            List(selection: Binding(
                get: { briefings.selectedDate },
                set: { if let d = $0 { Task { await briefings.select(date: d) } } }
            )) {
                Section("日报") {
                    ForEach(briefings.dates) { entry in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(entry.date).font(.headline)
                            Text(entry.summary.isEmpty ? "\(entry.segments) 段 · \(entry.wordCount) 字" : entry.summary)
                                .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                        }
                        .tag(entry.date)
                    }
                }
            }
            .frame(minWidth: 240)
        } detail: {
            detail
        }
        .task { await briefings.loadDates() }
    }

    @ViewBuilder
    private var detail: some View {
        ZStack {
            if job.job != nil {
                ProgressPanelView(job: job, onDismiss: dismissJob)
            } else if let briefing = briefings.selectedBriefing {
                BriefingDetailView(briefing: briefing)
            } else {
                dropPrompt
            }
        }
        .dropDestination(for: URL.self) { urls, _ in
            startJob(with: urls)
            return true
        } isTargeted: { isDropTargeted = $0 }
        .overlay {
            if isDropTargeted {
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(.tint, style: StrokeStyle(lineWidth: 2, dash: [8]))
                    .padding(8)
            }
        }
    }

    private var dropPrompt: some View {
        VStack(spacing: 12) {
            Image(systemName: "square.and.arrow.down.on.square")
                .font(.system(size: 48)).foregroundStyle(.secondary)
            Text("把录音文件拖到这里开始处理").foregroundStyle(.secondary)
            if let note = dropNote {
                Text(note).font(.footnote).foregroundStyle(.orange)
            }
            if let err = briefings.errorMessage {
                Text(err).font(.footnote).foregroundStyle(.red)
            }
        }
    }

    private func startJob(with urls: [URL]) {
        // 过滤受支持的格式，并对云端引擎设 5 个批量上限（见 CLAUDE.md 云端批量限制）。
        let dropped = urls.map(\.path)
        let paths = AudioFileFilter.eligible(dropped, maxBatch: 5)
        guard !paths.isEmpty else {
            dropNote = "拖入的文件都不是支持的音频/视频格式"
            return
        }
        dropNote = paths.count < dropped.count ? "已忽略部分文件，只处理前 \(paths.count) 个" : nil
        Task {
            await job.start(audioFiles: paths)
            job.startPolling()
        }
    }

    /// 任务终态后：清空任务并刷新日报列表，让刚生成的日报出现。
    private func dismissJob() {
        job.clear()
        Task { await briefings.loadDates() }
    }
}
