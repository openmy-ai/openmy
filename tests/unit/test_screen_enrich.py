#!/usr/bin/env python3
import unittest

from openmy.domain.models import RoleTag, SceneBlock, ScreenSession
from openmy.services.screen_recognition.enrich import enrich_scene_with_screen_context
from openmy.services.screen_recognition.settings import ScreenContextSettings


class TestScreenEnrich(unittest.TestCase):
    def make_scene(self):
        scene = SceneBlock(
            scene_id="scene_001",
            time_start="10:00",
            time_end="10:05",
            text="这个我待会儿弄",
        )
        scene.role = RoleTag(
            category="uncertain",
            scene_type="uncertain",
            scene_type_label="不确定",
            confidence=0.0,
            evidence_chain=[],
            needs_review=True,
        )
        return scene

    def test_enrich_writes_screen_context_summary_tags_and_primary_handles(self):
        scene = self.make_scene()
        sessions = [
            ScreenSession(
                app_name="Cursor",
                window_name="OpenMy - screen context",
                url_domain="github.com",
                text="正在修改 OpenMy 的 screen context provider 与 privacy",
                summary="",
                start_time="2026-04-10T10:00:30+08:00",
                end_time="2026-04-10T10:04:30+08:00",
                frame_ids=[1, 2, 3],
            )
        ]

        enrich_scene_with_screen_context(
            scene,
            sessions,
            ScreenContextSettings(enabled=True, participation_mode="summary_only"),
        )

        self.assertEqual(scene.screen_context.primary_app, "Cursor")
        self.assertEqual(scene.screen_context.primary_domain, "github.com")
        self.assertIn("development", scene.screen_context.tags)
        self.assertIn("OpenMy", scene.screen_context.summary)
        self.assertEqual(len(scene.screen_sessions), 1)

    def test_enrich_collects_completion_candidates(self):
        scene = self.make_scene()
        sessions = [
            ScreenSession(
                app_name="GitHub",
                window_name="Pull request merged",
                url_domain="github.com",
                text="Pull request merged successfully",
                summary="",
                start_time="2026-04-10T10:00:30+08:00",
                end_time="2026-04-10T10:04:30+08:00",
            )
        ]

        enrich_scene_with_screen_context(
            scene,
            sessions,
            ScreenContextSettings(enabled=True, participation_mode="summary_only"),
        )

        self.assertTrue(scene.screen_context.completion_candidates)
        self.assertEqual(scene.screen_context.completion_candidates[0].kind, "merged")


if __name__ == "__main__":
    unittest.main()
