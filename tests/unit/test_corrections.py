#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from openmy.services.context.active_context import (
    ActiveContext,
    DecisionItem,
    EntityRegistryCard,
    EntityRollup,
    OpenLoop,
    ProjectCard,
)
from openmy.services.context.consolidation import consolidate
from openmy.services.context.corrections import (
    CorrectionEvent,
    append_correction,
    apply_corrections,
    load_corrections,
)


class TestCorrections(unittest.TestCase):
    def make_context(self) -> ActiveContext:
        ctx = ActiveContext(
            generated_at="2026-04-08T23:58:10+08:00",
            context_seq=9,
            status_line="最近3天主要推进 AI思维、OpenMy；当前有 3 个待办未闭环；高频互动对象是 老婆。"
        )
        ctx.rolling_context.active_projects = [
            ProjectCard(
                id="project_ai",
                project_id="project_ai",
                title="AI思维",
                current_goal="整理想法",
                next_actions=["补 AI 思维文档"],
                confidence=0.8,
                source_rank="aggregate",
            ),
            ProjectCard(
                id="project_openmy",
                project_id="project_openmy",
                title="OpenMy",
                current_goal="做第四层",
                next_actions=["接 CLI"],
                confidence=0.9,
                source_rank="aggregate",
            ),
            ProjectCard(
                id="project_proxy",
                project_id="project_proxy",
                title="代理配置",
                current_goal="修网络问题",
                next_actions=["查 fake ip"],
                confidence=0.6,
                source_rank="aggregate",
            ),
        ]
        ctx.rolling_context.open_loops = [
            OpenLoop(
                id="loop_readme",
                loop_id="loop_readme",
                title="README 重写",
                loop_type="todo",
                status="open",
                confidence=0.9,
                source_rank="declared",
                last_seen_at="2026-04-08T22:00:00+08:00",
            ),
            OpenLoop(
                id="loop_liutao",
                loop_id="loop_liutao",
                title="聊某位朋友婚姻，感慨择偶比结婚本身更重要",
                loop_type="todo",
                status="open",
                confidence=0.7,
                source_rank="aggregate",
                last_seen_at="2026-04-08T22:10:00+08:00",
            ),
            OpenLoop(
                id="loop_context",
                loop_id="loop_context",
                title="补 active context 第一版",
                loop_type="todo",
                status="open",
                confidence=0.8,
                source_rank="aggregate",
                last_seen_at="2026-04-08T22:20:00+08:00",
            ),
        ]
        ctx.rolling_context.recent_decisions = [
            DecisionItem(
                id="decision_cli",
                decision_id="decision_cli",
                topic="OpenMy",
                decision="先做 CLI，再做前端。",
                effective_from="2026-04-08T20:00:00+08:00",
                confidence=0.9,
                source_rank="declared",
            ),
            DecisionItem(
                id="decision_lunch",
                decision_id="decision_lunch",
                topic="生活",
                decision="中午改吃河南蒸菜",
                effective_from="2026-04-08T12:00:00+08:00",
                confidence=0.5,
                source_rank="aggregate",
            ),
        ]
        ctx.stable_profile.key_people_registry = [
            EntityRegistryCard(
                id="entity_partner",
                entity_id="老婆",
                display_name="老婆",
                relation_type="person",
                aliases=["老婆"],
                source_rank="aggregate",
                confidence=0.7,
            )
        ]
        ctx.rolling_context.entity_rollups = [
            EntityRollup(
                entity_id="老婆",
                interaction_7d_count=5,
                interaction_30d_count=12,
                last_interaction_at="2026-04-08T19:40:00+08:00",
                recent_topics=["晚饭", "项目近况"],
            )
        ]
        return ctx

    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def make_fixture(self, root: Path) -> Path:
        data_root = root / "data"
        data_root.mkdir(parents=True, exist_ok=True)

        self.write_json(
            data_root / "2026-04-08" / "daily_briefing.json",
            {
                "date": "2026-04-08",
                "summary": "主要推进 OpenMy 和 AI思维。",
                "key_events": ["继续设计第四层"],
                "decisions": ["中午改吃河南蒸菜"],
                "todos_open": ["聊某位朋友婚姻，感慨择偶比结婚本身更重要"],
            },
        )
        self.write_json(
            root / "2026-04-08.meta.json",
            {
                "events": [
                    {"time": "11:00", "project": "AI思维", "summary": "梳理 AI 思维框架"},
                    {"time": "14:00", "project": "OpenMy", "summary": "定义第四层"},
                    {"time": "16:00", "project": "代理配置", "summary": "调代理"},
                ],
                "decisions": [
                    {"project": "OpenMy", "what": "中午改吃河南蒸菜", "why": "临时改主意"}
                ],
                "todos": [
                    {"task": "聊某位朋友婚姻，感慨择偶比结婚本身更重要", "priority": "medium", "project": "OpenMy"}
                ],
            },
        )
        return data_root

    def test_append_and_load(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir)
            append_correction(
                data_root,
                CorrectionEvent(
                    correction_id="corr_003",
                    created_at="2026-04-08T10:03:00+08:00",
                    actor="user",
                    op="reject_loop",
                    target_type="loop",
                    target_id="loop_c",
                    payload={},
                ),
            )
            append_correction(
                data_root,
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T10:01:00+08:00",
                    actor="user",
                    op="close_loop",
                    target_type="loop",
                    target_id="loop_a",
                    payload={"status": "done"},
                ),
            )
            append_correction(
                data_root,
                CorrectionEvent(
                    correction_id="corr_002",
                    created_at="2026-04-08T10:02:00+08:00",
                    actor="user",
                    op="merge_project",
                    target_type="project",
                    target_id="AI思维",
                    payload={"merge_into": "OpenMy"},
                ),
            )

            events = load_corrections(data_root)

        self.assertEqual([event.correction_id for event in events], ["corr_001", "corr_002", "corr_003"])

    def test_reject_loop(self):
        ctx = self.make_context()
        corrected = apply_corrections(
            ctx,
            [
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T10:01:00+08:00",
                    actor="user",
                    op="reject_loop",
                    target_type="loop",
                    target_id="loop_liutao",
                    payload={},
                )
            ],
        )

        titles = {item.title for item in corrected.rolling_context.open_loops}
        self.assertNotIn("聊某位朋友婚姻，感慨择偶比结婚本身更重要", titles)
        self.assertEqual(len(corrected.rolling_context.open_loops), 2)

    def test_close_loop(self):
        ctx = self.make_context()
        corrected = apply_corrections(
            ctx,
            [
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T10:01:00+08:00",
                    actor="user",
                    op="close_loop",
                    target_type="loop",
                    target_id="README 重写",
                    payload={"status": "done"},
                )
            ],
        )

        titles = {item.title for item in corrected.rolling_context.open_loops}
        self.assertNotIn("README 重写", titles)

    def test_merge_project(self):
        ctx = self.make_context()
        corrected = apply_corrections(
            ctx,
            [
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T10:01:00+08:00",
                    actor="user",
                    op="merge_project",
                    target_type="project",
                    target_id="AI思维",
                    payload={"merge_into": "OpenMy"},
                )
            ],
        )

        titles = [item.title for item in corrected.rolling_context.active_projects]
        self.assertEqual(titles.count("OpenMy"), 1)
        self.assertNotIn("AI思维", titles)
        openmy = next(item for item in corrected.rolling_context.active_projects if item.title == "OpenMy")
        self.assertIn("补 AI 思维文档", openmy.next_actions)

    def test_reject_project(self):
        ctx = self.make_context()
        corrected = apply_corrections(
            ctx,
            [
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T10:01:00+08:00",
                    actor="user",
                    op="reject_project",
                    target_type="project",
                    target_id="代理配置",
                    payload={},
                )
            ],
        )

        titles = {item.title for item in corrected.rolling_context.active_projects}
        self.assertNotIn("代理配置", titles)

    def test_reject_decision(self):
        ctx = self.make_context()
        corrected = apply_corrections(
            ctx,
            [
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T10:01:00+08:00",
                    actor="user",
                    op="reject_decision",
                    target_type="decision",
                    target_id="decision_lunch",
                    payload={},
                )
            ],
        )

        decisions = {item.decision for item in corrected.rolling_context.recent_decisions}
        self.assertNotIn("中午改吃河南蒸菜", decisions)

    def test_confirm_entity(self):
        ctx = self.make_context()
        corrected = apply_corrections(
            ctx,
            [
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T10:01:00+08:00",
                    actor="user",
                    op="confirm_entity",
                    target_type="entity",
                    target_id="老婆",
                    payload={"relation_type": "partner", "display_name": "伴侣"},
                )
            ],
        )

        entity = corrected.stable_profile.key_people_registry[0]
        rollup = corrected.rolling_context.entity_rollups[0]
        self.assertEqual(entity.display_name, "伴侣")
        self.assertEqual(entity.relation_type, "partner")
        self.assertEqual(entity.source_rank, "human_confirmed")
        self.assertEqual(rollup.entity_id, "伴侣")

    def test_status_line_regenerated(self):
        ctx = self.make_context()
        corrected = apply_corrections(
            ctx,
            [
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T10:01:00+08:00",
                    actor="user",
                    op="merge_project",
                    target_type="project",
                    target_id="AI思维",
                    payload={"merge_into": "OpenMy"},
                ),
                CorrectionEvent(
                    correction_id="corr_002",
                    created_at="2026-04-08T10:02:00+08:00",
                    actor="user",
                    op="reject_loop",
                    target_type="loop",
                    target_id="loop_liutao",
                    payload={},
                ),
            ],
        )

        self.assertIn("OpenMy", corrected.status_line)
        self.assertIn("2 个待办", corrected.status_line)

    def test_empty_corrections(self):
        ctx = self.make_context()
        corrected = apply_corrections(ctx, [])
        self.assertEqual(corrected.to_dict(), ctx.to_dict())

    def test_full_consolidation_with_corrections(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = self.make_fixture(project_root)
            append_correction(
                data_root,
                CorrectionEvent(
                    correction_id="corr_001",
                    created_at="2026-04-08T18:00:00+08:00",
                    actor="user",
                    op="reject_loop",
                    target_type="loop",
                    target_id="聊某位朋友婚姻，感慨择偶比结婚本身更重要",
                    payload={},
                ),
            )
            append_correction(
                data_root,
                CorrectionEvent(
                    correction_id="corr_002",
                    created_at="2026-04-08T18:01:00+08:00",
                    actor="user",
                    op="merge_project",
                    target_type="project",
                    target_id="AI思维",
                    payload={"merge_into": "OpenMy"},
                ),
            )
            append_correction(
                data_root,
                CorrectionEvent(
                    correction_id="corr_003",
                    created_at="2026-04-08T18:02:00+08:00",
                    actor="user",
                    op="reject_decision",
                    target_type="decision",
                    target_id="中午改吃河南蒸菜",
                    payload={},
                ),
            )

            ctx = consolidate(data_root)

        loop_titles = {item.title for item in ctx.rolling_context.open_loops}
        project_titles = {item.title for item in ctx.rolling_context.active_projects}
        decision_texts = {item.decision for item in ctx.rolling_context.recent_decisions}

        self.assertNotIn("聊某位朋友婚姻，感慨择偶比结婚本身更重要", loop_titles)
        self.assertIn("OpenMy", project_titles)
        self.assertNotIn("AI思维", project_titles)
        self.assertNotIn("中午改吃河南蒸菜", decision_texts)


if __name__ == "__main__":
    unittest.main()
