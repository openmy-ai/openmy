#!/usr/bin/env python3

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import openmy.commands.common as common_cmd
import openmy.commands.show as show_cmd
from openmy.commands import run as run_command


class TestRunAggregation(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def make_cli_stub(self, project_root: Path, data_root: Path, fake_briefing):
        return SimpleNamespace(
            ROOT_DIR=project_root,
            DATA_ROOT=data_root,
            ensure_day_dir=show_cmd.ensure_day_dir,
            resolve_day_paths=show_cmd.resolve_day_paths,
            read_json=show_cmd.read_json,
            write_json=common_cmd.write_json,
            freeze_scene_roles=show_cmd.freeze_scene_roles,
            cmd_briefing=fake_briefing,
            console=SimpleNamespace(print=lambda *args, **kwargs: None),
            Panel=lambda content, **kwargs: content,
        )

    def test_cmd_run_triggers_weekly_aggregation_on_seventh_briefing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            for date_str in ["2026-04-06", "2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10", "2026-04-11"]:
                self.write_json(data_root / date_str / "daily_briefing.json", {"summary": f"{date_str} briefing"})

            target_date = "2026-04-12"
            day_dir = data_root / target_date
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / "transcript.md").write_text("# 2026-04-12\n", encoding="utf-8")
            self.write_json(
                day_dir / "scenes.json",
                {"scenes": [{"scene_id": "s01", "summary": "done", "preview": "x", "role": {}}], "stats": {}},
            )
            self.write_json(day_dir / f"{target_date}.meta.json", {"daily_summary": "done", "intents": [], "facts": []})

            def fake_briefing(_args):
                self.write_json(day_dir / "daily_briefing.json", {"summary": "today"})
                return 0

            with (
                patch("openmy.commands.show.DATA_ROOT", data_root),
                patch("openmy.commands.show.LEGACY_ROOT", project_root),
                patch("openmy.services.context.consolidation.consolidate", return_value={}),
                patch("openmy.services.aggregation.generate_weekly_review") as weekly_mock,
                patch("openmy.services.aggregation.generate_monthly_review") as monthly_mock,
                patch.object(common_cmd, "ROOT_DIR", project_root),
                patch.object(common_cmd, "DATA_ROOT", data_root),
            ):
                cli_stub = self.make_cli_stub(project_root, data_root, fake_briefing)
                with patch.object(run_command, "_cli", return_value=cli_stub):
                    result = run_command.cmd_run(argparse.Namespace(date=target_date, audio=[], skip_transcribe=True, skip_aggregate=False))

            self.assertEqual(result, 0)
            weekly_mock.assert_called_once()
            monthly_mock.assert_not_called()
            status_payload = json.loads((day_dir / "run_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["steps"]["aggregate"]["status"], "completed")

    def test_cmd_run_triggers_monthly_aggregation_in_last_week_of_month(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            for date_str in ["2026-04-27", "2026-04-28", "2026-04-29"]:
                self.write_json(data_root / date_str / "daily_briefing.json", {"summary": f"{date_str} briefing"})

            target_date = "2026-04-30"
            day_dir = data_root / target_date
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / "transcript.md").write_text("# 2026-04-30\n", encoding="utf-8")
            self.write_json(
                day_dir / "scenes.json",
                {"scenes": [{"scene_id": "s01", "summary": "done", "preview": "x", "role": {}}], "stats": {}},
            )
            self.write_json(day_dir / f"{target_date}.meta.json", {"daily_summary": "done", "intents": [], "facts": []})

            def fake_briefing(_args):
                self.write_json(day_dir / "daily_briefing.json", {"summary": "today"})
                return 0

            with (
                patch("openmy.commands.show.DATA_ROOT", data_root),
                patch("openmy.commands.show.LEGACY_ROOT", project_root),
                patch("openmy.services.context.consolidation.consolidate", return_value={}),
                patch("openmy.services.aggregation.generate_weekly_review") as weekly_mock,
                patch("openmy.services.aggregation.generate_monthly_review") as monthly_mock,
                patch.object(common_cmd, "ROOT_DIR", project_root),
                patch.object(common_cmd, "DATA_ROOT", data_root),
            ):
                cli_stub = self.make_cli_stub(project_root, data_root, fake_briefing)
                with patch.object(run_command, "_cli", return_value=cli_stub):
                    result = run_command.cmd_run(argparse.Namespace(date=target_date, audio=[], skip_transcribe=True, skip_aggregate=False))

            self.assertEqual(result, 0)
            weekly_mock.assert_not_called()
            monthly_mock.assert_called_once()

    def test_cmd_run_keeps_success_when_aggregation_fails(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            target_date = "2026-04-12"
            day_dir = data_root / target_date
            (day_dir / "transcript.md").parent.mkdir(parents=True, exist_ok=True)
            (day_dir / "transcript.md").write_text("# 2026-04-12\n", encoding="utf-8")
            self.write_json(day_dir / "scenes.json", {"scenes": [{"scene_id": "s01", "summary": "done", "preview": "x", "role": {}}], "stats": {}})
            self.write_json(day_dir / f"{target_date}.meta.json", {"daily_summary": "done", "intents": [], "facts": []})

            def fake_briefing(_args):
                self.write_json(day_dir / "daily_briefing.json", {"summary": "today"})
                return 0

            with (
                patch("openmy.commands.show.DATA_ROOT", data_root),
                patch("openmy.commands.show.LEGACY_ROOT", project_root),
                patch("openmy.services.context.consolidation.consolidate", return_value={}),
                patch("openmy.services.aggregation.generate_weekly_review", side_effect=RuntimeError("boom")),
                patch.object(common_cmd, "ROOT_DIR", project_root),
                patch.object(common_cmd, "DATA_ROOT", data_root),
            ):
                cli_stub = self.make_cli_stub(project_root, data_root, fake_briefing)
                with patch.object(run_command, "_cli", return_value=cli_stub):
                    result = run_command.cmd_run(argparse.Namespace(date=target_date, audio=[], skip_transcribe=True, skip_aggregate=False))

            self.assertEqual(result, 0)
            status_payload = json.loads((day_dir / "run_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["status"], "completed")
            self.assertEqual(status_payload["steps"]["aggregate"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
