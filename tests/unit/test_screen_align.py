#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from openmy.domain.models import SceneBlock, ScreenSession
from openmy.services.screen_recognition.align import align_scene_sessions


class TestScreenAlign(unittest.TestCase):
    def test_aligns_overlapping_sessions_to_scene(self):
        scene = SceneBlock(scene_id="scene_001", time_start="10:00", time_end="10:05", text="这个我待会儿弄")
        sessions = [
            ScreenSession(
                app_name="Cursor",
                window_name="OpenMy - enrich.py",
                start_time="2026-04-10T10:00:30+08:00",
                end_time="2026-04-10T10:04:00+08:00",
            ),
            ScreenSession(
                app_name="微信",
                window_name="和老板聊天",
                start_time="2026-04-10T10:10:00+08:00",
                end_time="2026-04-10T10:12:00+08:00",
            ),
        ]

        with patch("openmy.utils.time.get_user_timezone", return_value="Asia/Shanghai"):
            aligned = align_scene_sessions(scene, sessions, "2026-04-10")

        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0].app_name, "Cursor")

    def test_returns_empty_when_no_overlap(self):
        scene = SceneBlock(scene_id="scene_002", time_start="09:00", time_end="09:05", text="test")
        sessions = [
            ScreenSession(
                app_name="微信",
                window_name="聊天",
                start_time="2026-04-10T10:00:00+08:00",
                end_time="2026-04-10T10:05:00+08:00",
            )
        ]

        with patch("openmy.utils.time.get_user_timezone", return_value="Asia/Shanghai"):
            self.assertEqual(align_scene_sessions(scene, sessions, "2026-04-10"), [])


if __name__ == "__main__":
    unittest.main()
