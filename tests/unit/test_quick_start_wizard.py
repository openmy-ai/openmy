#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestQuickStartWizard(unittest.TestCase):
    def test_wizard_accepts_demo_and_writes_provider(self):
        from openmy.commands import run

        with tempfile.TemporaryDirectory() as temp_dir:
            env_updates: dict[str, str] = {}
            fake_cli = SimpleNamespace(
                DATA_ROOT=Path(temp_dir),
                _upsert_project_env=lambda key, value: env_updates.__setitem__(key, value),
                infer_date_from_path=lambda _path: "2099-12-31",
            )
            with (
                patch("openmy.commands.run._cli", return_value=fake_cli),
                patch("openmy.commands.run.get_stt_provider_name", return_value=""),
                patch("openmy.commands.run.get_stt_api_key", return_value=""),
                patch("openmy.commands.run.select_option", side_effect=[0, 0]),
                patch("openmy.commands.run.prompt_input", side_effect=["demo-key", "demo"]),
            ):
                result = run._run_quick_start_wizard()

        self.assertEqual(result["provider_name"], "gemini")
        self.assertTrue(result["use_demo"])
        self.assertIsNone(result["audio_path"])
        self.assertEqual(env_updates["OPENMY_STT_PROVIDER"], "gemini")
        self.assertEqual(env_updates["GEMINI_API_KEY"], "demo-key")

    def test_wizard_accepts_local_audio_file(self):
        from openmy.commands import run

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "meeting-2026-04-12.wav"
            audio_path.write_bytes(b"wav")
            env_updates: dict[str, str] = {}
            fake_cli = SimpleNamespace(
                DATA_ROOT=Path(temp_dir),
                _upsert_project_env=lambda key, value: env_updates.__setitem__(key, value),
                infer_date_from_path=lambda _path: "2026-04-12",
            )
            with (
                patch("openmy.commands.run._cli", return_value=fake_cli),
                patch("openmy.commands.run.get_stt_provider_name", return_value=""),
                patch("openmy.commands.run.get_stt_api_key", return_value=""),
                patch("openmy.commands.run.select_option", side_effect=[2, 0]),
                patch("openmy.commands.run.prompt_input", side_effect=[str(audio_path)]),
            ):
                result = run._run_quick_start_wizard()

        self.assertEqual(result["provider_name"], "funasr")
        self.assertFalse(result["use_demo"])
        self.assertEqual(result["audio_path"], audio_path)
        self.assertEqual(env_updates["OPENMY_STT_PROVIDER"], "funasr")

    def test_cli_quick_start_without_args_uses_wizard_result(self):
        import openmy.cli as cli

        audio_path = PROJECT_ROOT / "tests" / "fixtures" / "wizard-2026-04-12.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"wav")
        parser = cli.build_parser()
        args = parser.parse_args(["quick-start"])

        with (
            patch("openmy.commands.run._run_quick_start_wizard", return_value={
                "provider_name": "funasr",
                "audio_path": audio_path,
                "use_demo": False,
            }),
            patch("openmy.cli.cmd_run", return_value=0) as run_mock,
            patch("openmy.cli.ensure_runtime_dependencies", return_value=None),
            patch("openmy.cli.launch_local_report", return_value=None),
        ):
            result = cli.main_with_args(args)

        self.assertEqual(result, 0)
        forwarded_args = run_mock.call_args.args[0]
        self.assertEqual(forwarded_args.stt_provider, "funasr")
        self.assertEqual(forwarded_args.audio, [str(audio_path)])
        audio_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
