#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openmy.adapters.screen_recognition.client import ScreenRecognitionClient
from openmy.services.screen_recognition.capture import (
    ScreenEventRecord,
    activity_summary,
    append_event,
    query_events,
    search_elements,
)


class TestScreenCaptureStore(unittest.TestCase):
    def test_query_events_filters_by_time_and_app(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            append_event(
                ScreenEventRecord(
                    frame_id=1,
                    timestamp="2026-04-12T10:00:00+08:00",
                    app_name="OpenMy",
                    window_name="日报",
                    browser_url="",
                    text="第一条",
                    screenshot_path="/tmp/1.png",
                    content_hash="hash-1",
                    ocr_engine="apple-vision",
                    ocr_text_json=[{"text": "第一条", "left": "0", "top": "0", "width": "1", "height": "1"}],
                ),
                data_root=data_root,
            )
            append_event(
                ScreenEventRecord(
                    frame_id=2,
                    timestamp="2026-04-12T10:00:10+08:00",
                    app_name="Terminal",
                    window_name="tmux",
                    browser_url="",
                    text="第二条",
                    screenshot_path="/tmp/2.png",
                    content_hash="hash-2",
                    ocr_engine="apple-vision",
                ),
                data_root=data_root,
            )

            records = query_events(
                "2026-04-12T09:59:00+08:00",
                "2026-04-12T10:00:05+08:00",
                data_root=data_root,
                app_name="OpenMy",
                limit=10,
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].text, "第一条")

    def test_activity_summary_aggregates_apps_and_windows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            for idx, ts in enumerate(
                [
                    "2026-04-12T10:00:00+08:00",
                    "2026-04-12T10:00:05+08:00",
                    "2026-04-12T10:00:10+08:00",
                ],
                start=1,
            ):
                append_event(
                    ScreenEventRecord(
                        frame_id=idx,
                        timestamp=ts,
                        app_name="OpenMy",
                        window_name="日报",
                        browser_url="http://localhost:8420/",
                        text=f"第{idx}条",
                        screenshot_path=f"/tmp/{idx}.png",
                        content_hash=f"hash-{idx}",
                        ocr_engine="apple-vision",
                    ),
                    data_root=data_root,
                )

            summary = activity_summary(
                "2026-04-12T09:59:00+08:00",
                "2026-04-12T10:01:00+08:00",
                data_root=data_root,
                capture_interval_seconds=5,
            )

        self.assertEqual(summary["total_frames"], 3)
        self.assertEqual(summary["apps"][0]["name"], "OpenMy")
        self.assertEqual(summary["windows"][0]["window_name"], "日报")
        self.assertGreater(summary["apps"][0]["minutes"], 0)

    def test_search_elements_flattens_ocr_boxes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            append_event(
                ScreenEventRecord(
                    frame_id=1,
                    timestamp="2026-04-12T10:00:00+08:00",
                    app_name="OpenMy",
                    window_name="日报",
                    browser_url="",
                    text="第一条",
                    screenshot_path="/tmp/1.png",
                    content_hash="hash-1",
                    ocr_engine="apple-vision",
                    ocr_text_json=[{"text": "按钮", "left": "0.1", "top": "0.2", "width": "0.3", "height": "0.4"}],
                ),
                data_root=data_root,
            )

            rows = search_elements(
                "2026-04-12T09:59:00+08:00",
                "2026-04-12T10:01:00+08:00",
                data_root=data_root,
                limit=10,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text"], "按钮")
        self.assertEqual(rows[0]["bounds"]["left"], "0.1")


class TestLocalScreenRecognitionClient(unittest.TestCase):
    def test_local_client_reports_available_when_daemon_running(self):
        with (
            patch("openmy.adapters.screen_recognition.client.is_capture_supported", return_value=True),
            patch("openmy.adapters.screen_recognition.client.daemon_running", return_value=True),
        ):
            client = ScreenRecognitionClient(data_root=Path("/tmp/openmy-data"))
            self.assertTrue(client.is_available())
            self.assertTrue(client.daemon_running())

    def test_local_client_uses_json_store(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            append_event(
                ScreenEventRecord(
                    frame_id=1,
                    timestamp="2026-04-12T10:00:00+08:00",
                    app_name="OpenMy",
                    window_name="日报",
                    browser_url="",
                    text="第一条",
                    screenshot_path="/tmp/1.png",
                    content_hash="hash-1",
                    ocr_engine="apple-vision",
                ),
                data_root=data_root,
            )
            with patch("openmy.adapters.screen_recognition.client.is_capture_supported", return_value=True):
                client = ScreenRecognitionClient(data_root=data_root)
                events = client.search_ocr(
                    "2026-04-12T09:59:00+08:00",
                    "2026-04-12T10:01:00+08:00",
                )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].app_name, "OpenMy")


if __name__ == "__main__":
    unittest.main()
