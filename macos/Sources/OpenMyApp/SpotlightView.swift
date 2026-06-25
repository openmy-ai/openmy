import SwiftUI
import OpenMyKit

/// 全局搜索浮层（spotlight）：居中浮层 + 顶部自动聚焦的搜索框，
/// 下面把命中按日期分组展示，命中片段用基础层 parseHighlight 把 <mark> 渲染成强调色加粗。
/// 键盘：上下方向键移动选中项、回车跳转（onSelect）、Esc 关闭（onClose）。
///
/// 绑定一个外部传入的 SearchViewModel，自身只负责呈现与键盘交互，
/// 检索逻辑、防过期、选中序号全部由 SearchViewModel 状态机持有。
struct SpotlightView: View {
    @Bindable var viewModel: SearchViewModel
    /// 命中后跳转：交给上层用 SearchFocus 做日期切换 + 段落定位 + 关键词高亮。
    var onSelect: (SearchFocus) -> Void
    /// 关闭浮层（Esc 或点击背景蒙层）。
    var onClose: () -> Void
    /// 最近的日期（空查询时作为快捷入口，对齐 Web spotlight 的最近记录）。
    var recentDates: [DayEntry] = []

    /// 搜索框聚焦态，出现时自动抢焦点。
    @FocusState private var searchFocused: Bool
    /// 检索去抖序号：每次输入 +1，延迟后只有最新一次真正触发 search。
    @State private var debounceToken = 0

    var body: some View {
        ZStack(alignment: .top) {
            // 半透明背景蒙层：点击空白关闭。
            Color.black.opacity(0.32)
                .ignoresSafeArea()
                .onTapGesture { onClose() }

            panel
                .frame(maxWidth: 640)
                .padding(.top, Theme.Spacing.xxl * 2)
                .padding(.horizontal, Theme.Spacing.xxl)
        }
        // 方向键 / 回车 / Esc：浮层级别统一接管，避免焦点散落在子视图。
        .onKeyPress(.downArrow) { viewModel.moveSelection(1); return .handled }
        .onKeyPress(.upArrow) { viewModel.moveSelection(-1); return .handled }
        .onKeyPress(.return) { submitSelection(); return .handled }
        .onKeyPress(.escape) { onClose(); return .handled }
        .onAppear { searchFocused = true }
    }

    // MARK: - 浮层主体

    private var panel: some View {
        VStack(spacing: 0) {
            searchField
            Divider()
            content
        }
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.container))
        .overlay {
            RoundedRectangle(cornerRadius: Theme.Radius.container)
                .strokeBorder(Theme.Palette.secondaryText.opacity(0.15), lineWidth: 1)
        }
        .shadow(radius: 24, y: 8)
    }

    private var searchField: some View {
        HStack(spacing: Theme.Spacing.md) {
            Image(systemName: "magnifyingglass")
                .font(Theme.Typography.sectionTitle)
                .foregroundStyle(Theme.Palette.secondaryText)

            TextField("搜索所有记录", text: $viewModel.query)
                .textFieldStyle(.plain)
                .font(Theme.Typography.sectionTitle)
                .foregroundStyle(Theme.Palette.primaryText)
                .focused($searchFocused)
                .onSubmit { submitSelection() }
                .onChange(of: viewModel.query) { _, _ in scheduleSearch() }

            if !viewModel.query.isEmpty {
                Button {
                    viewModel.clear()
                    searchFocused = true
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Theme.Palette.secondaryText)
                }
                .omButton(.ghost, size: .icon)
                .help("清空")
            }
        }
        .padding(.horizontal, Theme.Spacing.lg)
        .padding(.vertical, Theme.Spacing.lg)
    }

    // MARK: - 内容区（空提示 / 空结果 / 结果列表）

    @ViewBuilder
    private var content: some View {
        let trimmed = viewModel.query.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            if recentDates.isEmpty {
                stateHint(icon: "text.magnifyingglass", title: "输入关键词搜索所有记录", subtitle: "在全部日报的逐段转写里查找")
            } else {
                recentList
            }
        } else if let error = viewModel.errorMessage {
            VStack(spacing: Theme.Spacing.sm) {
                Image(systemName: "exclamationmark.triangle")
                    .font(Theme.Typography.sectionTitle)
                    .foregroundStyle(Theme.Palette.danger)
                OMErrorText("搜索失败：\(error)")
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.xxl)
        } else if viewModel.results.isEmpty {
            stateHint(icon: "questionmark.circle", title: "没有找到「\(trimmed)」", subtitle: "换个关键词试试")
        } else {
            resultList
        }
    }

    /// 空查询时的最近记录快捷入口（最多 5 天），对齐 Web spotlight。
    private var recentList: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("最近记录")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
                .padding(.horizontal, Theme.Spacing.lg)
                .padding(.top, Theme.Spacing.md)
            ForEach(recentDates.prefix(5)) { entry in
                Button {
                    onSelect(SearchFocus(date: entry.date, time: "", query: ""))
                } label: {
                    HStack(spacing: Theme.Spacing.md) {
                        Image(systemName: "calendar")
                            .foregroundStyle(Theme.Palette.accent)
                        VStack(alignment: .leading, spacing: 0) {
                            Text(entry.date)
                                .font(Theme.Typography.cardTitle)
                                .foregroundStyle(Theme.Palette.primaryText)
                            if !entry.summary.isEmpty {
                                Text(entry.summary)
                                    .font(Theme.Typography.caption)
                                    .foregroundStyle(Theme.Palette.secondaryText)
                                    .lineLimit(1)
                            }
                        }
                        Spacer()
                        Text("\(entry.segments) 段")
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Palette.secondaryText)
                    }
                    .padding(.horizontal, Theme.Spacing.lg)
                    .padding(.vertical, Theme.Spacing.md)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.bottom, Theme.Spacing.md)
    }

    /// 空提示 / 空结果共用的居中占位。
    private func stateHint(icon: String, title: String, subtitle: String) -> some View {
        VStack(spacing: Theme.Spacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 32, weight: .light))
                .foregroundStyle(Theme.Palette.secondaryText)
            Text(title)
                .font(Theme.Typography.cardTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Text(subtitle)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.xxl)
    }

    private var resultList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: Theme.Spacing.lg, pinnedViews: [.sectionHeaders]) {
                    ForEach(viewModel.groupedByDate, id: \.date) { group in
                        Section {
                            ForEach(group.results) { result in
                                resultRow(result)
                                    .id(result.id)
                            }
                        } header: {
                            dateHeader(group.date, count: group.results.count)
                        }
                    }
                }
                .padding(Theme.Spacing.md)
            }
            // 选中项变化时滚动到可见区，配合方向键导航。
            .onChange(of: viewModel.selectedResult?.id) { _, newID in
                guard let newID else { return }
                withAnimation(.easeOut(duration: 0.15)) {
                    proxy.scrollTo(newID, anchor: .center)
                }
            }
        }
        .frame(maxHeight: 420)
    }

    private func dateHeader(_ date: String, count: Int) -> some View {
        HStack(spacing: Theme.Spacing.sm) {
            Text(date)
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
            OMBadge("\(count) 条", kind: .neutral)
            Spacer()
        }
        .padding(.horizontal, Theme.Spacing.sm)
        .padding(.vertical, Theme.Spacing.xs)
        .background(.regularMaterial)
    }

    // MARK: - 单条命中

    private func resultRow(_ result: SearchResult) -> some View {
        let isSelected = viewModel.selectedResult?.id == result.id
        return HStack(alignment: .top, spacing: Theme.Spacing.md) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs / 2) {
                highlightedContext(result.context)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.primaryText)
                    .fixedSize(horizontal: false, vertical: true)
                    .multilineTextAlignment(.leading)
            }

            Spacer(minLength: Theme.Spacing.md)

            VStack(alignment: .trailing, spacing: Theme.Spacing.xs) {
                if !result.time.isEmpty {
                    Text(result.time)
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.accent)
                        .monospacedDigit()
                }
                OMBadge(result.date, kind: .neutral)
            }
        }
        .padding(.horizontal, Theme.Spacing.md)
        .padding(.vertical, Theme.Spacing.sm)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: Theme.Radius.card)
                .fill(isSelected ? Theme.Palette.accent.opacity(0.16) : Color.clear)
        )
        .contentShape(Rectangle())
        .onTapGesture { select(result) }
    }

    /// 把带 <mark> 的片段用 parseHighlight 切段，命中段渲染成强调色加粗。
    private func highlightedContext(_ html: String) -> Text {
        let segments = parseHighlight(html)
        return segments.reduce(Text("")) { acc, seg in
            var piece = Text(seg.text)
            if seg.isMatch {
                piece = piece
                    .fontWeight(.bold)
                    .foregroundColor(Theme.Palette.accent)
            }
            return acc + piece
        }
    }

    // MARK: - 动作

    /// 回车跳转：用当前选中项构造 SearchFocus 交回上层。
    private func submitSelection() {
        guard let result = viewModel.selectedResult else { return }
        select(result)
    }

    private func select(_ result: SearchResult) {
        let focus = SearchFocus(
            date: result.date,
            time: result.time,
            query: viewModel.query.trimmingCharacters(in: .whitespacesAndNewlines)
        )
        onSelect(focus)
    }

    /// 输入去抖：停止输入约 250ms 后再发检索，避免每个字符打一次后端。
    private func scheduleSearch() {
        debounceToken += 1
        let token = debounceToken
        Task {
            try? await Task.sleep(nanoseconds: 250_000_000)
            guard token == debounceToken else { return }
            await viewModel.search()
        }
    }
}
