#!/usr/bin/env python3
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestFeedbackService(unittest.TestCase):
    def test_set_feedback_opt_in_and_record_success(self):
        from openmy.services import feedback

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / ".openmy"
            feedback.set_feedback_opt_in(True, root=root)
            telemetry = feedback.record_processing_success("funasr", root=root, when="2026-04-14T10:00:00+08:00")

            settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
            saved_telemetry = json.loads((root / "telemetry.json").read_text(encoding="utf-8"))

        self.assertTrue(settings["feedback_opt_in"])
        self.assertEqual(telemetry["stt_provider"], "funasr")
        self.assertEqual(saved_telemetry["stt_provider"], "funasr")
        self.assertIn("tthw_seconds", saved_telemetry)


class TestFeedbackCli(unittest.TestCase):
    def test_feedback_opt_in_command_creates_local_files(self):
        import openmy.cli as cli

        with tempfile.TemporaryDirectory() as tmp_home:
            parser = cli.build_parser()
            args = parser.parse_args(["feedback", "--opt-in"])
            with patch.dict(os.environ, {"HOME": tmp_home}, clear=False):
                result = cli.main_with_args(args)

            self.assertEqual(result, 0)
            self.assertTrue((Path(tmp_home) / ".openmy" / "settings.json").exists())
            self.assertTrue((Path(tmp_home) / ".openmy" / "telemetry.json").exists())

    def test_feedback_show_command_reads_local_data(self):
        import openmy.cli as cli
        from openmy.services.feedback import save_settings, save_telemetry

        with tempfile.TemporaryDirectory() as tmp_home:
            root = Path(tmp_home) / ".openmy"
            save_settings(
                {
                    "feedback_opt_in": True,
                    "opted_in_at": "2026-04-14T09:00:00+08:00",
                    "first_install_time": "2026-04-14T09:00:00+08:00",
                },
                root=root,
            )
            save_telemetry(
                {
                    "first_install_time": "2026-04-14T09:00:00+08:00",
                    "first_successful_processing_time": "2026-04-14T09:30:00+08:00",
                    "tthw_seconds": 1800,
                    "stt_provider": "funasr",
                    "os": "Darwin",
                },
                root=root,
            )

            parser = cli.build_parser()
            args = parser.parse_args(["feedback", "--show"])
            output = io.StringIO()
            with patch.dict(os.environ, {"HOME": tmp_home}, clear=False), patch.object(cli, "console") as fake_console, patch.object(cli, "Panel", side_effect=lambda content, **kwargs: content):
                fake_console.print.side_effect = lambda *items, **kwargs: output.write(" ".join(str(item) for item in items))
                result = cli.main_with_args(args)

            self.assertEqual(result, 0)
            self.assertIn("1800", output.getvalue())


if __name__ == "__main__":
    unittest.main()
