#!/usr/bin/env python3
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestOpenMyCli(unittest.TestCase):
    def make_day_dir(self, date_str: str) -> Path:
        day_dir = PROJECT_ROOT / "data" / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def cleanup_day_dir(self, date_str: str) -> None:
        shutil.rmtree(PROJECT_ROOT / "data" / date_str, ignore_errors=True)

    def seed_view_day(self, date_str: str) -> Path:
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text(
            "# sample\n\n---\n\n## 12:42\n\n老婆，今天晚上吃火锅。",
            encoding="utf-8",
        )
        (day_dir / "daily_briefing.json").write_text(
            json.dumps({"summary": "今天主要在约晚饭。"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (day_dir / "scenes.json").write_text(
            json.dumps(
                {
                    "scenes": [
                        {
                            "scene_id": "scene_001",
                            "time_start": "12:42",
                            "time_end": "12:50",
                            "text": "老婆，今天晚上吃火锅。",
                            "summary": "在约晚饭。",
                            "preview": "老婆，今天晚上吃火锅。",
                            "role": {
                                "addressed_to": "老婆",
                                "scene_type_label": "跟人聊",
                                "needs_review": False,
                            },
                        }
                    ],
                    "stats": {
                        "total_scenes": 1,
                        "role_distribution": {"老婆": 1},
                        "needs_review_count": 0,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return day_dir

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
            timeout=60,
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
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue("openmy" in result.stdout.lower() or "OpenMy" in result.stdout)

    def test_cli_help_lists_quick_start(self):
        """openmy --help 应该显式列出 quick-start。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("quick-start", result.stdout)

    def test_cli_help_lists_skill(self):
        """openmy --help 应该显式列出 skill。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skill", result.stdout)

    def test_cli_quick_start_infers_date_and_reuses_run(self):
        """quick-start 应该自动推断日期并复用 run 主链。"""
        import openmy.cli as cli

        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "TX01_MIC005_20260408_131552_orig.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")

        parser = cli.build_parser()
        args = parser.parse_args(["quick-start", str(audio_path)])

        with (
            patch("openmy.cli.cmd_run", return_value=0) as run_mock,
            patch("openmy.cli.ensure_runtime_dependencies", return_value=None),
            patch("openmy.cli.launch_local_report", return_value=None),
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 0)
        self.assertEqual(run_mock.call_count, 1)
        forwarded_args = run_mock.call_args.args[0]
        self.assertEqual(forwarded_args.date, "2026-04-08")
        self.assertEqual(forwarded_args.audio, [str(audio_path)])
        self.assertFalse(forwarded_args.skip_transcribe)

    def test_cli_quick_start_reports_missing_gemini_key_in_plain_chinese(self):
        """quick-start 缺 key 时应该给中文人话提示。"""
        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "sample.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")
        env_path = PROJECT_ROOT / ".env"
        backup_path = PROJECT_ROOT / ".env.test-backup"
        if backup_path.exists():
            backup_path.unlink()
        if env_path.exists():
            env_path.rename(backup_path)

        try:
            env = os.environ.copy()
            env.pop("GEMINI_API_KEY", None)

            result = subprocess.run(
                [sys.executable, "-m", "openmy", "quick-start", str(audio_path)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
                env=env,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("GEMINI_API_KEY", result.stdout + result.stderr)
            self.assertIn(".env", result.stdout + result.stderr)
        finally:
            if backup_path.exists():
                backup_path.rename(env_path)

    def test_skill_status_get_outputs_json(self):
        import openmy.cli as cli

        parser = cli.build_parser()
        args = parser.parse_args(["skill", "status.get", "--json"])
        stdout = io.StringIO()

        with (
            patch("openmy.cli.find_all_dates", return_value=["2026-04-08"]),
            patch(
                "openmy.cli.get_date_status",
                return_value={
                    "date": "2026-04-08",
                    "has_transcript": True,
                    "has_raw": True,
                    "has_scenes": True,
                    "has_briefing": True,
                    "word_count": 120,
                    "scene_count": 3,
                    "role_distribution": {"AI助手": 2, "自己": 1},
                },
            ),
            patch("sys.stdout", stdout),
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["action"], "status.get")
        self.assertEqual(payload["items"][0]["date"], "2026-04-08")

    def test_cli_quick_start_launches_report_on_partial_run(self):
        """quick-start 部分完成时也应该拉起本地网页。"""
        import openmy.cli as cli

        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "TX01_MIC005_20260408_131552_orig.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")

        parser = cli.build_parser()
        args = parser.parse_args(["quick-start", str(audio_path)])

        with (
            patch("openmy.cli.cmd_run", return_value=2),
            patch("openmy.cli.ensure_runtime_dependencies", return_value=None),
            patch("openmy.cli.launch_local_report", return_value=None) as launch_mock,
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 2)
        launch_mock.assert_called_once()

    def test_cli_view_existing_date(self):
        """openmy view 2026-04-06 应该输出场景概览。"""
        date_str = "2099-01-10"
        self.seed_view_day(date_str)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "view", date_str],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("12:42", result.stdout)
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_view_nonexistent_date(self):
        """不存在的日期应该友好报错。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "view", "1999-01-01"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_cli_roles_nonexistent_date(self):
        """没有清洗文本时，roles 应该友好报错。"""
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "roles", "1999-01-01"],
            capture_output=True,
            text=True,
            timeout=60,
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
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output_dir / "daily_briefing.json").exists())
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_clean_generates_output(self):
        """openmy clean 应该从 raw 生成 transcript.md（规则引擎，不调 API）。"""
        import argparse

        date_str = "2099-01-03"
        day_dir = self.make_day_dir(date_str)
        raw_text = "# 2099-01-03 原始\n\n---\n\n## 10:00\n\n嗯\n老婆，今天去散步。"
        (day_dir / "transcript.raw.md").write_text(raw_text, encoding="utf-8")

        try:
            from openmy.cli import cmd_clean
            args = argparse.Namespace(date=date_str)
            result = cmd_clean(args)
            self.assertEqual(result, 0)

            transcript = (day_dir / "transcript.md").read_text(encoding="utf-8")
            self.assertIn("老婆", transcript)
            # 规则引擎应该删掉独立的"嗯"行
            self.assertNotIn("\n嗯\n", transcript)
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_roles_generates_scenes(self):
        """openmy roles 应该只切场景，不再自动做角色识别。"""
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
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((day_dir / "scenes.json").exists())
            payload = json.loads((day_dir / "scenes.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["stats"]["role_distribution"], {})
            self.assertEqual(payload["stats"]["needs_review_count"], 0)
            self.assertEqual(payload["scenes"][0]["role"]["addressed_to"], "")
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
                timeout=60,
                cwd=PROJECT_ROOT,
                env=env,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_distill_ignores_role_hint_when_roles_are_frozen(self):
        """openmy distill 不应继续把角色标签塞进蒸馏 prompt。"""
        date_str = "2099-01-11"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "scenes.json").write_text(
            json.dumps(
                {
                    "scenes": [
                        {
                            "scene_id": "s01",
                            "time_start": "10:00",
                            "time_end": "10:10",
                            "text": "老婆，今天晚上吃火锅。",
                            "summary": "",
                            "preview": "老婆，今天晚上吃火锅。",
                            "role": {
                                "addressed_to": "老婆",
                                "scene_type": "interpersonal",
                                "scene_type_label": "跟人聊",
                            },
                        }
                    ],
                    "stats": {"total_scenes": 1, "role_distribution": {"老婆": 1}, "needs_review_count": 0},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        try:
            from openmy import cli as openmy_cli
            from openmy.config import GEMINI_MODEL

            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with patch("openmy.services.distillation.distiller.summarize_scene", return_value="新的摘要") as mock_summarize:
                    result = openmy_cli.cmd_distill(argparse.Namespace(date=date_str))

            self.assertEqual(result, 0)
            mock_summarize.assert_called_once_with(
                "老婆，今天晚上吃火锅。",
                "test-key",
                GEMINI_MODEL,
            )
            payload = json.loads((day_dir / "scenes.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["scenes"][0]["summary"], "新的摘要")
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
                timeout=60,
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
                timeout=60,
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
                timeout=60,
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
                timeout=60,
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

    def test_correct_scene_role_updates_scene_and_stats(self):
        """openmy correct scene-role 应该原地修正 scenes.json 并更新统计。"""
        date_str = "2099-01-12"
        day_dir = self.make_day_dir(date_str)
        scenes_path = day_dir / "scenes.json"
        corrections_path = PROJECT_ROOT / "data" / "corrections.jsonl"
        original_corrections = corrections_path.read_text(encoding="utf-8") if corrections_path.exists() else None
        scenes_path.write_text(
            json.dumps(
                {
                    "scenes": [
                        {
                            "scene_id": "s01",
                            "time_start": "13:15",
                            "time_end": "13:25",
                            "text": "OpenMy 怎么样？对，可以。",
                            "summary": "讨论产品名。",
                            "preview": "OpenMy 怎么样？",
                            "role": {
                                "category": "interpersonal",
                                "entity_id": "妈妈",
                                "relation_label": "妈妈",
                                "confidence": 0.95,
                                "scene_type": "interpersonal",
                                "scene_type_label": "跟人聊",
                                "addressed_to": "妈妈",
                                "source": "declared",
                                "source_label": "亲口说的",
                                "evidence": "亲口说了妈妈",
                                "needs_review": False,
                            },
                        },
                        {
                            "scene_id": "s02",
                            "time_start": "13:30",
                            "time_end": "13:35",
                            "text": "Codex，继续跑一下。",
                            "summary": "继续让 AI 跑任务。",
                            "preview": "Codex，继续跑一下。",
                            "role": {
                                "category": "ai",
                                "entity_id": "AI助手",
                                "relation_label": "AI助手",
                                "confidence": 0.9,
                                "scene_type": "ai",
                                "scene_type_label": "跟AI说",
                                "addressed_to": "AI助手",
                                "source": "rule_matched",
                                "source_label": "一看就知道",
                                "evidence": "命中关键词：Codex",
                                "needs_review": False,
                            },
                        },
                    ],
                    "stats": {
                        "total_scenes": 2,
                        "role_distribution": {"妈妈": 1, "AI助手": 1},
                        "needs_review_count": 0,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "correct", "scene-role", date_str, "s01", "AI助手"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(scenes_path.read_text(encoding="utf-8"))
            scene = payload["scenes"][0]
            self.assertEqual(scene["role"]["addressed_to"], "AI助手")
            self.assertEqual(scene["role"]["scene_type"], "ai")
            self.assertEqual(scene["role"]["scene_type_label"], "跟AI说")
            self.assertEqual(scene["role"]["source"], "human_confirmed")
            self.assertEqual(payload["stats"]["role_distribution"], {"AI助手": 2})

            corrections_log = corrections_path.read_text(encoding="utf-8")
            self.assertIn("confirm_scene_role", corrections_log)
            self.assertIn(f"{date_str}:s01", corrections_log)
        finally:
            if original_corrections is None:
                corrections_path.unlink(missing_ok=True)
            else:
                corrections_path.write_text(original_corrections, encoding="utf-8")
            self.cleanup_day_dir(date_str)

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
            env = os.environ.copy()
            env.pop("GEMINI_API_KEY", None)
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "run", date_str, "--skip-transcribe"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((day_dir / "daily_briefing.json").exists())
        finally:
            self.cleanup_day_dir(date_str)

    def test_cmd_run_writes_partial_status_when_extract_times_out(self):
        """run 在提取超时时应该写出完整运行状态并返回部分成功。"""
        from openmy.commands import run as run_command
        from openmy.services.extraction import extractor

        date_str = "2099-01-12"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        scenes_path = day_dir / "scenes.json"

        transcript_path.write_text("# 2099-01-12\n\n---\n\n## 10:00\n\n今天记一下。", encoding="utf-8")
        scenes_payload = {
            "scenes": [
                {
                    "scene_id": "s01",
                    "time_start": "10:00",
                    "time_end": "10:05",
                    "text": "今天记一下。",
                    "summary": "在口述记录。",
                    "preview": "今天记一下。",
                    "role": {"addressed_to": "自己", "scene_type_label": "自言自语", "needs_review": False},
                }
            ],
            "stats": {"total_scenes": 1, "role_distribution": {"自己": 1}, "needs_review_count": 0},
        }
        scenes_path.write_text(json.dumps(scenes_payload, ensure_ascii=False), encoding="utf-8")

        try:
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False),
                patch("openmy.services.roles.resolver.resolve_roles", side_effect=lambda scenes, **kwargs: scenes),
                patch("openmy.services.roles.resolver.scenes_to_dict", return_value=scenes_payload),
                patch(
                    "openmy.services.extraction.extractor.run_core_extraction",
                    side_effect=extractor.ExtractionTimeoutError("Gemini 提取超时（45s）"),
                    create=True,
                ),
                patch("openmy.services.context.consolidation.consolidate") as consolidate_mock,
            ):
                result = run_command.cmd_run(argparse.Namespace(date=date_str, audio=[], skip_transcribe=True))

            self.assertEqual(result, 2)
            consolidate_mock.assert_not_called()

            status_payload = json.loads((day_dir / "run_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["status"], "partial")
            self.assertEqual(status_payload["current_step"], "extract_core")
            self.assertEqual(status_payload["steps"]["roles"]["status"], "skipped")
            self.assertEqual(status_payload["steps"]["briefing"]["status"], "completed")
            self.assertEqual(status_payload["steps"]["extract_core"]["status"], "failed")
            self.assertIn("超时", status_payload["steps"]["extract_core"]["message"])
            self.assertEqual(status_payload["steps"]["extract_enrich"]["status"], "skipped")
            self.assertEqual(status_payload["steps"]["consolidate"]["status"], "skipped")
        finally:
            self.cleanup_day_dir(date_str)

    def test_cmd_run_keeps_main_chain_complete_when_extract_enrich_fails(self):
        """第二阶段补全失败时，不应回滚第一阶段核心真相和 active_context 聚合。"""
        from openmy.commands import run as run_command
        from openmy.services.extraction import extractor

        date_str = "2099-01-22"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        scenes_path = day_dir / "scenes.json"

        transcript_path.write_text("# 2099-01-22\n\n---\n\n## 10:00\n\n今天记一下。", encoding="utf-8")
        scenes_payload = {
            "scenes": [
                {
                    "scene_id": "s01",
                    "time_start": "10:00",
                    "time_end": "10:05",
                    "text": "今天记一下。",
                    "summary": "在口述记录。",
                    "preview": "今天记一下。",
                    "role": {"addressed_to": "自己", "scene_type_label": "自言自语", "needs_review": False},
                }
            ],
            "stats": {"total_scenes": 1, "role_distribution": {"自己": 1}, "needs_review_count": 0},
        }
        scenes_path.write_text(json.dumps(scenes_payload, ensure_ascii=False), encoding="utf-8")

        core_payload = {
            "daily_summary": "今天先把核心真相定下来。",
            "events": [],
            "intents": [
                {
                    "intent_id": "intent_001",
                    "kind": "action_item",
                    "what": "补 README",
                    "status": "open",
                    "who": {"kind": "user", "label": "老板"},
                    "confidence_label": "high",
                    "confidence_score": 0.9,
                    "needs_review": False,
                    "evidence_quote": "今天把 README 补一下。",
                    "topic": "OpenMy",
                    "project_hint": "OpenMy",
                    "due": {"raw_text": "", "iso_date": "", "granularity": "none"},
                    "speech_act": "",
                    "source_scene_id": "",
                    "source_recording_id": "",
                }
            ],
            "facts": [
                {
                    "fact_type": "idea",
                    "content": "OpenMy 先求跑通。",
                    "topic": "OpenMy",
                    "confidence_label": "medium",
                    "confidence_score": 0.7,
                    "source_scene_id": "",
                }
            ],
            "role_hints": [],
            "extract_enrich_status": "pending",
            "extract_enrich_message": "",
        }

        try:
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False),
                patch("openmy.services.roles.resolver.resolve_roles", side_effect=lambda scenes, **kwargs: scenes),
                patch("openmy.services.roles.resolver.scenes_to_dict", return_value=scenes_payload),
                patch(
                    "openmy.services.extraction.extractor.run_core_extraction",
                    return_value=core_payload,
                    create=True,
                ),
                patch(
                    "openmy.services.extraction.extractor.run_enrichment_extraction",
                    side_effect=extractor.ExtractionTimeoutError("Gemini 补全超时（45s）"),
                    create=True,
                ),
                patch("openmy.services.context.consolidation.consolidate") as consolidate_mock,
            ):
                result = run_command.cmd_run(argparse.Namespace(date=date_str, audio=[], skip_transcribe=True))

            self.assertEqual(result, 0)
            consolidate_mock.assert_called_once()

            status_payload = json.loads((day_dir / "run_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["status"], "completed")
            self.assertEqual(status_payload["steps"]["roles"]["status"], "skipped")
            self.assertEqual(status_payload["steps"]["extract_core"]["status"], "completed")
            self.assertEqual(status_payload["steps"]["consolidate"]["status"], "completed")
            self.assertEqual(status_payload["steps"]["extract_enrich"]["status"], "failed")

            meta_payload = json.loads((day_dir / f"{date_str}.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta_payload["extract_enrich_status"], "failed")
            self.assertIn("超时", meta_payload["extract_enrich_message"])
            self.assertEqual(meta_payload["intents"][0]["status"], "open")
            self.assertEqual(meta_payload["intents"][0]["topic"], "OpenMy")
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
                timeout=60,
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

    def test_agent_recent_routes_to_context(self):
        """openmy agent --recent 应该走活动上下文入口。"""
        context_path = PROJECT_ROOT / "data" / "active_context.json"
        compact_path = PROJECT_ROOT / "data" / "active_context.compact.md"
        updates_path = PROJECT_ROOT / "data" / "active_context_updates.jsonl"

        original_context = context_path.read_text(encoding="utf-8") if context_path.exists() else None
        original_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else None
        original_updates = updates_path.read_text(encoding="utf-8") if updates_path.exists() else None

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "agent", "--recent"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Level 0", result.stdout)
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

    def test_agent_day_routes_to_view(self):
        """openmy agent --day 应该走单日查看入口。"""
        date_str = "2099-01-11"
        self.seed_view_day(date_str)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "agent", "--day", date_str],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("日报", result.stdout)
        finally:
            self.cleanup_day_dir(date_str)

    def test_agent_reject_decision_routes_to_correct(self):
        """openmy agent --reject-decision 应该追加 correction 事件。"""
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
                [sys.executable, "-m", "openmy", "agent", "--reject-decision", "中午改吃河南蒸菜"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = corrections_path.read_text(encoding="utf-8")
            self.assertIn("reject_decision", payload)
            self.assertIn("decision_lunch", payload)
        finally:
            if original_corrections is None:
                corrections_path.unlink(missing_ok=True)
            else:
                corrections_path.write_text(original_corrections, encoding="utf-8")

            if original_context is None:
                context_path.unlink(missing_ok=True)
            else:
                context_path.write_text(original_context, encoding="utf-8")

    def test_agent_ingest_reuses_existing_artifacts(self):
        """openmy agent --ingest 配合 --skip-transcribe 应该能复用现有数据。"""
        date_str = "2099-01-09"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text(
            "# 2099-01-09\n\n---\n\n## 10:00\n\n老婆，今天晚上吃火锅。",
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
            env = os.environ.copy()
            env.pop("GEMINI_API_KEY", None)
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "agent", "--ingest", date_str, "--skip-transcribe"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((day_dir / "daily_briefing.json").exists())
        finally:
            self.cleanup_day_dir(date_str)


if __name__ == "__main__":
    unittest.main()
