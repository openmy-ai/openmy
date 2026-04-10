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
            self.assertTrue(ctx.core_memory.focus_projects)

            registry_names = {item.display_name for item in ctx.stable_profile.key_people_registry}
            self.assertEqual(registry_names, set())

            loop_titles = {item.title for item in ctx.rolling_context.open_loops}
            self.assertIn("补 active context 第一版", loop_titles)
            self.assertIn("重写 README", loop_titles)

            decision_texts = {item.decision for item in ctx.rolling_context.recent_decisions}
            self.assertIn("决定先做 CLI，再做前端。", decision_texts)
            self.assertIn("先做第四层", decision_texts)
            self.assertTrue(ctx.rolling_context.recent_events)

            entity_rollups = {item.entity_id: item for item in ctx.rolling_context.entity_rollups}
            self.assertEqual(entity_rollups, {})

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

    def test_consolidate_generates_loops_and_decisions_from_intents(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            self.write_json(
                data_root / "2026-04-08" / "scenes.json",
                {
                    "scenes": [
                        {
                            "scene_id": "scene_001",
                            "time_start": "10:00",
                            "time_end": "10:20",
                            "summary": "让 Claude 去同步状态，并决定先做 Intent。",
                            "role": {"addressed_to": "AI助手", "needs_review": False},
                        }
                    ],
                    "stats": {"needs_review_count": 0},
                },
            )
            self.write_json(
                project_root / "2026-04-08.meta.json",
                {
                    "daily_summary": "今天主要推进 Intent。",
                    "events": [{"time": "10:00", "project": "OpenMy", "summary": "继续做 Intent。"}],
                    "intents": [
                        {
                            "intent_id": "intent_agent",
                            "kind": "action_item",
                            "what": "同步状态到 Obsidian",
                            "status": "open",
                            "who": {"kind": "agent", "label": "Claude"},
                            "confidence_label": "high",
                            "confidence_score": 0.91,
                            "needs_review": False,
                            "evidence_quote": "让 Claude 去同步。",
                            "source_scene_id": "scene_001",
                            "topic": "OpenMy",
                            "project_hint": "OpenMy",
                        },
                        {
                            "intent_id": "intent_question",
                            "kind": "open_question",
                            "what": "Intent 命名要不要改成 commitments",
                            "status": "open",
                            "who": {"kind": "user", "label": "老板"},
                            "confidence_label": "high",
                            "confidence_score": 0.84,
                            "needs_review": False,
                            "evidence_quote": "命名还要想一下。",
                            "source_scene_id": "scene_001",
                            "topic": "OpenMy",
                        },
                        {
                            "intent_id": "intent_decision",
                            "kind": "decision",
                            "what": "先做 Intent，再做前端。",
                            "status": "active",
                            "who": {"kind": "user", "label": "老板"},
                            "confidence_label": "high",
                            "confidence_score": 0.88,
                            "needs_review": False,
                            "evidence_quote": "先做 Intent。",
                            "source_scene_id": "scene_001",
                            "topic": "OpenMy",
                            "project_hint": "OpenMy",
                        },
                        {
                            "intent_id": "intent_low",
                            "kind": "action_item",
                            "what": "回头研究一下",
                            "status": "open",
                            "who": {"kind": "user", "label": "老板"},
                            "confidence_label": "low",
                            "confidence_score": 0.33,
                            "needs_review": True,
                            "evidence_quote": "回头看看。",
                            "source_scene_id": "scene_001",
                            "topic": "OpenMy",
                        },
                    ],
                    "facts": [{"fact_type": "idea", "content": "Intent 和 facts 要分桶。", "topic": "OpenMy"}],
                },
            )

            ctx = consolidate(data_root)

            loop_types = {item.title: item.loop_type for item in ctx.rolling_context.open_loops}
            self.assertEqual(loop_types["同步状态到 Obsidian"], "delegated")
            self.assertEqual(loop_types["Intent 命名要不要改成 commitments"], "question")
            self.assertNotIn("先做 Intent，再做前端。", loop_types)
            self.assertNotIn("回头研究一下", loop_types)

            core_loop_titles = {item.title for item in ctx.core_memory.open_loops}
            self.assertIn("同步状态到 Obsidian", core_loop_titles)
            self.assertIn("Intent 命名要不要改成 commitments", core_loop_titles)
            self.assertNotIn("回头研究一下", core_loop_titles)

            decision_texts = {item.decision for item in ctx.rolling_context.recent_decisions}
            self.assertIn("先做 Intent，再做前端。", decision_texts)
            decision = next(item for item in ctx.rolling_context.recent_decisions if item.decision == "先做 Intent，再做前端。")
            self.assertEqual(decision.current_state, "active")
            self.assertTrue(decision.provenance_refs)
            loop = next(item for item in ctx.rolling_context.open_loops if item.title == "同步状态到 Obsidian")
            self.assertEqual(loop.current_state, "active")
            self.assertTrue(loop.provenance_refs)

    def test_consolidate_prefers_day_dir_meta_written_by_extract(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            self.write_json(
                data_root / "2026-04-08" / "scenes.json",
                {
                    "scenes": [
                        {
                            "scene_id": "scene_001",
                            "time_start": "10:00",
                            "time_end": "10:20",
                            "summary": "提醒给张总回电话，并检查鸡蛋库存。",
                            "role": {"addressed_to": "", "needs_review": False},
                        }
                    ]
                },
            )
            self.write_json(
                data_root / "2026-04-08" / "2026-04-08.meta.json",
                {
                    "daily_summary": "今天主要在处理合同回电和生活采购。",
                    "events": [{"time": "15:00", "project": "合同对接", "summary": "准备联系张总。"}],
                    "intents": [
                        {
                            "intent_id": "intent_001",
                            "kind": "action_item",
                            "what": "给张总回电话，对齐合同细节",
                            "status": "open",
                            "who": {"kind": "user", "label": "老板"},
                            "confidence_label": "high",
                            "confidence_score": 0.95,
                            "needs_review": False,
                            "evidence_quote": "提醒我给张总回个电话。",
                            "source_scene_id": "scene_001",
                            "topic": "合同对接",
                            "project_hint": "合同对接",
                        }
                    ],
                    "facts": [{"fact_type": "observation", "content": "冰箱库存待确认。", "topic": "生活采购"}],
                },
            )

            ctx = consolidate(data_root)

            loop_titles = {item.title for item in ctx.rolling_context.open_loops}
            self.assertIn("给张总回电话，对齐合同细节", loop_titles)

    def test_consolidate_accumulates_repeated_loop_lineage_and_future_due(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.write_json(data_root / "2026-04-08" / "2026-04-08.meta.json", {
                "intents": [
                    {
                        "intent_id": "intent_001",
                        "kind": "action_item",
                        "what": "给张总回电话",
                        "status": "open",
                        "who": {"kind": "user", "label": "老板"},
                        "confidence_label": "high",
                        "confidence_score": 0.9,
                        "source_scene_id": "scene_001",
                        "due": {"raw_text": "后天", "iso_date": "2026-04-12", "granularity": "day"},
                        "project_hint": "合同对接",
                    }
                ]
            })
            self.write_json(data_root / "2026-04-09" / "2026-04-09.meta.json", {
                "intents": [
                    {
                        "intent_id": "intent_002",
                        "kind": "action_item",
                        "what": "给张总回电话",
                        "status": "open",
                        "who": {"kind": "user", "label": "老板"},
                        "confidence_label": "high",
                        "confidence_score": 0.93,
                        "source_scene_id": "scene_002",
                        "project_hint": "合同对接",
                    }
                ]
            })

            ctx = consolidate(data_root)
            loop = next(item for item in ctx.rolling_context.open_loops if item.title == "给张总回电话")

            self.assertEqual(loop.first_seen_at[:10], "2026-04-08")
            self.assertEqual(loop.last_seen_at[:10], "2026-04-09")
            self.assertEqual(loop.reinforcement_count, 2)
            self.assertEqual(loop.due_hint, "2026-04-12")
            self.assertEqual(loop.current_state, "future")

    def test_consolidate_closes_loop_using_done_intent_date_not_today(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            self.write_json(data_root / "2026-04-08" / "2026-04-08.meta.json", {
                "intents": [
                    {
                        "intent_id": "intent_open",
                        "kind": "action_item",
                        "what": "给张总回电话",
                        "status": "open",
                        "who": {"kind": "user", "label": "老板"},
                        "confidence_label": "high",
                        "confidence_score": 0.9,
                        "source_scene_id": "scene_001",
                    }
                ]
            })
            self.write_json(data_root / "2026-04-09" / "2026-04-09.meta.json", {
                "intents": [
                    {
                        "intent_id": "intent_done",
                        "kind": "action_item",
                        "what": "给张总回电话",
                        "status": "done",
                        "who": {"kind": "user", "label": "老板"},
                        "confidence_label": "high",
                        "confidence_score": 0.94,
                        "source_scene_id": "scene_002",
                        "valid_until": "2026-04-09T18:00:00+08:00",
                    }
                ]
            })

            ctx = consolidate(data_root)
            loop = next(item for item in ctx.rolling_context.open_loops if item.title == "给张总回电话")

            self.assertEqual(loop.current_state, "closed")
            self.assertTrue(loop.valid_until.startswith("2026-04-09"))

    def test_consolidate_emits_recent_conflicts_for_incompatible_facts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            self.write_json(data_root / "2026-04-08" / "2026-04-08.meta.json", {
                "facts": [
                    {
                        "fact_id": "fact_fw",
                        "fact_type": "project_update",
                        "content": "OpenMy 默认 ASR 是 faster-whisper。",
                        "topic": "OpenMy 默认 ASR",
                        "confidence_score": 0.9,
                        "source_scene_id": "scene_001",
                        "evidence_quote": "默认先走 faster-whisper。",
                    }
                ]
            })
            self.write_json(data_root / "2026-04-09" / "2026-04-09.meta.json", {
                "facts": [
                    {
                        "fact_id": "fact_funasr",
                        "fact_type": "project_update",
                        "content": "OpenMy 默认 ASR 是 FunASR。",
                        "topic": "OpenMy 默认 ASR",
                        "confidence_score": 0.9,
                        "source_scene_id": "scene_002",
                        "evidence_quote": "默认改成 FunASR。",
                    }
                ]
            })

            ctx = consolidate(data_root)

            self.assertTrue(ctx.rolling_context.recent_conflicts)
            self.assertEqual(ctx.rolling_context.recent_conflicts[0].conflict_type, "fact_conflict")

    def test_consolidate_surfaces_screen_completion_candidates_in_realtime_context(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            self.write_json(
                data_root / "2026-04-10" / "scenes.json",
                {
                    "scenes": [
                        {
                            "scene_id": "scene_001",
                            "time_start": "10:00",
                            "time_end": "10:20",
                            "summary": "准备继续推进 OpenMy。",
                            "role": {"addressed_to": "", "needs_review": False},
                            "screen_context": {
                                "summary": "当时正在 Cursor 修改 OpenMy 的屏幕上下文主链",
                                "primary_app": "Cursor",
                                "completion_candidates": [
                                    {
                                        "kind": "saved",
                                        "label": "保存成功",
                                        "confidence": 0.92,
                                        "evidence": "保存成功",
                                    }
                                ],
                            },
                        }
                    ]
                },
            )
            self.write_json(
                data_root / "2026-04-10" / "daily_briefing.json",
                {
                    "date": "2026-04-10",
                    "summary": "今天继续推进 OpenMy。",
                    "key_events": ["继续推进 OpenMy"],
                },
            )
            self.write_json(
                data_root / "2026-04-10" / "2026-04-10.meta.json",
                {
                    "daily_summary": "今天继续推进 OpenMy。",
                    "events": [{"time": "10:00", "project": "OpenMy", "summary": "继续推进屏幕上下文主链。"}],
                    "intents": [],
                    "facts": [],
                },
            )

            ctx = consolidate(data_root)

            self.assertIn("OpenMy", " ".join(ctx.realtime_context.today_focus))
            self.assertTrue(ctx.realtime_context.screen_completion_candidates)
            self.assertEqual(ctx.realtime_context.screen_completion_candidates[0].label, "保存成功")


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
