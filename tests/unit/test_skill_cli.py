#!/usr/bin/env python3
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


class TestSkillCliContract(unittest.TestCase):
    def make_day_dir(self, date_str: str) -> Path:
        day_dir = PROJECT_ROOT / "data" / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def cleanup_day_dir(self, date_str: str) -> None:
        shutil.rmtree(PROJECT_ROOT / "data" / date_str, ignore_errors=True)

    def cleanup_context_outputs(self) -> None:
        for path in [
            PROJECT_ROOT / "data" / "active_context.json",
            PROJECT_ROOT / "data" / "active_context.compact.md",
            PROJECT_ROOT / "data" / "active_context_updates.jsonl",
            PROJECT_ROOT / "data" / "corrections.jsonl",
        ]:
            path.unlink(missing_ok=True)

    def make_context_snapshot(self) -> dict:
        return {
            "schema_version": "active_context.v1",
            "user_id": "user_zhousefu",
            "generated_at": "2026-04-10T21:00:00+08:00",
            "context_seq": 1,
            "materialized_from_event_seq": 1,
            "default_delta_window_days": 3,
            "status_line": "最近主要推进 OpenMy；当前有 1 个待办未闭环。",
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
                        "current_goal": "收口 Skill 契约",
                        "next_actions": ["补测试"],
                        "blockers": [],
                        "momentum": "steady",
                        "last_touched_at": "2026-04-10T21:00:00+08:00",
                        "confidence": 0.9,
                        "source_rank": "aggregate",
                    }
                ],
                "open_loops": [
                    {
                        "id": "loop_readme",
                        "loop_id": "loop_readme",
                        "title": "README",
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
                "recent_decisions": [],
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

    def test_skill_day_get_uses_versioned_json_contract(self):
        date_str = "2099-02-01"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text("# sample", encoding="utf-8")
        (day_dir / "daily_briefing.json").write_text(
            json.dumps({"summary": "今天主要推进 Skill 重构。"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (day_dir / "scenes.json").write_text(
            json.dumps(
                {
                    "scenes": [{"scene_id": "scene_001", "time_start": "10:00", "text": "测试"}],
                    "stats": {"total_scenes": 1, "role_distribution": {}, "needs_review_count": 0},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "skill", "day.get", "--date", date_str, "--json"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("\x1b[", result.stdout)

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "day.get")
            self.assertEqual(payload["version"], "v1")
            self.assertIn("data", payload)
            self.assertIn("human_summary", payload)
            self.assertIn("artifacts", payload)
            self.assertIn("next_actions", payload)
            self.assertEqual(payload["data"]["date"], date_str)
        finally:
            self.cleanup_day_dir(date_str)

    def test_skill_unknown_action_returns_error_json_not_argparse_usage(self):
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "skill", "unknown.action", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), "")

        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["action"], "unknown.action")
        self.assertEqual(payload["error_code"], "unknown_action")
        self.assertEqual(payload["version"], "v1")

    def test_skill_correction_apply_accepts_op_and_arg_flags(self):
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
                [
                    sys.executable,
                    "-m",
                    "openmy",
                    "skill",
                    "correction.apply",
                    "--op",
                    "close-loop",
                    "--arg",
                    "README",
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "correction.apply")
            self.assertEqual(payload["version"], "v1")
            self.assertEqual(payload["data"]["op"], "close-loop")
            self.assertEqual(payload["data"]["args"], ["README"])
            self.assertIn("human_summary", payload)
            self.assertIn("close_loop", corrections_path.read_text(encoding="utf-8"))
        finally:
            if original_corrections is None:
                corrections_path.unlink(missing_ok=True)
            else:
                corrections_path.write_text(original_corrections, encoding="utf-8")

            if original_context is None:
                context_path.unlink(missing_ok=True)
            else:
                context_path.write_text(original_context, encoding="utf-8")

    def test_skill_correction_apply_typo_uses_date_from_skill_args(self):
        date_str = "2099-02-02"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        transcript_path.write_text("## 10:00\n\n青维今天去散步。", encoding="utf-8")

        corrections_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "corrections.json"
        vocab_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "vocab.txt"
        original_corrections = corrections_path.read_text(encoding="utf-8")
        original_vocab = vocab_path.read_text(encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "openmy",
                    "skill",
                    "correction.apply",
                    "--op",
                    "typo",
                    "--arg",
                    "青维",
                    "--arg",
                    "青梅",
                    "--date",
                    date_str,
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "correction.apply")
            self.assertEqual(payload["version"], "v1")
            self.assertEqual(payload["data"]["op"], "typo")
            self.assertEqual(payload["data"]["args"], [date_str, "青维", "青梅"])
            self.assertIn("青梅", transcript_path.read_text(encoding="utf-8"))
        finally:
            corrections_path.write_text(original_corrections, encoding="utf-8")
            vocab_path.write_text(original_vocab, encoding="utf-8")
            self.cleanup_day_dir(date_str)

    def test_agent_recent_is_compat_alias_over_skill_contract(self):
        result = subprocess.run(
            [sys.executable, "-m", "openmy", "agent", "--recent"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "context.get")
        self.assertEqual(payload["version"], "v1")

    def test_cmd_skill_prints_dispatch_payload_without_extra_rich_output(self):
        import openmy.cli as cli

        parser = cli.build_parser()
        args = parser.parse_args(["skill", "status.get", "--json"])
        stdout = io.StringIO()
        fake_payload = {
            "ok": True,
            "action": "status.get",
            "version": "v1",
            "data": {"total_days": 2},
            "human_summary": "共有 2 天数据。",
            "artifacts": {},
            "next_actions": [],
        }

        with (
            patch("openmy.skill_dispatch.dispatch_skill_action", return_value=(fake_payload, 0)),
            patch("sys.stdout", stdout),
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue()), fake_payload)

    def test_skill_day_run_succeeds_with_sample_audio_sidecar_without_api_key(self):
        date_str = "2099-02-02"
        self.cleanup_day_dir(date_str)
        sample_audio = PROJECT_ROOT / "tests" / "fixtures" / "sample.wav"
        sample_audio_exists = sample_audio.exists()
        if not sample_audio_exists:
            sample_audio.write_bytes(b"wav")

        env = os.environ.copy()
        env.pop("GEMINI_API_KEY", None)
        env.pop("OPENMY_STT_API_KEY", None)
        env.pop("OPENMY_LLM_API_KEY", None)
        env.pop("OPENMY_EXTRACT_API_KEY", None)
        env.pop("OPENMY_DISTILL_API_KEY", None)
        env.pop("OPENMY_ROLES_API_KEY", None)

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "openmy",
                    "skill",
                    "day.run",
                    "--date",
                    date_str,
                    "--audio",
                    str(sample_audio),
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "day.run")
            self.assertEqual(payload["version"], "v1")
            self.assertTrue((PROJECT_ROOT / "data" / date_str / "transcript.raw.md").exists())
            self.assertTrue((PROJECT_ROOT / "data" / date_str / "transcript.md").exists())
            self.assertTrue((PROJECT_ROOT / "data" / date_str / "scenes.json").exists())
            self.assertTrue((PROJECT_ROOT / "data" / date_str / "daily_briefing.json").exists())
        finally:
            self.cleanup_day_dir(date_str)
            self.cleanup_context_outputs()
            if not sample_audio_exists:
                sample_audio.unlink(missing_ok=True)

    def test_skill_day_run_requires_project_env_stt_key_for_api_transcription(self):
        date_str = "2099-02-04"
        self.cleanup_day_dir(date_str)
        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "no-sidecar.wav"
        audio_path.write_bytes(b"wav")

        env_path = PROJECT_ROOT / ".env"
        backup_path = PROJECT_ROOT / ".env.test-backup"
        if backup_path.exists():
            backup_path.unlink()
        if env_path.exists():
            env_path.rename(backup_path)

        env = os.environ.copy()
        env["GEMINI_API_KEY"] = "shadow-shell-key"
        env.pop("OPENMY_STT_API_KEY", None)
        env.pop("OPENMY_LLM_API_KEY", None)

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "openmy",
                    "skill",
                    "day.run",
                    "--date",
                    date_str,
                    "--audio",
                    str(audio_path),
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
                env=env,
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["action"], "day.run")
            self.assertEqual(payload["error_code"], "missing_stt_key")
            self.assertIn("语音转写 KEY", payload["message"])
            self.assertIn(".env", payload["hint"])
            self.assertIn("API 转写", payload["hint"])
        finally:
            audio_path.unlink(missing_ok=True)
            self.cleanup_day_dir(date_str)
            self.cleanup_context_outputs()
            if backup_path.exists():
                backup_path.rename(env_path)


if __name__ == "__main__":
    unittest.main()
