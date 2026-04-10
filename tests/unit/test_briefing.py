#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock

from openmy.services.briefing.generator import (
    DailyBriefing,
    _time_to_period,
    generate_briefing,
    save_briefing,
)


class TestTimeToPeriod(unittest.TestCase):
    def test_morning(self):
        self.assertEqual(_time_to_period("09:30"), "上午")

    def test_afternoon(self):
        self.assertEqual(_time_to_period("14:00"), "下午")

    def test_night(self):
        self.assertEqual(_time_to_period("21:00"), "晚上")

    def test_invalid(self):
        self.assertEqual(_time_to_period(""), "其他")


class TestGenerateBriefing(unittest.TestCase):
    def test_no_scenes_file(self):
        briefing = generate_briefing(Path("/nonexistent/scenes.json"), "2026-04-07")
        self.assertIn("没有语音数据", briefing.summary)

    def test_basic_scenes(self):
        scenes = {
            "scenes": [
                {
                    "time_start": "12:00",
                    "time_end": "12:10",
                    "text": "今天中午吃什么",
                    "summary": "讨论午饭",
                    "role": {"addressed_to": "老婆", "scene_type": "interpersonal"},
                },
                {
                    "time_start": "14:00",
                    "time_end": "14:30",
                    "text": "帮我改一下这个代码",
                    "summary": "改代码",
                    "role": {"addressed_to": "AI助手", "scene_type": "ai"},
                },
            ],
            "stats": {},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(scenes, fh, ensure_ascii=False)
            tmp_path = Path(fh.name)

        try:
            briefing = generate_briefing(tmp_path, "2026-04-07")
            self.assertEqual(briefing.total_scenes, 2)
            self.assertIn("老婆", briefing.people_interaction_map)
            self.assertIn("AI助手", briefing.people_interaction_map)
            self.assertEqual(len(briefing.time_blocks), 2)
        finally:
            os.unlink(tmp_path)

    def test_briefing_serializable(self):
        briefing = DailyBriefing(date="2026-04-07")
        data = asdict(briefing)
        json_str = json.dumps(data, ensure_ascii=False)
        self.assertIn("2026-04-07", json_str)

    def test_screenpipe_unavailable_still_works(self):
        scenes = {"scenes": [{"time_start": "10:00", "text": "test", "role": {}}], "stats": {}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(scenes, fh)
            tmp_path = Path(fh.name)

        try:
            mock_client = MagicMock()
            mock_client.is_available.return_value = False
            briefing = generate_briefing(tmp_path, "2026-04-07", mock_client)
            self.assertFalse(briefing.screen_recognition_available)
            self.assertEqual(briefing.total_scenes, 1)
        finally:
            os.unlink(tmp_path)


class TestSaveBriefing(unittest.TestCase):
    def test_save_briefing_writes_json(self):
        briefing = DailyBriefing(date="2026-04-07", summary="测试摘要")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            output_path = Path(fh.name)

        try:
            save_briefing(briefing, output_path)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["date"], "2026-04-07")
            self.assertEqual(data["summary"], "测试摘要")
        finally:
            output_path.unlink(missing_ok=True)


class TestBriefingCli(unittest.TestCase):
    def test_module_runs_from_repo_root(self):
        project_root = Path(__file__).resolve().parents[2]
        date_str = "2099-01-01"
        output_dir = project_root / "data" / date_str

        try:
            result = subprocess.run(
                [sys.executable, "-m", "openmy.services.briefing", date_str],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output_dir / "daily_briefing.json").exists())
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
