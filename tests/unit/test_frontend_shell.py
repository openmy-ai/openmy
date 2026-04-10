#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


INDEX_HTML = Path("/Users/zhousefu/Desktop/周瑟夫的上下文/app/index.html")


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
        self.assertIn('id="tab-corrections"', self.content)
        self.assertIn('id="tab-pipeline"', self.content)
        self.assertIn("概览", self.content)
        self.assertIn("校正", self.content)
        self.assertIn("流程", self.content)

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
        self.assertIn("view-corrections", self.content)
        self.assertIn("view-pipeline", self.content)
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
        self.assertIn("submitTypoCorrection", self.content)

    def test_index_contains_pipeline_job_panel(self):
        self.assertIn("pipelineJobsList", self.content)
        self.assertIn("pipelineJobDetail", self.content)
        self.assertIn("createPipelineJob", self.content)
        self.assertIn("refreshPipelineJobs", self.content)
        self.assertIn("刷新上下文", self.content)
        self.assertIn("重新运行", self.content)

    def test_mobile_layout_has_single_column_breakpoint(self):
        self.assertRegex(
            self.content,
            r"@media\s*\(max-width:\s*900px\)\s*\{[^}]*\.app\s*\{[^}]*grid-template-columns:\s*1fr;",
        )


if __name__ == "__main__":
    unittest.main()
