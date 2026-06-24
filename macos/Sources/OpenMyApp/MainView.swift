import SwiftUI
import OpenMyKit
import UniformTypeIdentifiers

/// 主界面：左侧日期列表，右侧日报 / 进行中的任务进度。
struct MainView: View {
    let client: APIClient
    @State private var briefings: BriefingListViewModel
    @State private var job: JobViewModel
    @State private var isDropTargeted = false

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
            if job.isActive || job.job != nil {
                ProgressPanelView(job: job)
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
            if let err = briefings.errorMessage {
                Text(err).font(.footnote).foregroundStyle(.red)
            }
        }
    }

    private func startJob(with urls: [URL]) {
        let paths = urls.map(\.path)
        guard !paths.isEmpty else { return }
        Task {
            await job.start(audioFiles: paths)
            job.startPolling()
        }
    }
}
