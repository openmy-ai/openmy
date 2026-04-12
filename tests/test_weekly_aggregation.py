#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path

from openmy.services.aggregation.weekly import generate_weekly_review


class TestWeeklyAggregation(unittest.TestCase):
    def write_briefing(self, data_root: Path, date_str: str, payload: dict) -> None:
        day_dir = data_root / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "daily_briefing.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_generate_weekly_review_with_seven_days(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            for idx, date_str in enumerate(["2026-04-06", "2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10", "2026-04-11", "2026-04-12"]):
                self.write_briefing(
                    data_root,
                    date_str,
                    {
                        "summary": f"第 {idx + 1} 天主要推进 OpenMy。",
                        "key_events": ["OpenMy：补日报", "OpenMy：补日报", f"事件 {idx + 1}"],
                        "decisions": ["先做 click"],
                        "todos_open": ["查错词", "查错词"],
                        "insights": ["转写误差会带偏意思"],
                    },
                )

            payload = generate_weekly_review(data_root, "2026-W15")

            self.assertEqual(payload["week"], "2026-W15")
            self.assertEqual(payload["date_range"], "2026-04-06 ~ 2026-04-12")
            self.assertTrue(payload["summary"])
            self.assertIn("OpenMy", payload["projects"])
            self.assertEqual(payload["wins"].count("OpenMy：补日报"), 1)
            self.assertEqual(payload["open_items"], ["查错词"])
            self.assertEqual(payload["decisions"], ["先做 click"])
            self.assertTrue((data_root / "weekly" / "2026-W15.json").exists())

    def test_generate_weekly_review_skips_missing_days(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            for date_str in ["2026-04-06", "2026-04-08", "2026-04-10"]:
                self.write_briefing(
                    data_root,
                    date_str,
                    {
                        "summary": "主要推进 OpenMy。",
                        "key_events": ["OpenMy：补日报"],
                        "decisions": [],
                        "todos_open": ["补测试"],
                        "insights": [],
                    },
                )

            payload = generate_weekly_review(data_root, "2026-W15")

            self.assertEqual(payload["week"], "2026-W15")
            self.assertEqual(payload["open_items"], ["补测试"])
            self.assertTrue(payload["summary"])

    def test_generate_weekly_review_with_zero_days(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"

            payload = generate_weekly_review(data_root, "2026-W15")

            self.assertEqual(
                payload,
                {
                    "week": "2026-W15",
                    "date_range": "2026-04-06 ~ 2026-04-12",
                    "summary": "",
                    "projects": [],
                    "wins": [],
                    "challenges": [],
                    "open_items": [],
                    "decisions": [],
                    "next_week_focus": "",
                },
            )


if __name__ == "__main__":
    unittest.main()
