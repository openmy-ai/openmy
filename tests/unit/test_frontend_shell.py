#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "app" / "index.html"
STYLE_CSS = PROJECT_ROOT / "app" / "static" / "style.css"
APP_JS = PROJECT_ROOT / "app" / "static" / "app.js"


class TestFrontendShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_content = INDEX_HTML.read_text(encoding="utf-8")
        cls.style_content = STYLE_CSS.read_text(encoding="utf-8")
        cls.script_content = APP_JS.read_text(encoding="utf-8")
        cls.content = "\n".join(
            [
                cls.html_content,
                "\n/* STYLE */\n",
                cls.style_content,
                "\n// SCRIPT\n",
                cls.script_content,
            ]
        )

    def test_index_preserves_reading_first_shell(self):
        self.assertIn("renderDayLayout()", self.content)
        self.assertIn("record-list", self.content)
        self.assertIn("summary-callout", self.content)
        self.assertIn("详细记录", self.content)
        self.assertIn("数据图表", self.content)
        self.assertIn("props-grid", self.content)
        self.assertIn("meta-section", self.content)

    def test_index_adds_context_tabs_without_replacing_reader_views(self):
        self.assertIn("renderHomePage()", self.content)
        self.assertIn("renderWeeklyReport()", self.content)
        self.assertIn("renderMonthlyReport()", self.content)
        self.assertIn("首页", self.content)
        self.assertIn("周报", self.content)
        self.assertIn("月报", self.content)

    def test_index_fetches_context_and_day_payloads(self):
        self.assertIn("/api/context", self.content)
        self.assertIn("/api/onboarding", self.content)
        self.assertIn("/api/context/loops", self.content)
        self.assertIn("/api/context/projects", self.content)
        self.assertIn("/api/context/decisions", self.content)
        self.assertIn("/api/pipeline/jobs", self.content)
        self.assertRegex(self.content, r"/api/date/\$\{[^}]+\}/meta")
        self.assertRegex(self.content, r"/api/date/\$\{[^}]+\}/briefing")
        self.assertIn('/static/vendor/chart.umd.js', self.content)
        self.assertNotIn('cdn.jsdelivr.net/npm/chart.js', self.content)

    def test_home_page_contains_onboarding_card(self):
        self.assertIn("renderOnboardingCard", self.content)
        self.assertIn("renderTranscriptionSettings", self.content)
        self.assertIn("selectOnboardingProvider", self.content)
        self.assertIn("selectTranscriptionOption", self.content)
        self.assertIn("confirmTranscriptionProvider", self.content)
        self.assertIn("transcriptionSettingsSection", self.content)

    def test_home_page_wiki_view(self):
        self.assertIn("renderWikiHome", self.content)
        self.assertIn("renderRecentSummaryHome", self.content)
        self.assertIn("showWikiHome", self.content)

    def test_index_renders_meta_panels_inside_day_view(self):
        self.assertIn("renderMetaPanels", self.content)
        self.assertIn("meta-section", self.content)
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

    def test_home_page_contains_dropzone_and_progress_panel(self):
        self.assertIn("renderHomeDropZone", self.content)
        self.assertIn("renderHomePipelineSlotCard", self.content)
        self.assertIn("hasReadyTranscriptionProvider", self.content)
        self.assertIn("getHomePipelineJob", self.content)
        self.assertIn("homeJobFocusId", self.content)
        self.assertIn("clearHomeJobFocus", self.content)
        self.assertIn("homeDropzone", self.content)
        self.assertIn("/api/upload", self.content)
        self.assertIn("runPipelineAction", self.content)
        self.assertIn("['queued', 'running', 'paused'].includes(job.status)", self.content)
        self.assertIn("先选转写引擎，再上传音频", self.content)
        self.assertIn("openSettings('transcription')", self.content)
        self.assertNotIn("['queued', 'running', 'paused', 'failed', 'partial', 'cancelled', 'interrupted', 'succeeded'].includes(detail.status)", self.content)

    def test_timeline_distillation_uses_plain_summary_fallback(self):
        match = re.search(
            r"function getSegmentDistillation\(segment, meta\) \{(?P<body>.*?)\n\}\n\nfunction initCharts",
            self.content,
            re.S,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("if (segment.summary) return escapeHtml(plainText(segment.summary));", body)
        self.assertIn("return escapeHtml(plainText(segment.preview || segment.text || '').slice(0, 200));", body)

    def test_chart_init_has_missing_script_guard(self):
        self.assertIn("if (typeof Chart === 'undefined') return;", self.content)

    def test_plain_text_cleans_markdown_separator(self):
        self.assertIn(".replace(/^---+$/gm, '')", self.content)

    def test_day_view_detail_list_starts_collapsed(self):
        self.assertIn("collapsible-header", self.content)
        self.assertIn("collapse-arrow", self.content)
        self.assertIn("record-list collapsed", self.content)
        self.assertIn("function toggleSection(header)", self.content)

    def test_sidebar_filters_future_test_dates(self):
        self.assertIn("function getVisibleDates()", self.content)
        self.assertIn("year <= currentYear + 1", self.content)

    def test_meta_panel_project_tag_switched_to_parentheses(self):
        self.assertIn("inline-project", self.content)
        self.assertNotIn("project-tag", self.script_content)

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

    def test_sidebar_contains_transcription_entry(self):
        self.assertIn('transcriptionBtn', self.content)
        self.assertIn('转写模型', self.content)
        self.assertIn("openSettings('transcription')", self.content)

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
