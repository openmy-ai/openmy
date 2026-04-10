#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[2] / "app" / "index.html"


class TestFrontendShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = INDEX_HTML.read_text(encoding="utf-8")

    def test_index_preserves_reading_first_shell(self):
        self.assertIn('class="view-tabs"', self.content)
        self.assertIn('id="tab-briefing"', self.content)
        self.assertIn('id="tab-timeline"', self.content)
        self.assertIn('id="tab-table"', self.content)
        self.assertIn('id="tab-charts"', self.content)
        self.assertIn("props-grid", self.content)
        self.assertIn("briefing-grid", self.content)

    def test_index_adds_context_tabs_without_replacing_reader_views(self):
        self.assertIn('id="tab-overview"', self.content)
        self.assertIn("概览", self.content)

    def test_index_fetches_context_and_day_payloads(self):
        self.assertIn("/api/context", self.content)
        self.assertIn("/api/context/loops", self.content)
        self.assertIn("/api/context/projects", self.content)
        self.assertIn("/api/context/decisions", self.content)
        self.assertIn("/api/pipeline/jobs", self.content)
        self.assertRegex(self.content, r"/api/date/\$\{[^}]+\}/meta")
        self.assertRegex(self.content, r"/api/date/\$\{[^}]+\}/briefing")

    def test_index_renders_meta_panels_inside_day_view(self):
        self.assertIn("renderMetaPanels", self.content)
        self.assertIn("view-overview", self.content)
        self.assertIn("打算做什么", self.content)
        self.assertIn("记住了什么", self.content)
        self.assertIn("决定了什么", self.content)
        self.assertIn("发生了什么", self.content)

    def test_index_exposes_correction_actions(self):
        self.assertIn("loops/close", self.content)
        self.assertIn("loops/reject", self.content)
        self.assertIn("projects/merge", self.content)
        self.assertIn("projects/reject", self.content)
        self.assertIn("decisions/reject", self.content)

    def test_index_contains_pipeline_job_panel(self):
        self.assertIn("pipelineJobsList", self.content)
        self.assertIn("pipelineJobDetail", self.content)
        self.assertIn("createPipelineJob", self.content)
        self.assertIn("refreshPipelineJobs", self.content)
        self.assertIn("刷新上下文", self.content)
        self.assertIn("重新运行", self.content)

    def test_timeline_distillation_uses_unified_bold_markup(self):
        match = re.search(
            r"function getSegmentDistillation\(segment, meta\) \{(?P<body>.*?)\n\}\n\nfunction renderBriefingView",
            self.content,
            re.S,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("📌 <strong>摘要</strong>", body)
        self.assertIn("📌 <strong>片段</strong>", body)
        self.assertNotIn("seg-distilled-placeholder", body)

    def test_mobile_layout_has_single_column_breakpoint(self):
        self.assertRegex(
            self.content,
            r"@media\s*\(max-width:\s*900px\)\s*\{[^}]*\.app\s*\{[^}]*grid-template-columns:\s*1fr;",
        )

    def test_spotlight_overlay_dom_structure(self):
        """Spotlight 浮窗的 DOM 骨架必须存在"""
        self.assertIn('id="spotlightOverlay"', self.content)
        self.assertIn('id="spotlightInput"', self.content)
        self.assertIn('id="spotlightResults"', self.content)
        self.assertIn("spotlight-modal", self.content)
        self.assertIn("spotlight-input-wrapper", self.content)

    def test_spotlight_sidebar_trigger_button(self):
        """侧边栏必须有触发按钮和快捷键提示"""
        self.assertIn("sidebar-search-btn", self.content)
        self.assertIn("openSpotlight()", self.content)
        self.assertIn("⌘K", self.content)

    def test_spotlight_js_functions_exist(self):
        """Spotlight 核心函数必须全部定义"""
        self.assertIn("function openSpotlight()", self.content)
        self.assertIn("function closeSpotlight(", self.content)
        self.assertIn("async function runSearchSpotlight(", self.content)
        self.assertIn("async function jumpToSearchResult(", self.content)

    def test_spotlight_keyboard_shortcut_listener(self):
        """Cmd+K / Ctrl+K 快捷键监听必须存在"""
        self.assertIn("e.metaKey", self.content)
        self.assertIn("e.key === 'k'", self.content)
        self.assertIn("e.key === 'Escape'", self.content)

    def test_spotlight_search_highlight_css(self):
        """搜索命中高亮的 CSS 类必须定义"""
        self.assertIn("search-highlight", self.content)
        self.assertIn("flashHighlight", self.content)
        self.assertIn("highlight-target", self.content)

    def test_search_jump_auto_expands_raw_text(self):
        """scrollToSegment 必须支持 query 参数并自动展开原文"""
        match = re.search(
            r"function scrollToSegment\(time,\s*query",
            self.content,
        )
        self.assertIsNotNone(match, "scrollToSegment 必须接受 query 参数")
        # 确认函数体里有自动展开 seg-raw 的逻辑
        self.assertIn("seg-raw", self.content)
        self.assertIn("rawNode.classList.add('visible')", self.content)

    def test_inline_correction_popover_exists(self):
        """全局选词纠错浮窗的 DOM 和 JS 必须存在"""
        self.assertIn('id="correctionPopover"', self.content)
        self.assertIn('id="cpWrongText"', self.content)
        self.assertIn('id="cpRightInput"', self.content)
        self.assertIn("function openCorrectionPopover(", self.content)
        self.assertIn("function closeCorrectionPopover()", self.content)
        self.assertIn("async function submitInlineCorrection()", self.content)
        self.assertIn("correction-popover", self.content)

    def test_settings_page_exists(self):
        """设置页面的 DOM 和相关 JS 必须存在"""
        self.assertIn('id="settingsBtn"', self.content)
        self.assertIn("function openSettings()", self.content)
        self.assertIn("function applySettings()", self.content)
        self.assertIn('data-theme="dark"', self.content)
        self.assertIn('localStorage.setItem(\'openmy-\'', self.content)

    def test_overview_query_panel_exists(self):
        self.assertIn("contextQueryInput", self.content)
        self.assertIn("contextQueryKind", self.content)
        self.assertIn("contextQueryResults", self.content)
        self.assertIn("contextQueryEvidence", self.content)

    def test_context_query_js_functions_exist(self):
        self.assertIn("async function runContextQuery(", self.content)
        self.assertIn("function renderContextQueryResult(", self.content)
        self.assertIn("/api/context/query", self.content)
        self.assertIn("scene_id", self.content)
        self.assertIn("quote", self.content)


if __name__ == "__main__":
    unittest.main()
