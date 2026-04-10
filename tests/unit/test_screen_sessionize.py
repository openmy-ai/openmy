#!/usr/bin/env python3
import unittest

from openmy.adapters.screen_recognition.client import ScreenEvent
from openmy.services.screen_recognition.sessionize import sessionize_screen_events


class TestScreenSessionize(unittest.TestCase):
    def test_groups_same_window_with_short_gap(self):
        events = [
            ScreenEvent(
                app_name="Cursor",
                window_name="OpenMy - provider.py",
                timestamp="2026-04-10T10:00:00+08:00",
                frame_id=1,
                text="修改 provider.py",
                url="https://github.com/openmy/openmy/pull/1",
            ),
            ScreenEvent(
                app_name="Cursor",
                window_name="OpenMy - provider.py",
                timestamp="2026-04-10T10:00:08+08:00",
                frame_id=2,
                text="继续修改 provider.py",
                url="https://github.com/openmy/openmy/pull/1",
            ),
        ]

        sessions = sessionize_screen_events(events, gap_seconds=15)

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].app_name, "Cursor")
        self.assertEqual(sessions[0].frame_ids, [1, 2])
        self.assertEqual(sessions[0].url_domain, "github.com")
        self.assertIn("provider.py", sessions[0].text)

    def test_splits_when_gap_too_large_or_window_changes(self):
        events = [
            ScreenEvent(
                app_name="Google Chrome",
                window_name="淘宝退款页",
                timestamp="2026-04-10T11:00:00+08:00",
                frame_id=11,
                text="退款申请",
                url="https://refund.taobao.com",
            ),
            ScreenEvent(
                app_name="Google Chrome",
                window_name="淘宝退款页",
                timestamp="2026-04-10T11:01:10+08:00",
                frame_id=12,
                text="退款申请处理中",
                url="https://refund.taobao.com",
            ),
            ScreenEvent(
                app_name="微信",
                window_name="和商家聊天",
                timestamp="2026-04-10T11:01:20+08:00",
                frame_id=13,
                text="请尽快处理售后",
            ),
        ]

        sessions = sessionize_screen_events(events, gap_seconds=15)

        self.assertEqual(len(sessions), 3)
        self.assertEqual(sessions[0].app_name, "Google Chrome")
        self.assertEqual(sessions[1].app_name, "Google Chrome")
        self.assertEqual(sessions[2].app_name, "微信")


if __name__ == "__main__":
    unittest.main()
