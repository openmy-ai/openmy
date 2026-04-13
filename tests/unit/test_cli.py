#!/usr/bin/env python3
import argparse
import io
import importlib
import json
import os
import signal
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestOpenMyCli(unittest.TestCase):
    def read_optional_text(self, path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.exists() else None

    def restore_optional_text(self, path: Path, original: str | None) -> None:
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(original, encoding="utf-8")

    def make_day_dir(self, date_str: str) -> Path:
        day_dir = PROJECT_ROOT / "data" / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def cleanup_day_dir(self, date_str: str) -> None:
        shutil.rmtree(PROJECT_ROOT / "data" / date_str, ignore_errors=True)

    def test_infer_date_from_path_prefers_parent_directory(self):
        from openmy import cli as openmy_cli

        path = PROJECT_ROOT / "data" / "2026-04-08" / "transcript.md"
        self.assertEqual(openmy_cli.infer_date_from_path(path), "2026-04-08")

    def test_openmy_without_args_shows_main_menu(self):
        result = subprocess.run(
            [sys.executable, "-m", "openmy"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OpenMy — 你的个人上下文引擎", result.stdout)
        self.assertIn("openmy weekly", result.stdout)
        self.assertIn("openmy monthly", result.stdout)
        self.assertIn("openmy watch", result.stdout)
        self.assertIn("openmy screen on/off", result.stdout)

    def test_openmy_without_args_shows_onboarding_hint_when_incomplete(self):
        import openmy.cli as cli

        onboarding_path = PROJECT_ROOT / "data" / "onboarding_state.json"
        original = self.read_optional_text(onboarding_path)
        onboarding_path.parent.mkdir(parents=True, exist_ok=True)
        onboarding_path.write_text(json.dumps({
            "completed": False,
            "recommended_label": "本地中文优先",
            "recommended_reason": "中文录音优先，而且不用密钥。"
        }, ensure_ascii=False), encoding="utf-8")

        try:
            buffer = io.StringIO()
            with patch("sys.stdout", buffer):
                cli.main_with_args(argparse.Namespace(command=None))
            output = buffer.getvalue()
        finally:
            self.restore_optional_text(onboarding_path, original)

        self.assertIn("首次使用引导", output)
        self.assertIn("本地中文优先", output)

    def seed_view_day(self, date_str: str) -> Path:
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text(
            "# sample\n\n---\n\n## 12:42\n\n伴侣，今天晚上吃火锅。",
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
                            "text": "伴侣，今天晚上吃火锅。",
                            "summary": "在约晚饭。",
                            "preview": "伴侣，今天晚上吃火锅。",
                            "role": {
                                "addressed_to": "伴侣",
                                "scene_type_label": "跟人聊",
                                "needs_review": False,
                            },
                        }
                    ],
                    "stats": {
                        "total_scenes": 1,
                        "role_distribution": {"伴侣": 1},
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
            "user_id": "user_default",
            "generated_at": "2026-04-08T23:58:10+08:00",
            "context_seq": 1,
            "materialized_from_event_seq": 1,
            "default_delta_window_days": 3,
            "status_line": "最近主要推进 OpenMy；当前有 1 个待办未闭环；高频互动对象是 伴侣。",
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
                        "decision": "中午改吃家常菜",
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

    def test_cli_help_uses_english_when_locale_is_not_chinese(self):
        import openmy.cli as cli

        original_lang = os.environ.get("LANG")
        os.environ["LANG"] = "en_US.UTF-8"
        try:
            cli = importlib.reload(cli)
            parser = cli.build_parser()
            help_text = parser.format_help()
        finally:
            if original_lang is None:
                os.environ.pop("LANG", None)
            else:
                os.environ["LANG"] = original_lang
            importlib.reload(cli)

        self.assertIn("Available commands", help_text)
        self.assertIn("Upgrade the current OpenMy installation", help_text)

    def test_cli_help_uses_chinese_when_locale_is_chinese(self):
        import openmy.cli as cli

        original_lang = os.environ.get("LANG")
        os.environ["LANG"] = "zh_CN.UTF-8"
        try:
            cli = importlib.reload(cli)
            parser = cli.build_parser()
            help_text = parser.format_help()
        finally:
            if original_lang is None:
                os.environ.pop("LANG", None)
            else:
                os.environ["LANG"] = original_lang
            importlib.reload(cli)

        self.assertIn("可用命令", help_text)
        self.assertIn("升级当前 OpenMy 安装", help_text)

    def test_cli_self_update_runs_pip_upgrade(self):
        import openmy.cli as cli

        parser = cli.build_parser()
        args = parser.parse_args(["self-update"])

        with patch("openmy.cli.subprocess.run", return_value=subprocess.CompletedProcess(args=[], returncode=0)) as run_mock:
            result = cli.main_with_args(args)

        self.assertEqual(result, 0)
        run_mock.assert_called_once()
        self.assertEqual(
            run_mock.call_args.args[0],
            [sys.executable, "-m", "pip", "install", "--upgrade", "openmy"],
        )

    def test_cli_quick_start_infers_date_and_reuses_run(self):
        """quick-start 应该自动推断日期并复用 run 主链。"""
        import openmy.cli as cli

        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "TX01_MIC005_20260408_131552_orig.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")

        parser = cli.build_parser()
        args = parser.parse_args(["quick-start", str(audio_path)])

        with (
            patch("openmy.commands.run.get_stt_provider_name", return_value="faster-whisper"),
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

    def test_cli_quick_start_accepts_stt_provider_flags(self):
        import openmy.cli as cli

        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "TX01_MIC005_20260408_131552_orig.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")

        parser = cli.build_parser()
        args = parser.parse_args(
            [
                "quick-start",
                str(audio_path),
                "--stt-provider",
                "faster-whisper",
                "--stt-model",
                "small",
                "--stt-vad",
            ]
        )

        with (
            patch("openmy.cli.cmd_run", return_value=0) as run_mock,
            patch("openmy.cli.ensure_runtime_dependencies", return_value=None),
            patch("openmy.cli.launch_local_report", return_value=None),
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 0)
        forwarded_args = run_mock.call_args.args[0]
        self.assertEqual(forwarded_args.stt_provider, "faster-whisper")

    def test_cli_quick_start_shows_guidance_when_no_provider_selected(self):
        import openmy.cli as cli

        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "TX01_MIC005_20260408_131552_orig.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")

        parser = cli.build_parser()
        args = parser.parse_args(["quick-start", str(audio_path)])
        onboarding_path = PROJECT_ROOT / "data" / "onboarding_state.json"
        original = self.read_optional_text(onboarding_path)

        try:
            with (
                patch("openmy.commands.run.get_stt_provider_name", return_value=""),
                patch("openmy.commands.run.get_stt_api_key", return_value=""),
                patch("openmy.commands.run._cli") as cli_mock,
            ):
                fake_console = cli.console
                cli_mock.return_value = cli
                with patch.object(fake_console, "print") as print_mock:
                    result = cli.main_with_args(args)

            self.assertEqual(result, 1)
            panel = print_mock.call_args_list[0].args[0]
            rendered = str(panel.renderable)
            self.assertIn("还差一步", rendered)
            self.assertIn("profile.set --stt-provider", rendered)
            self.assertTrue(onboarding_path.exists())
        finally:
            self.restore_optional_text(onboarding_path, original)

    def test_cli_quick_start_accepts_funasr_and_enrich_mode_flags(self):
        import openmy.cli as cli

        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "TX01_MIC005_20260408_131552_orig.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")

        parser = cli.build_parser()
        args = parser.parse_args(
            [
                "quick-start",
                str(audio_path),
                "--stt-provider",
                "funasr",
                "--stt-model",
                "paraformer-zh",
                "--stt-enrich-mode",
                "recommended",
            ]
        )

        with (
            patch("openmy.cli.cmd_run", return_value=0) as run_mock,
            patch("openmy.cli.ensure_runtime_dependencies", return_value=None),
            patch("openmy.cli.launch_local_report", return_value=None),
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 0)
        forwarded_args = run_mock.call_args.args[0]
        self.assertEqual(forwarded_args.stt_provider, "funasr")
        self.assertEqual(forwarded_args.stt_enrich_mode, "recommended")

    def test_cli_quick_start_demo_uses_bundled_fixture_without_runtime_check(self):
        import openmy.cli as cli

        parser = cli.build_parser()
        args = parser.parse_args(["quick-start", "--demo"])
        demo_audio = PROJECT_ROOT / "tests" / "fixtures" / "TX01_MIC005_20991231_120000_demo.wav"
        demo_audio.parent.mkdir(parents=True, exist_ok=True)
        demo_audio.write_bytes(b"wav")

        try:
            with (
                patch("openmy.commands.run._prepare_demo_inputs", return_value=(demo_audio, "演示一下 OpenMy。")),
                patch("openmy.commands.run._seed_demo_transcript", return_value=None) as seed_mock,
                patch("openmy.cli.cmd_run", return_value=0) as run_mock,
                patch("openmy.cli.ensure_runtime_dependencies", return_value=None) as ensure_mock,
                patch("openmy.cli.launch_local_report", return_value=None),
            ):
                result = cli.main_with_args(args)

            self.assertEqual(result, 0)
            ensure_mock.assert_not_called()
            seed_mock.assert_called_once_with("2099-12-31", "演示一下 OpenMy。")
            forwarded_args = run_mock.call_args.args[0]
            self.assertIsNone(forwarded_args.audio)
            self.assertTrue(forwarded_args.skip_transcribe)
            self.assertEqual(forwarded_args.date, "2099-12-31")
        finally:
            demo_audio.unlink(missing_ok=True)

    def test_runtime_dependency_check_allows_local_funasr_without_key(self):
        import openmy.cli as cli

        with (
            patch("openmy.cli.shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
            patch.dict(
                os.environ,
                {
                    "OPENMY_STT_PROVIDER": "funasr",
                    "OPENMY_STT_MODEL": "paraformer-zh",
                },
                clear=True,
            ),
        ):
            cli.ensure_runtime_dependencies(stt_provider="funasr")

    def test_cli_quick_start_requires_project_env_even_if_shell_has_gemini_key(self):
        """quick-start 只认项目 .env，不能吃到个人 shell 里的 key。"""
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
            env["GEMINI_API_KEY"] = "shadow-shell-key"

            result = subprocess.run(
                [sys.executable, "-m", "openmy", "quick-start", str(audio_path), "--stt-provider", "gemini"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
                env=env,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(".env", result.stdout + result.stderr)
            self.assertIn("语音转写", result.stdout + result.stderr)
        finally:
            if backup_path.exists():
                backup_path.rename(env_path)

    def test_ensure_runtime_dependencies_checks_project_env_before_ffmpeg(self):
        import openmy.cli as cli

        with (
            patch("openmy.cli.prepare_project_runtime_env", return_value=False),
            patch("openmy.cli.get_stt_provider_name", return_value="gemini"),
            patch("openmy.cli.get_stt_api_key", return_value=""),
            patch("openmy.cli.shutil.which", return_value=None),
        ):
            with self.assertRaises(cli.FriendlyCliError) as ctx:
                cli.ensure_runtime_dependencies(stt_provider="gemini")

        self.assertIn(".env", str(ctx.exception))

    def test_ensure_runtime_dependencies_allows_local_stt_without_api_key(self):
        import openmy.cli as cli

        with (
            patch("openmy.cli.shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
            patch("openmy.cli.load_project_env", return_value=False),
            patch("openmy.cli.get_stt_provider_name", return_value="faster-whisper"),
            patch("openmy.cli.get_stt_api_key", return_value=""),
            patch("openmy.cli.get_llm_api_key", return_value="llm-key"),
        ):
            cli.ensure_runtime_dependencies()

    def test_skill_status_get_outputs_json(self):
        import openmy.cli as cli

        parser = cli.build_parser()
        args = parser.parse_args(["skill", "status.get", "--json"])
        stdout = io.StringIO()

        with (
            patch(
                "openmy.skill_dispatch.dispatch_skill_action",
                return_value=(
                    {
                        "ok": True,
                        "action": "status.get",
                        "version": "v1",
                        "data": {
                            "items": [
                                {
                                    "date": "2026-04-08",
                                    "has_transcript": True,
                                    "has_raw": True,
                                    "has_scenes": True,
                                    "has_briefing": True,
                                    "word_count": 120,
                                    "scene_count": 3,
                                    "role_distribution": {"AI助手": 2, "自己": 1},
                                }
                            ],
                            "total_days": 1,
                            "latest_date": "2026-04-08",
                        },
                        "human_summary": "1 day of data available; latest: 2026-04-08.",
                        "artifacts": {"data_root": "data"},
                        "next_actions": [],
                    },
                    0,
                ),
            ),
            patch("sys.stdout", stdout),
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "status.get")
        self.assertEqual(payload["version"], "v1")
        self.assertEqual(payload["data"]["items"][0]["date"], "2026-04-08")

    def test_cli_quick_start_launches_report_on_partial_run(self):
        """quick-start 部分完成时也应该拉起本地网页。"""
        import openmy.cli as cli

        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "TX01_MIC005_20260408_131552_orig.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")

        parser = cli.build_parser()
        args = parser.parse_args(["quick-start", str(audio_path)])

        with (
            patch("openmy.commands.run.get_stt_provider_name", return_value="faster-whisper"),
            patch("openmy.cli.cmd_run", return_value=2),
            patch("openmy.cli.ensure_runtime_dependencies", return_value=None),
            patch("openmy.cli.launch_local_report", return_value=None) as launch_mock,
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 2)
        launch_mock.assert_called_once()

    def test_launch_local_report_restarts_unhealthy_server(self):
        import openmy.cli as cli

        with (
            patch("openmy.cli.is_local_report_running", side_effect=[True, False]),
            patch("openmy.cli.is_local_report_healthy", return_value=False),
            patch("openmy.cli.kill_report_processes") as kill_mock,
            patch("openmy.cli.wait_for_local_report", return_value=True),
            patch("openmy.cli.subprocess.Popen") as popen_mock,
            patch("openmy.cli.webbrowser.open") as open_mock,
        ):
            cli.launch_local_report()

        kill_mock.assert_called_once()
        popen_mock.assert_called_once()
        open_mock.assert_called_once_with("http://127.0.0.1:8420")

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
        raw_text = "# 2099-01-03 原始\n\n---\n\n## 10:00\n\n嗯\n伴侣，今天去散步。"
        (day_dir / "transcript.raw.md").write_text(raw_text, encoding="utf-8")

        try:
            from openmy.cli import cmd_clean
            args = argparse.Namespace(date=date_str)
            result = cmd_clean(args)
            self.assertEqual(result, 0)

            transcript = (day_dir / "transcript.md").read_text(encoding="utf-8")
            self.assertIn("伴侣", transcript)
            # 规则引擎应该删掉独立的"嗯"行
            self.assertNotIn("\n嗯\n", transcript)
        finally:
            self.cleanup_day_dir(date_str)

    def test_cli_roles_generates_scenes(self):
        """openmy roles 应该只切场景，不再自动做角色识别。"""
        date_str = "2099-01-04"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text(
            "# 2099-01-04\n\n---\n\n## 10:00\n\n伴侣，晚上一起吃饭。\n\n## 11:00\n\nClaude 帮我看一下代码。",
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
                            "text": "伴侣，今天晚上吃火锅。",
                            "summary": "",
                            "preview": "伴侣，今天晚上吃火锅。",
                            "role": {
                                "addressed_to": "伴侣",
                                "scene_type": "interpersonal",
                                "scene_type_label": "跟人聊",
                            },
                        }
                    ],
                    "stats": {"total_scenes": 1, "role_distribution": {"伴侣": 1}, "needs_review_count": 0},
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
                "伴侣，今天晚上吃火锅。",
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
        transcript_path.write_text("## 10:00\n\n示例错名今天去散步。", encoding="utf-8")

        corrections_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "corrections.json"
        vocab_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "vocab.txt"
        original_corrections = self.read_optional_text(corrections_path)
        original_vocab = self.read_optional_text(vocab_path)
        corrections_path.parent.mkdir(parents=True, exist_ok=True)
        corrections_path.write_text(json.dumps({"corrections": []}, ensure_ascii=False), encoding="utf-8")
        vocab_path.write_text("示例正名 | 示例说明\n", encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "correct", date_str, "示例错名", "示例正名"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("示例正名", transcript_path.read_text(encoding="utf-8"))
            self.assertNotIn("示例错名今天", transcript_path.read_text(encoding="utf-8"))
        finally:
            self.restore_optional_text(corrections_path, original_corrections)
            self.restore_optional_text(vocab_path, original_vocab)
            self.cleanup_day_dir(date_str)

    def test_correct_typo_subcommand(self):
        """openmy correct typo 应该兼容新的子命令写法。"""
        date_str = "2099-01-08"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        transcript_path.write_text("## 10:00\n\n示例错名今天去散步。", encoding="utf-8")

        corrections_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "corrections.json"
        vocab_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "vocab.txt"
        original_corrections = self.read_optional_text(corrections_path)
        original_vocab = self.read_optional_text(vocab_path)
        corrections_path.parent.mkdir(parents=True, exist_ok=True)
        corrections_path.write_text(json.dumps({"corrections": []}, ensure_ascii=False), encoding="utf-8")
        vocab_path.write_text("示例正名 | 示例说明\n", encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy", "correct", "typo", date_str, "示例错名", "示例正名"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("示例正名", transcript_path.read_text(encoding="utf-8"))
        finally:
            self.restore_optional_text(corrections_path, original_corrections)
            self.restore_optional_text(vocab_path, original_vocab)
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
            self.assertIn('"status": "done"', payload)
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
            "# 2099-01-07\n\n---\n\n## 10:00\n\n伴侣，今天晚上吃火锅。",
            encoding="utf-8",
        )
        (day_dir / "scenes.json").write_text(
            (
                '{"scenes":[{"scene_id":"s01","time_start":"10:00","time_end":"10:30",'
                '"text":"伴侣，今天晚上吃火锅。","summary":"在约晚饭。","preview":"伴侣，今天晚上吃火锅。",'
                '"role":{"addressed_to":"伴侣","scene_type_label":"跟人聊","needs_review":false}}],'
                '"stats":{"total_scenes":1,"role_distribution":{"伴侣":1},"needs_review_count":0}}'
            ),
            encoding="utf-8",
        )
        (day_dir / f"{date_str}.meta.json").write_text(
            json.dumps({"daily_summary": "今天约了晚饭。", "intents": [], "facts": []}, ensure_ascii=False),
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

    def test_cmd_run_with_new_audio_rebuilds_stale_downstream_artifacts(self):
        from openmy.commands import run as run_command

        date_str = "2099-01-24"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        scenes_path = day_dir / "scenes.json"
        briefing_path = day_dir / "daily_briefing.json"
        meta_path = day_dir / f"{date_str}.meta.json"

        transcript_path.write_text("旧 transcript", encoding="utf-8")
        scenes_path.write_text(json.dumps({"scenes": [{"scene_id": "old"}], "stats": {}}, ensure_ascii=False), encoding="utf-8")
        briefing_path.write_text(json.dumps({"summary": "旧 briefing"}, ensure_ascii=False), encoding="utf-8")
        meta_path.write_text(json.dumps({"daily_summary": "旧 meta"}, ensure_ascii=False), encoding="utf-8")

        def fake_transcribe(*args, **kwargs):
            (day_dir / "transcript.raw.md").write_text("# raw", encoding="utf-8")
            return 0

        def fake_clean(args):
            transcript_path.write_text("新 transcript", encoding="utf-8")
            return 0

        segmented_payload = {
            "scenes": [
                {
                    "scene_id": "new",
                    "time_start": "10:00",
                    "time_end": "10:05",
                    "text": "新文本",
                    "summary": "新摘要",
                    "preview": "新文本",
                    "role": {"addressed_to": "", "scene_type_label": "自言自语", "needs_review": False},
                }
            ],
            "stats": {"total_scenes": 1, "role_distribution": {}, "needs_review_count": 0},
        }

        def fake_distill(args):
            return 0

        def fake_briefing(args):
            briefing_path.write_text(json.dumps({"summary": "新 briefing"}, ensure_ascii=False), encoding="utf-8")
            return 0

        try:
            with (
                patch.object(run_command, "transcribe_audio_files", side_effect=fake_transcribe),
                patch("openmy.cli.cmd_clean", side_effect=fake_clean) as clean_mock,
                patch("openmy.cli.build_segmented_scenes_payload", return_value=segmented_payload) as segment_mock,
                patch("openmy.cli.cmd_distill", side_effect=fake_distill) as distill_mock,
                patch("openmy.cli.cmd_briefing", side_effect=fake_briefing) as briefing_mock,
                patch("openmy.commands.run.has_llm_credentials", return_value=False),
                patch("openmy.services.context.consolidation.consolidate"),
            ):
                result = run_command.cmd_run(
                    argparse.Namespace(
                        date=date_str,
                        audio=["/tmp/fake.wav"],
                        skip_transcribe=False,
                        stt_provider="gemini",
                        stt_model="gemini-3.1-flash-lite-preview",
                        stt_vad=False,
                        stt_word_timestamps=False,
                        stt_enrich_mode="off",
                        stt_align=False,
                        stt_diarize=False,
                    )
                )

            self.assertEqual(result, 2)
            clean_mock.assert_called_once()
            segment_mock.assert_called_once()
            distill_mock.assert_not_called()
            briefing_mock.assert_not_called()
            self.assertEqual(transcript_path.read_text(encoding="utf-8"), "新 transcript")
            self.assertEqual(json.loads(scenes_path.read_text(encoding="utf-8"))["scenes"][0]["scene_id"], "new")
            status_payload = json.loads((day_dir / "run_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["current_step"], "extract_core")
            self.assertTrue((transcript_path.with_name("transcript.md.bak")).exists())
            self.assertTrue((scenes_path.with_name("scenes.json.bak")).exists())
            self.assertTrue((briefing_path.with_name("daily_briefing.json.bak")).exists())
            self.assertTrue((meta_path.with_name(f"{date_str}.meta.json.bak")).exists())
        finally:
            self.cleanup_day_dir(date_str)

    def test_cmd_run_auto_discovers_audio_from_configured_source_dir(self):
        from openmy.commands import run as run_command

        date_str = "2099-01-26"
        day_dir = self.make_day_dir(date_str)
        fake_audio = "/tmp/today.wav"

        def fake_transcribe(date_str, audio_files, **kwargs):
            self.assertEqual(audio_files, [fake_audio])
            (day_dir / "transcript.raw.md").write_text("# raw", encoding="utf-8")
            return 0, ""

        def fake_clean(args):
            (day_dir / "transcript.md").write_text("新 transcript", encoding="utf-8")
            return 0

        segmented_payload = {
            "scenes": [
                {
                    "scene_id": "new",
                    "time_start": "10:00",
                    "time_end": "10:05",
                    "text": "新文本",
                    "summary": "",
                    "preview": "新文本",
                    "role": {"addressed_to": "", "scene_type_label": "自言自语", "needs_review": False},
                }
            ],
            "stats": {"total_scenes": 1, "role_distribution": {}, "needs_review_count": 0},
        }

        try:
            with (
                patch.object(run_command, "_discover_audio_inputs", return_value=([fake_audio], "/tmp/audio-source")),
                patch.object(run_command, "transcribe_audio_files", side_effect=fake_transcribe) as transcribe_mock,
                patch("openmy.cli.cmd_clean", side_effect=fake_clean),
                patch("openmy.cli.build_segmented_scenes_payload", return_value=segmented_payload),
                patch("openmy.commands.run.has_llm_credentials", return_value=False),
            ):
                result = run_command.cmd_run(
                    argparse.Namespace(
                        date=date_str,
                        audio=None,
                        skip_transcribe=False,
                        skip_aggregate=True,
                        stt_provider="faster-whisper",
                        stt_model="small",
                        stt_vad=False,
                        stt_word_timestamps=False,
                        stt_enrich_mode="off",
                        stt_align=False,
                        stt_diarize=False,
                    )
                )

            self.assertEqual(result, 2)
            transcribe_mock.assert_called_once()
        finally:
            self.cleanup_day_dir(date_str)

    def test_cmd_run_keeps_backup_artifacts_when_rerun_extract_fails(self):
        from openmy.commands import run as run_command

        date_str = "2099-01-25"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        scenes_path = day_dir / "scenes.json"
        briefing_path = day_dir / "daily_briefing.json"
        meta_path = day_dir / f"{date_str}.meta.json"

        transcript_path.write_text("旧 transcript", encoding="utf-8")
        scenes_path.write_text(json.dumps({"scenes": [{"scene_id": "old"}], "stats": {}}, ensure_ascii=False), encoding="utf-8")
        briefing_path.write_text(json.dumps({"summary": "旧 briefing"}, ensure_ascii=False), encoding="utf-8")
        meta_path.write_text(json.dumps({"daily_summary": "旧 meta"}, ensure_ascii=False), encoding="utf-8")

        def fake_transcribe(*args, **kwargs):
            (day_dir / "transcript.raw.md").write_text("# raw", encoding="utf-8")
            return 0

        def fake_clean(args):
            transcript_path.write_text("新 transcript", encoding="utf-8")
            return 0

        segmented_payload = {
            "scenes": [
                {
                    "scene_id": "new",
                    "time_start": "10:00",
                    "time_end": "10:05",
                    "text": "新文本",
                    "summary": "新摘要",
                    "preview": "新文本",
                    "role": {"addressed_to": "", "scene_type_label": "自言自语", "needs_review": False},
                }
            ],
            "stats": {"total_scenes": 1, "role_distribution": {}, "needs_review_count": 0},
        }

        def fake_briefing(args):
            briefing_path.write_text(json.dumps({"summary": "新 briefing"}, ensure_ascii=False), encoding="utf-8")
            return 0

        try:
            with (
                patch.object(run_command, "transcribe_audio_files", side_effect=fake_transcribe),
                patch("openmy.cli.cmd_clean", side_effect=fake_clean),
                patch("openmy.cli.build_segmented_scenes_payload", return_value=segmented_payload),
                patch("openmy.cli.cmd_briefing", side_effect=fake_briefing),
                patch("openmy.commands.run.has_llm_credentials", side_effect=lambda stage=None: stage == "extract"),
                patch(
                    "openmy.services.extraction.extractor.run_core_extraction",
                    side_effect=RuntimeError("boom"),
                    create=True,
                ),
                patch("openmy.services.context.consolidation.consolidate") as consolidate_mock,
            ):
                result = run_command.cmd_run(
                    argparse.Namespace(
                        date=date_str,
                        audio=["/tmp/fake.wav"],
                        skip_transcribe=False,
                        stt_provider="gemini",
                        stt_model="gemini-3.1-flash-lite-preview",
                        stt_vad=False,
                        stt_word_timestamps=False,
                        stt_enrich_mode="off",
                        stt_align=False,
                        stt_diarize=False,
                    )
                )

            self.assertEqual(result, 2)
            consolidate_mock.assert_not_called()
            self.assertEqual((day_dir / "transcript.md.bak").read_text(encoding="utf-8"), "旧 transcript")
            self.assertEqual(
                json.loads((day_dir / "scenes.json.bak").read_text(encoding="utf-8"))["scenes"][0]["scene_id"],
                "old",
            )
            self.assertEqual(json.loads((day_dir / "daily_briefing.json.bak").read_text(encoding="utf-8"))["summary"], "旧 briefing")
            self.assertEqual(json.loads((day_dir / f"{date_str}.meta.json.bak").read_text(encoding="utf-8"))["daily_summary"], "旧 meta")
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

    def test_cmd_run_marks_timeout_after_completed_step(self):
        from openmy.commands import run as run_command

        date_str = "2099-01-24"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        scenes_path = day_dir / "scenes.json"

        transcript_path.write_text("# 2099-01-24\n\n---\n\n## 10:00\n\n今天记一下。", encoding="utf-8")
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
            with patch("openmy.commands.run._run_timed_out", return_value=True):
                result = run_command.cmd_run(argparse.Namespace(date=date_str, audio=[], skip_transcribe=True))

            self.assertEqual(result, 2)
            status_payload = json.loads((day_dir / "run_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["status"], "timeout")
            self.assertEqual(status_payload["current_step"], "transcribe")
            self.assertIn("30分钟", status_payload["steps"]["transcribe"]["message"])
        finally:
            self.cleanup_day_dir(date_str)

    def test_kill_stale_runs_terminates_other_matching_processes(self):
        from openmy.commands import run as run_command

        current_pid = os.getpid()
        ps_output = "\n".join(
            [
                f"{current_pid} 999 python -m openmy run 2099-01-24",
                "4321 601 python -m openmy run 2099-01-24",
                "8765 20 python -m openmy run 2099-01-24",
                "9876 800 python -m openmy run 2099-01-25",
            ]
        )
        with (
            patch("openmy.commands.run.subprocess.run") as run_mock,
            patch("openmy.commands.run.os.kill") as kill_mock,
        ):
            run_mock.return_value = argparse.Namespace(stdout=ps_output)
            killed = run_command._kill_stale_runs("2099-01-24")

        self.assertEqual(killed, 1)
        kill_mock.assert_called_once_with(4321, signal.SIGTERM)

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

    def test_cmd_run_keeps_main_chain_complete_when_transcription_enrich_fails(self):
        from openmy.commands import run as run_command

        date_str = "2099-01-23"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        scenes_path = day_dir / "scenes.json"
        briefing_path = day_dir / "daily_briefing.json"
        transcription_path = day_dir / "transcript.transcription.json"

        transcript_path.write_text("# 2099-01-23\n\n---\n\n## 10:00\n\n今天上午我在修 OpenMy。", encoding="utf-8")
        scenes_payload = {
            "scenes": [
                {
                    "scene_id": "s01",
                    "time_start": "10:00",
                    "time_end": "10:05",
                    "text": "今天上午我在修 OpenMy。",
                    "summary": "在口述 OpenMy 进展。",
                    "preview": "今天上午我在修 OpenMy。",
                    "role": {"addressed_to": "", "scene_type_label": "自言自语", "needs_review": False},
                }
            ],
            "stats": {"total_scenes": 1, "role_distribution": {}, "needs_review_count": 0},
        }
        scenes_path.write_text(json.dumps(scenes_payload, ensure_ascii=False), encoding="utf-8")
        briefing_path.write_text(json.dumps({"summary": "今天继续推进 OpenMy。"}, ensure_ascii=False), encoding="utf-8")
        transcription_path.write_text(
            json.dumps(
                {
                    "schema_version": "openmy.transcription.v1",
                    "date": date_str,
                    "provider": "faster-whisper",
                    "model": "small",
                    "chunks": [
                        {
                            "chunk_id": "chunk_0001",
                            "chunk_path": str(day_dir / "stt_chunks" / "chunk_0001.mp3"),
                            "time_label": "10:00",
                            "text": "今天上午我在修 OpenMy。",
                            "segments": [],
                            "provider_metadata": {},
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        def fake_transcribe(*args, **kwargs):
            (day_dir / "transcript.raw.md").write_text(
                "# 2099-01-23 上下文（原始）\n\n---\n\n## 10:00\n\n今天上午我在修 OpenMy。\n",
                encoding="utf-8",
            )
            return 0

        def fake_briefing(args):
            briefing_path.write_text(json.dumps({"summary": "今天继续推进 OpenMy。"}, ensure_ascii=False), encoding="utf-8")
            return 0

        rebuilt_scenes_payload = {
            "scenes": [
                {
                    "scene_id": "s01",
                    "time_start": "10:00",
                    "time_end": "10:05",
                    "text": "今天上午我在修 OpenMy。",
                    "summary": "在口述 OpenMy 进展。",
                    "preview": "今天上午我在修 OpenMy。",
                    "role": {"addressed_to": "", "scene_type_label": "自言自语", "needs_review": False},
                }
            ],
            "stats": {"total_scenes": 1, "role_distribution": {}, "needs_review_count": 0},
        }

        try:
            with (
                patch.object(run_command, "transcribe_audio_files", side_effect=fake_transcribe),
                patch.object(run_command, "run_transcription_enrichment", side_effect=RuntimeError("whisperx 缺少依赖"), create=True),
                patch("openmy.cli.build_segmented_scenes_payload", return_value=rebuilt_scenes_payload),
                patch("openmy.cli.cmd_briefing", side_effect=fake_briefing),
                patch("openmy.commands.run._load_existing_core_payload", return_value={"daily_summary": "已有结构化结果", "intents": [], "facts": []}),
                patch("openmy.services.context.consolidation.consolidate") as consolidate_mock,
            ):
                result = run_command.cmd_run(
                    argparse.Namespace(
                        date=date_str,
                        audio=["/tmp/fake.wav"],
                        skip_transcribe=False,
                        stt_align=True,
                        stt_diarize=False,
                        stt_provider="faster-whisper",
                        stt_model="small",
                        stt_vad=False,
                        stt_word_timestamps=False,
                    )
                )

            self.assertEqual(result, 0)
            consolidate_mock.assert_called_once()

            status_payload = json.loads((day_dir / "run_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["status"], "completed")
            self.assertEqual(status_payload["steps"]["transcribe"]["status"], "completed")
            self.assertEqual(status_payload["steps"]["transcribe_enrich"]["status"], "failed")
            self.assertEqual(status_payload["steps"]["consolidate"]["status"], "completed")
            self.assertEqual(status_payload["steps"]["roles"]["skip_reason"], "role_step_frozen")

            meta_payload = json.loads((day_dir / f"{date_str}.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta_payload["transcription_enrich_status"], "failed")
            self.assertIn("缺少依赖", meta_payload["transcription_enrich_message"])
            self.assertEqual(meta_payload["transcription_diarization_status"], "degraded_missing_token")
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
        """openmy agent --recent 应该输出 context.get 的稳定 JSON 契约。"""
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
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "context.get")
            self.assertEqual(payload["version"], "v1")
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
        """openmy agent --day 应该输出 day.get 的稳定 JSON 契约。"""
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
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "day.get")
            self.assertEqual(payload["data"]["date"], date_str)
        finally:
            self.cleanup_day_dir(date_str)

    def test_agent_reject_decision_routes_to_correct(self):
        """openmy agent --reject-decision 应该走 correction.apply 契约。"""
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
                [sys.executable, "-m", "openmy", "agent", "--reject-decision", "中午改吃家常菜"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "correction.apply")
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
        """openmy agent --ingest 配合 --skip-transcribe 应该映射到 day.run 契约。"""
        date_str = "2099-01-09"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text(
            "# 2099-01-09\n\n---\n\n## 10:00\n\n伴侣，今天晚上吃火锅。",
            encoding="utf-8",
        )
        (day_dir / "scenes.json").write_text(
            (
                '{"scenes":[{"scene_id":"s01","time_start":"10:00","time_end":"10:30",'
                '"text":"伴侣，今天晚上吃火锅。","summary":"在约晚饭。","preview":"伴侣，今天晚上吃火锅。",'
                '"role":{"addressed_to":"伴侣","scene_type_label":"跟人聊","needs_review":false}}],'
                '"stats":{"total_scenes":1,"role_distribution":{"伴侣":1},"needs_review_count":0}}'
            ),
            encoding="utf-8",
        )
        (day_dir / f"{date_str}.meta.json").write_text(
            json.dumps({"daily_summary": "今天约了晚饭。", "intents": [], "facts": []}, ensure_ascii=False),
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
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "day.run")
            self.assertTrue((day_dir / "daily_briefing.json").exists())
        finally:
            self.cleanup_day_dir(date_str)

    def test_cmd_weekly_prints_review(self):
        from openmy import cli as openmy_cli

        buffer = io.StringIO()
        with patch.object(openmy_cli, "console", openmy_cli.Console(file=buffer)), patch(
            "openmy.services.aggregation.weekly.generate_weekly_review",
            return_value={
                "week": "2026-W15",
                "summary": "这周主要推进 OpenMy。",
                "projects": ["OpenMy"],
                "wins": ["补好主链"],
                "open_items": ["补细节"],
                "next_week_focus": "继续补细节",
            },
        ):
            result = openmy_cli.cmd_weekly(argparse.Namespace(week="2026-W15"))

        self.assertEqual(result, 0)
        output = buffer.getvalue()
        self.assertIn("本周回顾", output)
        self.assertIn("OpenMy", output)

    def test_cmd_monthly_prints_review(self):
        from openmy import cli as openmy_cli

        buffer = io.StringIO()
        with patch.object(openmy_cli, "console", openmy_cli.Console(file=buffer)), patch(
            "openmy.services.aggregation.monthly.generate_monthly_review",
            return_value={
                "month": "2026-04",
                "summary": "本月主要推进 OpenMy。",
                "projects": ["OpenMy"],
                "key_decisions": ["先做主链"],
                "open_items": ["补菜单"],
                "direction": "继续补菜单",
            },
        ):
            result = openmy_cli.cmd_monthly(argparse.Namespace(month="2026-04"))

        self.assertEqual(result, 0)
        output = buffer.getvalue()
        self.assertIn("本月回顾", output)
        self.assertIn("OpenMy", output)

    def test_cmd_watch_delegates_to_watcher_service(self):
        from openmy import cli as openmy_cli

        with patch("openmy.services.watcher.watch") as watch_mock:
            result = openmy_cli.cmd_watch(argparse.Namespace(directory=None))

        self.assertEqual(result, 0)
        watch_mock.assert_called_once_with(None)

    def test_cmd_screen_updates_env_and_runtime_settings(self):
        from openmy import cli as openmy_cli
        from openmy.services.screen_recognition.settings import ScreenContextSettings

        original_env = self.read_optional_text(openmy_cli.PROJECT_ENV_PATH)
        runtime_path = PROJECT_ROOT / "data" / "runtime" / "screen_context_settings.json"
        original_runtime = runtime_path.read_text(encoding="utf-8") if runtime_path.exists() else None

        settings = ScreenContextSettings(enabled=False, participation_mode="off")
        buffer = io.StringIO()
        try:
            temp_env = PROJECT_ROOT / ".env.test-screen"
            with patch.object(openmy_cli, "console", openmy_cli.Console(file=buffer)), patch.object(
                openmy_cli,
                "PROJECT_ENV_PATH",
                temp_env,
            ), patch("openmy.services.screen_recognition.settings.load_screen_context_settings", return_value=settings), patch(
                "openmy.services.screen_recognition.settings.save_screen_context_settings"
            ) as save_mock, patch(
                "openmy.services.screen_recognition.capture.is_capture_supported", return_value=True
            ), patch(
                "openmy.services.screen_recognition.capture.start_capture_daemon",
                return_value=argparse.Namespace(pid=12345),
            ):
                result = openmy_cli.cmd_screen(argparse.Namespace(action="on"))

            self.assertEqual(result, 0)
            self.assertIn("屏幕识别已开启", buffer.getvalue())
            self.assertEqual(settings.enabled, True)
            self.assertEqual(settings.participation_mode, "summary_only")
            save_mock.assert_called_once()
            self.assertIn("SCREEN_RECOGNITION_ENABLED=true", temp_env.read_text(encoding="utf-8"))
        finally:
            temp_env = PROJECT_ROOT / ".env.test-screen"
            temp_env.unlink(missing_ok=True)
            if original_env is None and openmy_cli.PROJECT_ENV_PATH.exists():
                openmy_cli.PROJECT_ENV_PATH.unlink(missing_ok=True)
            elif original_env is not None:
                openmy_cli.PROJECT_ENV_PATH.write_text(original_env, encoding="utf-8")

            if original_runtime is None:
                runtime_path.unlink(missing_ok=True)
            else:
                runtime_path.write_text(original_runtime, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
