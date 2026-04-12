#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path

from openmy.services.aggregation.monthly import generate_monthly_review


class TestMonthlyAggregation(unittest.TestCase):
    def write_weekly(self, data_root: Path, week_str: str, payload: dict) -> None:
        weekly_dir = data_root / "weekly"
        weekly_dir.mkdir(parents=True, exist_ok=True)
        (weekly_dir / f"{week_str}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_generate_monthly_review_with_four_weeks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            for week_str in ["2026-W14", "2026-W15", "2026-W16", "2026-W17"]:
                self.write_weekly(
                    data_root,
                    week_str,
                    {
                        "week": week_str,
                        "summary": f"{week_str} 主要推进 OpenMy。",
                        "projects": ["OpenMy", "OpenMy"],
                        "decisions": ["先做 click"],
                        "open_items": ["补测试"],
                    },
                )

            payload = generate_monthly_review(data_root, "2026-04")

            self.assertEqual(payload["month"], "2026-04")
            self.assertIn("OpenMy", payload["projects"])
            self.assertEqual(payload["key_decisions"], ["先做 click"])
            self.assertEqual(payload["open_items"], ["补测试"])
            self.assertTrue(payload["summary"])
            self.assertTrue((data_root / "monthly" / "2026-04.json").exists())

    def test_generate_monthly_review_with_one_week(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            self.write_weekly(
                data_root,
                "2026-W14",
                {
                    "week": "2026-W14",
                    "summary": "这周主要推进 OpenMy。",
                    "projects": ["OpenMy"],
                    "decisions": [],
                    "open_items": ["查浏览器"],
                },
            )

            payload = generate_monthly_review(data_root, "2026-04")

            self.assertEqual(payload["projects"], ["OpenMy"])
            self.assertEqual(payload["open_items"], ["查浏览器"])

    def test_generate_monthly_review_with_zero_weeks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"

            payload = generate_monthly_review(data_root, "2026-04")

            self.assertEqual(
                payload,
                {
                    "month": "2026-04",
                    "summary": "",
                    "projects": [],
                    "key_decisions": [],
                    "open_items": [],
                    "direction": "",
                },
            )


if __name__ == "__main__":
    unittest.main()
