#!/usr/bin/env python3
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class TestSkillDispatch(unittest.TestCase):
    def make_args(self, **overrides):
        base = {
            "action": "status.get",
            "date": None,
            "audio": None,
            "skip_transcribe": False,
            "skip_aggregate": False,
            "correct_args": None,
            "op": None,
            "arg": None,
            "status": "done",
            "level": 1,
            "compact": False,
            "json": True,
            "payload_json": None,
            "payload_file": None,
            "name": None,
            "language": None,
            "timezone": None,
            "audio_source": None,
            "stt_provider": None,
            "export_provider": None,
            "export_path": None,
            "export_key": None,
            "export_db": None,
            "screen_recognition": None,
            "week": None,
            "month": None,
        }
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_registry_contains_exact_required_actions(self):
        from openmy import skill_dispatch

        self.assertEqual(
            set(skill_dispatch.ACTION_HANDLERS.keys()),
            {
                "context.get",
                "context.query",
                "correction.apply",
                "day.get",
                "day.run",
                "aggregate",
                "aggregate.monthly",
                "aggregate.weekly",
                "distill.pending",
                "distill.submit",
                "extract.core.pending",
                "extract.core.submit",
                "health.check",
                "profile.get",
                "profile.set",
                "status.get",
                "vocab.init",
            },
        )

    def test_dispatch_unknown_action_returns_contract_error(self):
        from openmy import skill_dispatch

        payload, exit_code = skill_dispatch.dispatch_skill_action("unknown.action", self.make_args(action="unknown.action"))
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["error"])
        self.assertEqual(payload["action"], "unknown.action")
        self.assertEqual(payload["error_code"], "unknown_action")
        self.assertIn("fix", payload)
        self.assertIn("message_en", payload)
        self.assertIn("fix_en", payload)
        self.assertIn("doc_url", payload)
        self.assertEqual(payload["version"], "v1")

    def test_correction_apply_normalizes_op_and_arg_flags(self):
        from openmy import skill_dispatch

        self.assertEqual(
            skill_dispatch.build_correction_tokens(self.make_args(op="close-loop", arg=["README"], correct_args=None)),
            ["close-loop", "README"],
        )

    def test_correction_apply_injects_date_for_typo_ops(self):
        from openmy import skill_dispatch

        self.assertEqual(
            skill_dispatch.build_correction_tokens(
                self.make_args(date="2026-04-09", op="typo", arg=["错词", "正词"], correct_args=None)
            ),
            ["typo", "2026-04-09", "错词", "正词"],
        )

    def test_dispatch_routes_through_handler_table(self):
        from openmy import skill_dispatch

        fake_payload = skill_dispatch.build_success_payload(
            action="status.get",
            data={"total_days": 1},
            human_summary="1 day of data available.",
        )
        with patch.dict(skill_dispatch.ACTION_HANDLERS, {"status.get": lambda _args: (fake_payload, 0)}, clear=False):
            payload, exit_code = skill_dispatch.dispatch_skill_action("status.get", self.make_args())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, fake_payload)

    def test_aggregate_routes_to_weekly_by_default(self):
        from openmy import skill_dispatch

        with patch.object(skill_dispatch, "handle_aggregate_weekly", return_value=({"ok": True}, 0)) as weekly_mock:
            payload, exit_code = skill_dispatch.dispatch_skill_action("aggregate", self.make_args(action="aggregate"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, {"ok": True})
        weekly_mock.assert_called_once()

    def test_aggregate_routes_to_monthly_when_month_is_present(self):
        from openmy import skill_dispatch

        with patch.object(skill_dispatch, "handle_aggregate_monthly", return_value=({"ok": True}, 0)) as monthly_mock:
            payload, exit_code = skill_dispatch.dispatch_skill_action(
                "aggregate",
                self.make_args(action="aggregate", month="2026-04"),
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, {"ok": True})
        monthly_mock.assert_called_once()

    def test_aggregate_rejects_conflicting_targets(self):
        from openmy import skill_dispatch

        payload, exit_code = skill_dispatch.dispatch_skill_action(
            "aggregate",
            self.make_args(action="aggregate", week="2026-W15", month="2026-04"),
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["error_code"], "conflicting_target")

    def test_day_run_bridges_existing_run_command(self):
        from openmy import skill_dispatch

        fake_status = {"status": "completed", "current_step": "briefing"}
        with (
            patch("openmy.skill_dispatch._run_existing_command", return_value=0) as run_mock,
            patch("openmy.skill_dispatch._day_run_status_path") as status_path_mock,
            patch("openmy.skill_dispatch._read_json", return_value=fake_status),
            patch("openmy.services.ingest.audio_pipeline.load_sidecar_transcript", return_value="已有侧车转写"),
        ):
            status_path_mock.return_value.exists.return_value = True
            payload, exit_code = skill_dispatch.dispatch_skill_action(
                "day.run",
                self.make_args(action="day.run", date="2026-04-10", audio=["a.wav"]),
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "day.run")
        run_mock.assert_called_once()

    def test_day_run_rejects_invalid_date_format(self):
        from openmy import skill_dispatch

        payload, exit_code = skill_dispatch.dispatch_skill_action(
            "day.run",
            self.make_args(action="day.run", date="../../etc"),
        )

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "invalid_date")

    def test_vocab_init_creates_files_from_example(self):

        from openmy import skill_dispatch
        from openmy.services.cleaning.cleaner import CORRECTIONS_FILE, VOCAB_FILE

        original_corrections = CORRECTIONS_FILE.read_text(encoding="utf-8") if CORRECTIONS_FILE.exists() else None
        original_vocab = VOCAB_FILE.read_text(encoding="utf-8") if VOCAB_FILE.exists() else None
        CORRECTIONS_FILE.unlink(missing_ok=True)
        VOCAB_FILE.unlink(missing_ok=True)

        try:
            payload, exit_code = skill_dispatch.dispatch_skill_action("vocab.init", self.make_args(action="vocab.init"))
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertIn("corrections.json", payload["data"]["created"])
            self.assertIn("vocab.txt", payload["data"]["created"])
            self.assertTrue(CORRECTIONS_FILE.exists())
            self.assertTrue(VOCAB_FILE.exists())
        finally:
            if original_corrections is None:
                CORRECTIONS_FILE.unlink(missing_ok=True)
            else:
                CORRECTIONS_FILE.write_text(original_corrections, encoding="utf-8")
            if original_vocab is None:
                VOCAB_FILE.unlink(missing_ok=True)
            else:
                VOCAB_FILE.write_text(original_vocab, encoding="utf-8")

    def test_profile_set_updates_fields(self):
        from openmy import skill_dispatch
        from openmy.services.context.consolidation import profile_path

        data_root = skill_dispatch._cli().DATA_ROOT
        path = profile_path(data_root)
        original = path.read_text(encoding="utf-8") if path.exists() else None

        try:
            args = self.make_args(action="profile.set", name="Alice", language="en-US", timezone="America/Los_Angeles")
            payload, exit_code = skill_dispatch.dispatch_skill_action("profile.set", args)
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["profile"]["name"], "Alice")
            self.assertEqual(payload["data"]["profile"]["language"], "en-US")
            self.assertEqual(payload["data"]["profile"]["timezone"], "America/Los_Angeles")

            payload, exit_code = skill_dispatch.dispatch_skill_action("profile.get", self.make_args(action="profile.get"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["data"]["profile"]["name"], "Alice")
        finally:
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(original, encoding="utf-8")

    def test_profile_set_accepts_stt_provider_and_syncs_env(self):
        from openmy import skill_dispatch

        env_path = skill_dispatch._cli().PROJECT_ENV_PATH
        original_env = env_path.read_text(encoding="utf-8") if env_path.exists() else None

        try:
            args = self.make_args(action="profile.set", stt_provider="funasr")
            payload, exit_code = skill_dispatch.dispatch_skill_action("profile.set", args)
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["stt_provider"], "funasr")
            self.assertIn("stt_provider", payload["data"]["updated_fields"])
            self.assertIn("OPENMY_STT_PROVIDER=funasr", env_path.read_text(encoding="utf-8"))
        finally:
            if original_env is None:
                env_path.unlink(missing_ok=True)
            else:
                env_path.write_text(original_env, encoding="utf-8")

    def test_profile_set_accepts_audio_source_and_syncs_env(self):
        from openmy import skill_dispatch
        from openmy.services.context.consolidation import profile_path

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            audio_source = Path(tmp_dir) / "audio"
            audio_source.mkdir(parents=True, exist_ok=True)
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("OPENMY_STT_PROVIDER=faster-whisper\n", encoding="utf-8")

            fake_cli = SimpleNamespace(DATA_ROOT=data_root, PROJECT_ENV_PATH=env_path)
            with patch("openmy.skill_dispatch._cli", return_value=fake_cli):
                args = self.make_args(action="profile.set", audio_source=str(audio_source))
                payload, exit_code = skill_dispatch.dispatch_skill_action("profile.set", args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["data"]["profile"]["audio_source_dir"], str(audio_source))
            self.assertIn("OPENMY_AUDIO_SOURCE_DIR=", env_path.read_text(encoding="utf-8"))
            saved = json.loads(profile_path(data_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["audio_source_dir"], str(audio_source))

    def test_profile_set_accepts_obsidian_export_and_syncs_env(self):
        from openmy import skill_dispatch

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            vault_path = Path(tmp_dir) / "vault"
            vault_path.mkdir(parents=True, exist_ok=True)
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")

            fake_cli = SimpleNamespace(DATA_ROOT=data_root, PROJECT_ENV_PATH=env_path)
            with patch("openmy.skill_dispatch._cli", return_value=fake_cli):
                args = self.make_args(
                    action="profile.set",
                    export_provider="obsidian",
                    export_path=str(vault_path),
                )
                payload, exit_code = skill_dispatch.dispatch_skill_action("profile.set", args)

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["export"]["provider"], "obsidian")
            self.assertEqual(payload["data"]["export"]["path"], str(vault_path))
            env_text = env_path.read_text(encoding="utf-8")
            self.assertIn("OPENMY_EXPORT_PROVIDER=obsidian", env_text)
            self.assertIn(f"OPENMY_OBSIDIAN_VAULT_PATH={vault_path}", env_text)

    def test_profile_set_auto_detects_obsidian_export_from_path(self):
        from openmy import skill_dispatch

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            vault_path = Path(tmp_dir) / "vault"
            vault_path.mkdir(parents=True, exist_ok=True)
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")

            fake_cli = SimpleNamespace(DATA_ROOT=data_root, PROJECT_ENV_PATH=env_path)
            with patch("openmy.skill_dispatch._cli", return_value=fake_cli):
                args = self.make_args(
                    action="profile.set",
                    export_path=str(vault_path),
                )
                payload, exit_code = skill_dispatch.dispatch_skill_action("profile.set", args)

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["export"]["provider"], "obsidian")
            self.assertIn("Auto-detected Obsidian export from --export-path.", payload["human_summary"])
            env_text = env_path.read_text(encoding="utf-8")
            self.assertIn("OPENMY_EXPORT_PROVIDER=obsidian", env_text)
            self.assertIn(f"OPENMY_OBSIDIAN_VAULT_PATH={vault_path}", env_text)

    def test_profile_set_accepts_screen_recognition_and_persists_settings(self):
        from openmy import skill_dispatch
        from openmy.services.screen_recognition.settings import load_screen_context_settings

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")

            fake_cli = SimpleNamespace(DATA_ROOT=data_root, PROJECT_ENV_PATH=env_path)
            with patch("openmy.skill_dispatch._cli", return_value=fake_cli):
                args = self.make_args(action="profile.set", screen_recognition="on")
                payload, exit_code = skill_dispatch.dispatch_skill_action("profile.set", args)

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["data"]["screen_recognition"]["enabled"])
            settings = load_screen_context_settings(data_root=data_root)
            self.assertTrue(settings.enabled)
            self.assertEqual(settings.participation_mode, "summary_only")
            self.assertIn("SCREEN_RECOGNITION_ENABLED=true", env_path.read_text(encoding="utf-8"))

    def test_latest_summary_stem_ignores_permission_errors(self):
        from openmy.skill_handlers.context_profile import _latest_summary_stem

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            summary_path = root / "weekly.json"
            summary_path.write_text("{}", encoding="utf-8")

            with patch("pathlib.Path.stat", side_effect=PermissionError):
                self.assertEqual(_latest_summary_stem(root), "")

    def test_day_run_uses_configured_audio_source_when_audio_missing(self):
        from openmy import skill_dispatch

        fake_status = {"status": "completed", "current_step": "briefing"}
        with (
            patch("openmy.skill_dispatch._run_existing_command", return_value=0) as run_mock,
            patch("openmy.skill_dispatch._day_run_status_path") as status_path_mock,
            patch("openmy.skill_dispatch._read_json", return_value=fake_status),
            patch("openmy.services.ingest.audio_pipeline.discover_configured_audio_files", return_value=["/tmp/today.wav"]),
            patch("openmy.services.ingest.audio_pipeline.load_sidecar_transcript", return_value="已有侧车转写"),
        ):
            status_path_mock.return_value.exists.return_value = True
            args = self.make_args(action="day.run", date="2099-02-10", audio=None)
            payload, exit_code = skill_dispatch.dispatch_skill_action("day.run", args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(args.audio, ["/tmp/today.wav"])
        self.assertTrue(payload["ok"])
        run_mock.assert_called_once()

    def test_health_check_masks_export_api_key(self):
        from openmy import skill_dispatch

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            profile_file = data_root / "profile.json"
            profile_file.write_text("{}", encoding="utf-8")
            corrections = data_root / "corrections.json"
            corrections.write_text("{}", encoding="utf-8")
            vocab = data_root / "vocab.txt"
            vocab.write_text("词汇", encoding="utf-8")

            fake_cli = SimpleNamespace(DATA_ROOT=data_root, find_all_dates=lambda: ["2026-04-10"])
            fake_screen_settings = SimpleNamespace(
                enabled=False,
                participation_mode="off",
                capture_interval_seconds=5,
                screenshot_retention_hours=24,
            )

            with (
                patch("openmy.skill_dispatch._cli", return_value=fake_cli),
                patch("openmy.config.get_export_provider_name", return_value="notion"),
                patch(
                    "openmy.config.get_export_config",
                    return_value={"api_key": "secret-token", "database_id": "db_123"},
                ),
                patch("openmy.config.get_llm_provider_name", return_value="gemini"),
                patch("openmy.config.has_llm_credentials", return_value=True),
                patch("openmy.config.get_stt_provider_name", return_value="faster-whisper"),
                patch("openmy.config.has_stt_credentials", return_value=True),
                patch("openmy.services.cleaning.cleaner.CORRECTIONS_FILE", corrections),
                patch("openmy.services.cleaning.cleaner.VOCAB_FILE", vocab),
                patch("openmy.services.context.consolidation.profile_path", return_value=profile_file),
                patch(
                    "openmy.services.screen_recognition.settings.load_screen_context_settings",
                    return_value=fake_screen_settings,
                ),
                patch("shutil.which", return_value="/usr/bin/fake"),
            ):
                payload, exit_code = skill_dispatch.handle_health_check(self.make_args(action="health.check"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["export"]["config"]["api_key"], "***")
        self.assertEqual(payload["data"]["export"]["config"]["database_id"], "db_123")
        self.assertTrue(payload["data"]["llm_available"])
        self.assertIn("onboarding", payload["data"])
        self.assertEqual(payload["data"]["onboarding"]["recommended_provider"], "faster-whisper")
        self.assertTrue(payload["data"]["onboarding"]["state_path"].endswith("onboarding_state.json"))
        self.assertIn("headline", payload["data"]["onboarding"])
        self.assertIn("choices", payload["data"]["onboarding"])
        self.assertEqual(payload["next_actions"][0], payload["data"]["onboarding"]["primary_action"])

    def test_health_check_requires_engine_choice_when_provider_missing(self):
        from openmy import skill_dispatch

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            fake_cli = SimpleNamespace(DATA_ROOT=data_root, find_all_dates=lambda: [])
            fake_screen_settings = SimpleNamespace(
                enabled=False,
                participation_mode="off",
                capture_interval_seconds=5,
                screenshot_retention_hours=24,
            )

            with (
                patch("openmy.skill_dispatch._cli", return_value=fake_cli),
                patch("openmy.config.get_export_provider_name", return_value=""),
                patch("openmy.config.get_export_config", return_value={}),
                patch("openmy.config.get_llm_provider_name", return_value="gemini"),
                patch("openmy.config.has_llm_credentials", return_value=False),
                patch("openmy.config.get_stt_provider_name", return_value=""),
                patch("openmy.config.has_stt_credentials", return_value=False),
                patch("openmy.providers.stt.funasr.AutoModel", object()),
                patch("openmy.providers.stt.faster_whisper.WhisperModel", object()),
                patch("openmy.services.screen_recognition.settings.load_screen_context_settings", return_value=fake_screen_settings),
                patch("shutil.which", return_value="/usr/bin/fake"),
            ):
                payload, exit_code = skill_dispatch.handle_health_check(self.make_args(action="health.check"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["stt_active"], "")
        self.assertIn("No STT provider selected yet.", payload["data"]["issues"][0])
        self.assertEqual(payload["next_actions"][0], payload["data"]["onboarding"]["primary_action"])
        self.assertEqual(payload["data"]["onboarding"]["stage"], "choose_provider")
        self.assertEqual(payload["data"]["onboarding"]["recommended_provider"], "funasr")
        self.assertIn("当前还没选转写引擎", payload["human_summary"])

    def test_health_check_marks_local_provider_unready_when_dependency_missing(self):
        from openmy import skill_dispatch

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            profile_file = data_root / "profile.json"
            profile_file.write_text("{}", encoding="utf-8")
            corrections = data_root / "corrections.json"
            corrections.write_text("{}", encoding="utf-8")
            vocab = data_root / "vocab.txt"
            vocab.write_text("词汇", encoding="utf-8")
            fake_cli = SimpleNamespace(DATA_ROOT=data_root, find_all_dates=lambda: [])
            fake_screen_settings = SimpleNamespace(
                enabled=False,
                participation_mode="off",
                capture_interval_seconds=5,
                screenshot_retention_hours=24,
            )

            with (
                patch("openmy.skill_dispatch._cli", return_value=fake_cli),
                patch("openmy.config.get_export_provider_name", return_value=""),
                patch("openmy.config.get_export_config", return_value={}),
                patch("openmy.config.get_llm_provider_name", return_value="gemini"),
                patch("openmy.config.has_llm_credentials", return_value=True),
                patch("openmy.config.get_stt_provider_name", return_value="funasr"),
                patch("openmy.config.has_stt_credentials", return_value=True),
                patch("openmy.providers.stt.funasr.AutoModel", None),
                patch("openmy.providers.stt.faster_whisper.WhisperModel", object()),
                patch("openmy.services.cleaning.cleaner.CORRECTIONS_FILE", corrections),
                patch("openmy.services.cleaning.cleaner.VOCAB_FILE", vocab),
                patch("openmy.services.context.consolidation.profile_path", return_value=profile_file),
                patch("openmy.services.screen_recognition.settings.load_screen_context_settings", return_value=fake_screen_settings),
                patch("shutil.which", return_value="/usr/bin/fake"),
            ):
                payload, exit_code = skill_dispatch.handle_health_check(self.make_args(action="health.check"))

        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["data"]["stt_configured"])
        provider = next(item for item in payload["data"]["stt_providers"] if item["name"] == "funasr")
        self.assertFalse(provider["ready"])
        self.assertIn("missing its local dependency", payload["data"]["issues"][0])
        self.assertEqual(payload["data"]["onboarding"]["stage"], "choose_provider")
        self.assertEqual(payload["data"]["onboarding"]["recommended_provider"], "faster-whisper")

    def test_distill_pending_and_submit_round_trip(self):
        from openmy import skill_dispatch

        date_str = "2099-03-01"
        day_dir = skill_dispatch._cli().ensure_day_dir(date_str)
        scenes_path = day_dir / "scenes.json"
        original = scenes_path.read_text(encoding="utf-8") if scenes_path.exists() else None
        scenes_path.write_text(
            """{
  "scenes": [
    {
      "scene_id": "s01",
      "time_start": "10:00",
      "text": "我今天把代理接手方案理顺了。",
      "summary": "",
      "role": {"addressed_to": "自己"},
      "screen_context": {"summary": "在看计划文档"}
    }
  ]
}""",
            encoding="utf-8",
        )

        try:
            pending_payload, exit_code = skill_dispatch.handle_distill_pending(
                self.make_args(action="distill.pending", date=date_str)
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(pending_payload["data"]["status"], "pending")
            self.assertEqual(len(pending_payload["data"]["pending_scenes"]), 1)

            submit_payload, submit_exit = skill_dispatch.handle_distill_submit(
                self.make_args(
                    action="distill.submit",
                    date=date_str,
                    payload_json='{"date":"2099-03-01","summaries":[{"scene_id":"s01","summary":"我把代理接手方案拆成了先蒸馏后提取。"}]}',
                )
            )
            self.assertEqual(submit_exit, 0)
            self.assertEqual(submit_payload["data"]["pending_count"], 0)
            saved = skill_dispatch._read_json(scenes_path, {})
            self.assertEqual(saved["scenes"][0]["summary"], "我把代理接手方案拆成了先蒸馏后提取。")
        finally:
            if original is None:
                scenes_path.unlink(missing_ok=True)
            else:
                scenes_path.write_text(original, encoding="utf-8")

    def test_extract_core_pending_and_submit_round_trip(self):
        from openmy import skill_dispatch

        date_str = "2099-03-02"
        day_dir = skill_dispatch._cli().ensure_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        scenes_path = day_dir / "scenes.json"
        meta_path = day_dir / f"{date_str}.meta.json"
        original_transcript = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else None
        original_scenes = scenes_path.read_text(encoding="utf-8") if scenes_path.exists() else None
        original_meta = meta_path.read_text(encoding="utf-8") if meta_path.exists() else None
        transcript_path.write_text("## 10:00\n\n昨天把旧问题修好了，明天下午继续验收。", encoding="utf-8")
        scenes_path.write_text(
            """{
  "scenes": [
    {
      "scene_id": "s01",
      "time_start": "10:00",
      "summary": "我昨天把旧问题修好了，明天下午继续验收。",
      "preview": "昨天把旧问题修好了",
      "screen_context": {"summary": "在看返工计划"}
    }
  ]
}""",
            encoding="utf-8",
        )
        meta_path.unlink(missing_ok=True)

        try:
            pending_payload, exit_code = skill_dispatch.handle_extract_core_pending(
                self.make_args(action="extract.core.pending", date=date_str)
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(pending_payload["data"]["status"], "pending")
            self.assertIn("output_schema", pending_payload["data"])

            submit_payload, submit_exit = skill_dispatch.handle_extract_core_submit(
                self.make_args(
                    action="extract.core.submit",
                    date=date_str,
                    payload_json=(
                        '{"daily_summary":"我昨天修完了旧问题，明天下午继续验收。",'
                        '"intents":[{"intent_id":"i1","kind":"action_item","what":"明天下午继续验收","status":"open","who":{"kind":"user"},"confidence_label":"high"}],'
                        '"facts":[{"fact_id":"f1","fact_type":"progress","content":"昨天把旧问题修好了","confidence_label":"high"}]}'
                    ),
                )
            )
            self.assertEqual(submit_exit, 0)
            self.assertEqual(submit_payload["data"]["extract_enrich_status"], "pending")
            saved_meta = skill_dispatch._read_json(meta_path, {})
            self.assertEqual(saved_meta["extract_enrich_status"], "pending")
            self.assertEqual(saved_meta["daily_summary"], "我昨天修完了旧问题，明天下午继续验收。")
        finally:
            if original_transcript is None:
                transcript_path.unlink(missing_ok=True)
            else:
                transcript_path.write_text(original_transcript, encoding="utf-8")
            if original_scenes is None:
                scenes_path.unlink(missing_ok=True)
            else:
                scenes_path.write_text(original_scenes, encoding="utf-8")
            if original_meta is None:
                meta_path.unlink(missing_ok=True)
            else:
                meta_path.write_text(original_meta, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
