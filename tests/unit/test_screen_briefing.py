#!/usr/bin/env python3
import json
import os
import tempfile
import unittest
from pathlib import Path

from openmy.services.briefing.generator import generate_briefing


class TestScreenBriefing(unittest.TestCase):
    def test_briefing_surfaces_screen_context_not_just_app_usage(self):
        scenes = {
            "scenes": [
                {
                    "scene_id": "scene_001",
                    "time_start": "10:00",
                    "time_end": "10:10",
                    "text": "这个我待会儿弄",
                    "summary": "准备继续推进屏幕上下文主链",
                    "role": {"addressed_to": "自己", "scene_type": "self"},
                    "screen_context": {
                        "summary": "当时正在 Cursor 修改 OpenMy 的屏幕上下文主链",
                        "primary_app": "Cursor",
                        "primary_domain": "github.com",
                        "tags": ["development"],
                        "completion_candidates": [
                            {"kind": "saved", "label": "保存成功", "confidence": 0.9, "evidence": "保存成功"}
                        ],
                    },
                }
            ],
            "stats": {},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(scenes, fh, ensure_ascii=False)
            tmp_path = Path(fh.name)

        try:
            briefing = generate_briefing(tmp_path, "2026-04-10")
        finally:
            os.unlink(tmp_path)

        self.assertTrue(briefing.screen_highlights)
        self.assertIn("OpenMy", briefing.screen_highlights[0])
        self.assertTrue(briefing.completion_candidates)
        self.assertIn("屏幕", briefing.summary)

    def test_briefing_respects_screen_context_off_mode(self):
        scenes = {
            "scenes": [
                {
                    "scene_id": "scene_001",
                    "time_start": "10:00",
                    "time_end": "10:10",
                    "text": "这个我待会儿弄",
                    "summary": "准备继续推进主链",
                    "role": {"addressed_to": "自己", "scene_type": "self"},
                }
            ],
            "stats": {},
        }

        class StubScreenClient:
            def __init__(self):
                self.search_calls = 0
                self.summary_calls = 0

            def is_available(self):
                return True

            def search_ocr(self, **_kwargs):
                self.search_calls += 1
                return []

            def activity_summary(self, *_args, **_kwargs):
                self.summary_calls += 1
                return {"apps": [{"name": "Google Chrome", "minutes": 42}]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(scenes, fh, ensure_ascii=False)
            tmp_path = Path(fh.name)

        client = StubScreenClient()
        previous_mode = os.environ.get("OPENMY_SCREEN_CONTEXT_MODE")
        os.environ["OPENMY_SCREEN_CONTEXT_MODE"] = "off"
        try:
            briefing = generate_briefing(tmp_path, "2026-04-10", client)
        finally:
            os.unlink(tmp_path)
            if previous_mode is None:
                os.environ.pop("OPENMY_SCREEN_CONTEXT_MODE", None)
            else:
                os.environ["OPENMY_SCREEN_CONTEXT_MODE"] = previous_mode

        self.assertFalse(briefing.screen_recognition_available)
        self.assertEqual(briefing.work_sessions, {})
        self.assertEqual(client.search_calls, 0)
        self.assertEqual(client.summary_calls, 0)

    def test_briefing_summary_uses_first_person_when_screen_usage_is_available(self):
        scenes = {
            "scenes": [
                {
                    "scene_id": "scene_001",
                    "time_start": "20:00",
                    "time_end": "20:10",
                    "text": "简单记录一下。",
                    "summary": "简单记录一下。",
                    "role": {"addressed_to": "自己", "scene_type": "self"},
                }
            ],
            "stats": {},
        }

        class StubScreenClient:
            def is_available(self):
                return True

            def search_ocr(self, **_kwargs):
                return []

            def activity_summary(self, *_args, **_kwargs):
                return {"apps": [{"name": "Codex", "minutes": 95}, {"name": "Google Chrome", "minutes": 61}]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(scenes, fh, ensure_ascii=False)
            tmp_path = Path(fh.name)

        try:
            briefing = generate_briefing(tmp_path, "2026-04-10", StubScreenClient())
        finally:
            os.unlink(tmp_path)

        self.assertTrue(briefing.summary.startswith("我"))
        self.assertIn("Codex", briefing.summary)


if __name__ == "__main__":
    unittest.main()
