#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from openmy.services.context.active_context import ActiveContext
from openmy.services.context.consolidation import consolidate
from openmy.services.context.renderer import (
    render_compact_md,
    render_level0,
    render_level1,
)


class TestConsolidation(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def make_fixture(self, root: Path) -> Path:
        data_root = root / "data"
        data_root.mkdir(parents=True, exist_ok=True)

        self.write_json(
            data_root / "2026-04-06" / "scenes.json",
            {
                "scenes": [
                    {
                        "scene_id": "scene_001",
                        "time_start": "12:00",
                        "time_end": "12:10",
                        "summary": "讨论 OpenMy 的 CLI 路线",
                        "role": {
                            "addressed_to": "老婆",
                            "needs_review": False,
                        },
                    },
                    {
                        "scene_id": "scene_002",
                        "time_start": "14:00",
                        "time_end": "14:20",
                        "summary": "让 AI 帮忙梳理 active context 方案",
                        "role": {
                            "addressed_to": "AI助手",
                            "needs_review": True,
                        },
                    },
                ],
                "stats": {"needs_review_count": 1},
            },
        )
        self.write_json(
            data_root / "2026-04-06" / "daily_briefing.json",
            {
                "date": "2026-04-06",
                "summary": "主要推进 OpenMy CLI 和第四层设计。",
                "key_events": ["完成 CLI 命令梳理", "开始设计 active context"],
                "decisions": ["决定先做 CLI，再做前端。"],
                "todos_open": ["补 active context 第一版"],
            },
        )

        self.write_json(
            root / "2026-04-07.scenes.json",
            {
                "scenes": [
                    {
                        "scene_id": "scene_101",
                        "time_start": "11:30",
                        "time_end": "11:50",
                        "summary": "继续讨论 OpenMy 和开源方向",
                        "role": {
                            "addressed_to": "老婆",
                            "needs_review": False,
                        },
                    }
                ],
                "stats": {"needs_review_count": 0},
            },
        )
        self.write_json(
            root / "2026-04-07.meta.json",
            {
                "daily_summary": "今天主要推进 OpenMy 的开源表达。",
                "events": [
                    {"time": "11:37", "project": "OpenMy", "summary": "继续完善第四层总状态卡。"},
                    {"time": "14:05", "project": "开源计划", "summary": "讨论开源路径和 README。"},
                ],
                "decisions": [
                    {"project": "OpenMy", "what": "先做第四层", "why": "让 Agent 先理解人。"}
                ],
                "todos": [
                    {"task": "重写 README", "priority": "high", "project": "OpenMy"}
                ],
            },
        )
        return data_root

    def test_consolidate_reads_new_and_legacy_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = self.make_fixture(project_root)

            ctx = consolidate(data_root)

            self.assertEqual(ctx.stable_profile.identity.canonical_name, "周瑟夫")
            self.assertEqual(ctx.realtime_context.ingestion_health.last_processed_date, "2026-04-07")
            self.assertTrue(ctx.status_line)

            registry_names = {item.display_name for item in ctx.stable_profile.key_people_registry}
            self.assertIn("老婆", registry_names)

            loop_titles = {item.title for item in ctx.rolling_context.open_loops}
            self.assertIn("补 active context 第一版", loop_titles)
            self.assertIn("重写 README", loop_titles)

            decision_texts = {item.decision for item in ctx.rolling_context.recent_decisions}
            self.assertIn("决定先做 CLI，再做前端。", decision_texts)
            self.assertIn("先做第四层", decision_texts)

            entity_rollups = {item.entity_id: item for item in ctx.rolling_context.entity_rollups}
            self.assertEqual(entity_rollups["老婆"].interaction_7d_count, 2)

            updates_path = data_root / "active_context_updates.jsonl"
            self.assertTrue(updates_path.exists())
            self.assertTrue(updates_path.read_text(encoding="utf-8").strip())

    def test_consolidate_increments_context_seq(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = self.make_fixture(project_root)
            existing = ActiveContext(context_seq=7)

            ctx = consolidate(data_root, existing_context=existing)

            self.assertGreater(ctx.context_seq, 7)
            self.assertEqual(ctx.materialized_from_event_seq, ctx.context_seq)


class TestRenderer(unittest.TestCase):
    def make_context(self) -> ActiveContext:
        ctx = ActiveContext(
            generated_at="2026-04-08T23:58:10+08:00",
            context_seq=9,
            status_line="最近主要推进 OpenMy 第四层；当前有 2 个待办未闭环；高频互动对象是 老婆。",
        )
        ctx.rolling_context.open_loops = []
        ctx.rolling_context.recent_changes = []
        ctx.rolling_context.active_projects = []
        ctx.rolling_context.recent_decisions = []
        ctx.rolling_context.entity_rollups = []
        ctx.realtime_context.today_focus = ["第四层", "CLI"]
        ctx.realtime_context.today_state.primary_mode = "design"
        return ctx

    def test_render_level0_returns_short_summary(self):
        content = render_level0(self.make_context())

        self.assertIn("最近主要推进", content)

    def test_render_level1_contains_key_sections(self):
        content = render_level1(self.make_context())

        self.assertIn("当前状态", content)
        self.assertIn("今天重点", content)

    def test_render_compact_md_returns_markdown(self):
        content = render_compact_md(self.make_context())

        self.assertTrue(content.startswith("# Active Context"))
        self.assertIn("最近主要推进", content)


if __name__ == "__main__":
    unittest.main()
