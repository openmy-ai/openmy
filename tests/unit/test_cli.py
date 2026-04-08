#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestOpenMyCli(unittest.TestCase):
    def make_day_dir(self, date_str: str) -> Path:
        day_dir = PROJECT_ROOT / "data" / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def cleanup_day_dir(self, date_str: str) -> None:
        shutil.rmtree(PROJECT_ROOT / "data" / date_str, ignore_errors=True)

    def make_context_snapshot(self) -> dict:
        return {
            "schema_version": "active_context.v1",
            "user_id": "user_zhousefu",
            "generated_at": "2026-04-08T23:58:10+08:00",
            "context_seq": 1,
            "materialized_from_event_seq": 1,
            "default_delta_window_days": 3,
            "status_line": "最近主要推进 OpenMy；当前有 1 个待办未闭环；高频互动对象是 老婆。",
            "stable_profile": {
                "identity": {},
                "communication_contract": {},
                "enduring_preferences": [],
                "durable_constraints": [],
                "routine_signals": [],
                "key_people_registry": [],
            },
            "rolling_context": {
                "recent_changes": [],
                "active_projects": [
                    {
                        "id": "project_openmy",
                        "project_id": "project_openmy",
                        "title": "OpenMy",
                        "status": "active",
                        "priority": "high",
                        "current_goal": "做第四层",
                        "next_actions": ["接 CLI"],
                        "blockers": [],
                        "momentum": "steady",
                        "last_touched_at": "2026-04-08T22:00:00+08:00",
                        "confidence": 0.9,
                        "source_rank": "aggregate",
                    },
                    {
                        "id": "project_ai",
                        "project_id": "project_ai",
                        "title": "AI思维",
                        "status": "active",
                        "priority": "medium",
                        "current_goal": "整理想法",
                        "next_actions": ["补 AI 思维文档"],
                        "blockers": [],
                        "momentum": "steady",
                        "last_touched_at": "2026-04-08T21:00:00+08:00",
                        "confidence": 0.8,
                        "source_rank": "aggregate",
                    },
                ],
                "open_loops": [
                    {
                        "id": "loop_readme",
                        "loop_id": "loop_readme",
                        "title": "重写 README",
                        "loop_type": "todo",
                        "status": "open",
                        "owner": "self",
                        "due_hint": "",
                        "priority": "high",
                        "waiting_on": "",
                        "close_condition": "README 提交到仓库",
                        "confidence": 0.9,
                        "source_rank": "declared",
                    }
                ],
                "recent_decisions": [
                    {
                        "id": "decision_lunch",
                        "decision_id": "decision_lunch",
                        "topic": "生活",
                        "decision": "中午改吃河南蒸菜",
                        "scope": "project",
                        "effective_from": "2026-04-08T12:00:00+08:00",
                        "supersedes": [],
                        "confidence": 0.5,
                        "source_rank": "aggregate",
                    }
                ],
                "belief_shifts": [],
                "entity_rollups": [],
                "topic_rollups": [],
            },
            "realtime_context": {
                "today_focus": [],
                "today_state": {},
                "latest_scene_refs": [],
                "pending_followups_today": [],
                "ingestion_health": {},
            },
            "quality": {},
        }

    def test_cli_status_runs(self):
        """openmy status 应该能跑通不报错。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue("日期" in result.stdout or "📅" in result.stdout)

    def test_cli_help(self):
        """openmy --help 应该输出帮助。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue("openmy" in result.stdout.lower() or "OpenMy" in result.stdout)

    def test_cli_view_existing_date(self):
        """openmy view 2026-04-06 应该输出场景概览。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "view", "2026-04-06"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue("12:" in result.stdout or "13:" in result.stdout)

    def test_cli_view_nonexistent_date(self):
        """不存在的日期应该友好报错。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "view", "1999-01-01"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_cli_roles_nonexistent_date(self):
        """没有清洗文本时，roles 应该友好报错。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "roles", "1999-01-01"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_cli_briefing_generates_output(self):
        """openmy briefing 应该生成日报文件。"""
        date_str = "2099-01-02"
        output_dir = self.make_day_dir(date_str)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "briefing", date_str],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output_dir / "daily_briefing.json").exists())
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_clean_generates_output(self):
        """openmy clean 应该从 raw 生成 transcript.md。"""
        date_str = "2099-01-03"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.raw.md").write_text(
            "# 2099-01-03 原始\n\n---\n\n## 10:00\n\n嗯\n老婆，今天去散步。",
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "clean", date_str],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            transcript = (day_dir / "transcript.md").read_text(encoding="utf-8")
            self.assertIn("老婆", transcript)
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_roles_generates_scenes(self):
        """openmy roles 应该从 transcript 生成 scenes.json。"""
        date_str = "2099-01-04"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text(
            "# 2099-01-04\n\n---\n\n## 10:00\n\n老婆，晚上一起吃饭。\n\n## 11:00\n\nClaude 帮我看一下代码。",
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "roles", date_str],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((day_dir / "scenes.json").exists())
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_distill_requires_api_key(self):
        """openmy distill 没有 GEMINI_API_KEY 时应该友好报错。"""
        date_str = "2099-01-05"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "scenes.json").write_text(
            '{"scenes":[{"scene_id":"s01","text":"测试文本","summary":""}],"stats":{"total_scenes":1,"role_distribution":{}}}',
            encoding="utf-8",
        )

        env = dict(**os.environ)
        env.pop("GEMINI_API_KEY", None)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "distill", date_str],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
                env=env,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_correct_updates_transcript(self):
        """openmy correct 应该更新 transcript 并同步纠错词典。"""
        date_str = "2099-01-06"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        transcript_path.write_text("## 10:00\n\n青维今天去散步。", encoding="utf-8")

        corrections_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "corrections.json"
        vocab_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "vocab.txt"
        original_corrections = corrections_path.read_text(encoding="utf-8")
        original_vocab = vocab_path.read_text(encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "correct", date_str, "青维", "青梅"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("青梅", transcript_path.read_text(encoding="utf-8"))
            self.assertNotIn("青维今天", transcript_path.read_text(encoding="utf-8"))
        finally:
            corrections_path.write_text(original_corrections, encoding="utf-8")
            vocab_path.write_text(original_vocab, encoding="utf-8")
            self.cleanup_day_dir(date_str)

    def test_correct_typo_subcommand(self):
        """openmy correct typo 应该兼容新的子命令写法。"""
        date_str = "2099-01-08"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        transcript_path.write_text("## 10:00\n\n青维今天去散步。", encoding="utf-8")

        corrections_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "corrections.json"
        vocab_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "vocab.txt"
        original_corrections = corrections_path.read_text(encoding="utf-8")
        original_vocab = vocab_path.read_text(encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "correct", "typo", date_str, "青维", "青梅"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("青梅", transcript_path.read_text(encoding="utf-8"))
        finally:
            corrections_path.write_text(original_corrections, encoding="utf-8")
            vocab_path.write_text(original_vocab, encoding="utf-8")
            self.cleanup_day_dir(date_str)

    def test_correct_close_loop(self):
        """openmy correct close-loop 应该追加 correction 事件。"""
        corrections_path = PROJECT_ROOT / "data" / "corrections.jsonl"
        context_path = PROJECT_ROOT / "data" / "active_context.json"
        original_corrections = corrections_path.read_text(encoding="utf-8") if corrections_path.exists() else None
        original_context = context_path.read_text(encoding="utf-8") if context_path.exists() else None

        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text(
            json.dumps(self.make_context_snapshot(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "correct", "close-loop", "README"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = corrections_path.read_text(encoding="utf-8")
            self.assertIn("close_loop", payload)
            self.assertIn("loop_readme", payload)
        finally:
            if original_corrections is None:
                corrections_path.unlink(missing_ok=True)
            else:
                corrections_path.write_text(original_corrections, encoding="utf-8")

            if original_context is None:
                context_path.unlink(missing_ok=True)
            else:
                context_path.write_text(original_context, encoding="utf-8")

    def test_correct_list(self):
        """openmy correct list 应该列出修正历史。"""
        corrections_path = PROJECT_ROOT / "data" / "corrections.jsonl"
        original_corrections = corrections_path.read_text(encoding="utf-8") if corrections_path.exists() else None
        corrections_path.parent.mkdir(parents=True, exist_ok=True)
        corrections_path.write_text(
            json.dumps(
                {
                    "correction_id": "corr_001",
                    "created_at": "2026-04-08T18:00:00+08:00",
                    "actor": "user",
                    "op": "reject_project",
                    "target_type": "project",
                    "target_id": "代理配置",
                    "payload": {},
                    "reason": "不是主项目",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "correct", "list"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("reject_project", result.stdout)
            self.assertIn("代理配置", result.stdout)
        finally:
            if original_corrections is None:
                corrections_path.unlink(missing_ok=True)
            else:
                corrections_path.write_text(original_corrections, encoding="utf-8")

    def test_cli_run_reuses_existing_artifacts(self):
        """openmy run --skip-transcribe 应该能复用已有 transcript/scenes 生成 briefing。"""
        date_str = "2099-01-07"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text(
            "# 2099-01-07\n\n---\n\n## 10:00\n\n老婆，今天晚上吃火锅。",
            encoding="utf-8",
        )
        (day_dir / "scenes.json").write_text(
            (
                '{"scenes":[{"scene_id":"s01","time_start":"10:00","time_end":"10:30",'
                '"text":"老婆，今天晚上吃火锅。","summary":"在约晚饭。","preview":"老婆，今天晚上吃火锅。",'
                '"role":{"addressed_to":"老婆","scene_type_label":"跟人聊","needs_review":false}}],'
                '"stats":{"total_scenes":1,"role_distribution":{"老婆":1},"needs_review_count":0}}'
            ),
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "run", date_str, "--skip-transcribe"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((day_dir / "daily_briefing.json").exists())
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_context_generates_outputs(self):
        """openmy context 应该生成 active_context 产物。"""
        context_path = PROJECT_ROOT / "data" / "active_context.json"
        compact_path = PROJECT_ROOT / "data" / "active_context.compact.md"
        updates_path = PROJECT_ROOT / "data" / "active_context_updates.jsonl"

        original_context = context_path.read_text(encoding="utf-8") if context_path.exists() else None
        original_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else None
        original_updates = updates_path.read_text(encoding="utf-8") if updates_path.exists() else None

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "context", "--compact"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(context_path.exists())
            self.assertTrue(compact_path.exists())
            self.assertTrue(updates_path.exists())
        finally:
            if original_context is None:
                context_path.unlink(missing_ok=True)
            else:
                context_path.write_text(original_context, encoding="utf-8")

            if original_compact is None:
                compact_path.unlink(missing_ok=True)
            else:
                compact_path.write_text(original_compact, encoding="utf-8")

            if original_updates is None:
                updates_path.unlink(missing_ok=True)
            else:
                updates_path.write_text(original_updates, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
