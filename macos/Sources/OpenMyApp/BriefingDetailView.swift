import SwiftUI
import OpenMyKit

/// 日报详情。
struct BriefingDetailView: View {
    let briefing: Briefing

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text(briefing.date).font(.largeTitle).bold()
                stats

                if !briefing.summary.isEmpty {
                    section("摘要") { Text(briefing.summary) }
                }
                if !briefing.timeBlocks.isEmpty {
                    section("时间线") {
                        ForEach(briefing.timeBlocks, id: \.period) { tb in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(tb.period).font(.subheadline).bold()
                                Text(tb.summary).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                if !briefing.keyEvents.isEmpty {
                    section("关键事件") { bullets(briefing.keyEvents) }
                }
                if !briefing.todosOpen.isEmpty {
                    section("待办") { bullets(briefing.todosOpen) }
                }
                if !briefing.insights.isEmpty {
                    section("洞察") {
                        ForEach(briefing.insights, id: \.topic) { i in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(i.topic).font(.subheadline).bold()
                                Text(i.content).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var stats: some View {
        HStack(spacing: 20) {
            stat("\(briefing.totalScenes)", "场景")
            stat("\(briefing.totalWords)", "字")
            stat(String(format: "%.1f", briefing.voiceHours), "小时语音")
        }
    }

    private func stat(_ value: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.title3).bold()
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
    }

    private func bullets(_ items: [String]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(items, id: \.self) { item in
                HStack(alignment: .top, spacing: 8) {
                    Text("•")
                    Text(item)
                }
            }
        }
    }

    @ViewBuilder
    private func section<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.title3).bold()
            content()
        }
    }
}
