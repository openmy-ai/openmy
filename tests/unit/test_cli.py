#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestDayTapeCli(unittest.TestCase):
    def make_day_dir(self, date_str: str) -> Path:
        day_dir = PROJECT_ROOT / "data" / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def cleanup_day_dir(self, date_str: str) -> None:
        shutil.rmtree(PROJECT_ROOT / "data" / date_str, ignore_errors=True)

    def test_cli_status_runs(self):
        """daytape status 应该能跑通不报错。"""
        result = subprocess.run(
            [sys.executable, "-m", "daytape", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue("日期" in result.stdout or "📅" in result.stdout)

    def test_cli_help(self):
        """daytape --help 应该输出帮助。"""
        result = subprocess.run(
            [sys.executable, "-m", "daytape", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue("daytape" in result.stdout.lower() or "DayTape" in result.stdout)

    def test_cli_view_existing_date(self):
        """daytape view 2026-04-06 应该输出场景概览。"""
        result = subprocess.run(
            [sys.executable, "-m", "daytape", "view", "2026-04-06"],
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
            [sys.executable, "-m", "daytape", "view", "1999-01-01"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_cli_roles_nonexistent_date(self):
        """没有清洗文本时，roles 应该友好报错。"""
        result = subprocess.run(
            [sys.executable, "-m", "daytape", "roles", "1999-01-01"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_cli_briefing_generates_output(self):
        """daytape briefing 应该生成日报文件。"""
        date_str = "2099-01-02"
        output_dir = self.make_day_dir(date_str)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "daytape", "briefing", date_str],
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
        """daytape clean 应该从 raw 生成 transcript.md。"""
        date_str = "2099-01-03"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.raw.md").write_text(
            "# 2099-01-03 原始\n\n---\n\n## 10:00\n\n嗯\n老婆，今天去散步。",
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "daytape", "clean", date_str],
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
        """daytape roles 应该从 transcript 生成 scenes.json。"""
        date_str = "2099-01-04"
        day_dir = self.make_day_dir(date_str)
        (day_dir / "transcript.md").write_text(
            "# 2099-01-04\n\n---\n\n## 10:00\n\n老婆，晚上一起吃饭。\n\n## 11:00\n\nClaude 帮我看一下代码。",
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "daytape", "roles", date_str],
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
        """daytape distill 没有 GEMINI_API_KEY 时应该友好报错。"""
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
                [sys.executable, "-m", "daytape", "distill", date_str],
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
        """daytape correct 应该更新 transcript 并同步纠错词典。"""
        date_str = "2099-01-06"
        day_dir = self.make_day_dir(date_str)
        transcript_path = day_dir / "transcript.md"
        transcript_path.write_text("## 10:00\n\n青维今天去散步。", encoding="utf-8")

        corrections_path = PROJECT_ROOT / "src" / "daytape" / "resources" / "corrections.json"
        vocab_path = PROJECT_ROOT / "src" / "daytape" / "resources" / "vocab.txt"
        original_corrections = corrections_path.read_text(encoding="utf-8")
        original_vocab = vocab_path.read_text(encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "daytape", "correct", date_str, "青维", "青梅"],
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

    def test_cli_run_reuses_existing_artifacts(self):
        """daytape run --skip-transcribe 应该能复用已有 transcript/scenes 生成 briefing。"""
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
                [sys.executable, "-m", "daytape", "run", date_str, "--skip-transcribe"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((day_dir / "daily_briefing.json").exists())
        finally:
            self.cleanup_day_dir(date_str)


if __name__ == "__main__":
    unittest.main()
