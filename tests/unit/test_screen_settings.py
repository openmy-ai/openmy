#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from openmy.domain.models import ScreenContext, SceneBlock
from openmy.services.roles.resolver import resolve_roles
from openmy.services.screen_recognition.settings import (
    ScreenContextSettings,
    load_screen_context_settings,
    save_screen_context_settings,
)


class TestScreenSettings(unittest.TestCase):
    def test_defaults_are_conservative(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            settings = load_screen_context_settings(data_root=data_root)

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.participation_mode, "summary_only")
        self.assertEqual(settings.capture_interval_seconds, 5)
        self.assertEqual(settings.screenshot_retention_hours, 24)

    def test_round_trip_file_persists_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            settings = ScreenContextSettings(
                enabled=True,
                participation_mode="full",
                exclude_apps=["微信"],
                exclude_domains=["taobao.com"],
                exclude_window_keywords=["支付"],
                capture_interval_seconds=7,
                screenshot_retention_hours=48,
            )
            save_screen_context_settings(settings, data_root=data_root)

            loaded = load_screen_context_settings(data_root=data_root)

        self.assertEqual(loaded.participation_mode, "full")
        self.assertEqual(loaded.exclude_apps, ["微信"])
        self.assertEqual(loaded.exclude_domains, ["taobao.com"])
        self.assertEqual(loaded.exclude_window_keywords, ["支付"])
        self.assertEqual(loaded.capture_interval_seconds, 7)
        self.assertEqual(loaded.screenshot_retention_hours, 48)

    def test_off_mode_is_loaded_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            save_screen_context_settings(
                ScreenContextSettings(enabled=False, participation_mode="off"),
                data_root=data_root,
            )

            loaded = load_screen_context_settings(data_root=data_root)

        self.assertFalse(loaded.enabled)
        self.assertEqual(loaded.participation_mode, "off")

    def test_legacy_screen_recognition_env_can_disable_participation(self):
        loaded = load_screen_context_settings(env={"SCREEN_RECOGNITION_ENABLED": "false"})

        self.assertFalse(loaded.enabled)
        self.assertEqual(loaded.participation_mode, "off")

    def test_resolve_roles_clears_stale_screen_context_when_no_screen_client(self):
        scene = SceneBlock(scene_id="scene_001", time_start="10:00", time_end="10:05", text="这个我待会儿弄")
        scene.screen_context = ScreenContext(
            enabled=True,
            aligned=True,
            summary="当时正在 Cursor 修改 OpenMy",
            primary_app="Cursor",
        )

        result = resolve_roles([scene], date_str="2026-04-10", screen_client=None)

        self.assertFalse(result[0].screen_context.aligned)
        self.assertEqual(result[0].screen_context.summary, "")


if __name__ == "__main__":
    unittest.main()
