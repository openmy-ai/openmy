#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from openmy.services import notify


class TestNotify(unittest.TestCase):
    def test_completion_message_full(self):
        title, msg = notify.build_completion_message(
            "2026-06-29", {"voice_hours": 2.34, "key_events": [1, 2, 3]}
        )
        self.assertEqual(title, "OpenMy")
        self.assertEqual(msg, "2026-06-29 2.3 小时录音整理好了，3 件事值得看")

    def test_completion_message_no_events(self):
        _, msg = notify.build_completion_message(
            "2026-06-29", {"voice_hours": 2.34, "key_events": []}
        )
        self.assertEqual(msg, "2026-06-29 2.3 小时录音整理好了")

    def test_completion_message_empty_briefing(self):
        _, msg = notify.build_completion_message("2026-06-29", None)
        self.assertEqual(msg, "2026-06-29 录音整理好了")

    def test_voice_hours_below_threshold_dropped(self):
        _, msg = notify.build_completion_message(
            "2026-06-29", {"voice_hours": 0.01, "key_events": [1]}
        )
        self.assertEqual(msg, "2026-06-29 录音整理好了，1 件事值得看")

    def test_voice_hours_non_numeric(self):
        self.assertIsNone(notify._voice_hours({"voice_hours": "oops"}))
        self.assertIsNone(notify._voice_hours({}))

    def test_worth_looking_count_handles_bad_types(self):
        self.assertEqual(notify._worth_looking_count({"key_events": None}), 0)
        self.assertEqual(notify._worth_looking_count({"key_events": "x"}), 0)
        self.assertEqual(notify._worth_looking_count(None), 0)

    def test_escape(self):
        self.assertEqual(notify._escape('a "b" c'), 'a \\"b\\" c')
        self.assertEqual(notify._escape("a\\b"), "a\\\\b")

    def test_start_and_error_messages(self):
        self.assertEqual(
            notify.build_start_message("2026-06-29", 3),
            ("OpenMy", "检测到 DJI Mic，3 段新录音正在整理…"),
        )
        self.assertEqual(
            notify.build_error_message("2026-06-29", "坏了"),
            ("OpenMy", "2026-06-29 处理出错：坏了"),
        )

    def test_send_notification_returns_false_off_macos(self):
        with patch.object(notify.platform, "system", return_value="Linux"):
            self.assertFalse(notify.send_notification("t", "m"))

    def test_send_notification_swallows_errors(self):
        with patch.object(notify.platform, "system", return_value="Darwin"), patch.object(
            notify.subprocess, "run", side_effect=OSError("boom")
        ):
            self.assertFalse(notify.send_notification("t", "m"))


if __name__ == "__main__":
    unittest.main()
