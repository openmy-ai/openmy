#!/usr/bin/env python3
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestDayTapeCli(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
