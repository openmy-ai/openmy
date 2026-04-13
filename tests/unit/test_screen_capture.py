#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openmy.adapters.screen_recognition.client import ScreenRecognitionClient
from openmy.services.screen_recognition.capture_common import CaptureMetadata, OcrPayload
from openmy.services.screen_recognition.capture import (
    OcrCache,
    ScreenEventRecord,
    activity_summary,
    append_event,
    capture_once,
    capture_screen_event,
    query_events,
    search_elements,
    start_capture_daemon,
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


class TestCaptureWorkerIsolation(unittest.TestCase):
    def test_capture_screen_event_reuses_cached_ocr_payload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            cache = OcrCache()

            def fake_capture_screenshot(path: Path, display_id: str | None = None):
                path.write_bytes(b"image")
                return path

            metadata = CaptureMetadata(app_name="OpenMy", window_name="日报", browser_url="")
            payload = OcrPayload(text="缓存文本", text_json=[{"text": "缓存文本"}], confidence=1.0, engine="apple-vision")

            with (
                patch("openmy.services.screen_recognition.capture_engine.get_frontmost_context", return_value=metadata),
                patch("openmy.services.screen_recognition.capture_engine.capture_screenshot", side_effect=fake_capture_screenshot),
                patch("openmy.services.screen_recognition.capture_engine._file_hash", return_value="hash-1"),
                patch("openmy.services.screen_recognition.capture_engine._run_ocr_in_subprocess", return_value=payload) as worker_mock,
            ):
                first = capture_screen_event(data_root=data_root, ocr_cache=cache)
                second = capture_screen_event(data_root=data_root, ocr_cache=cache)

        self.assertEqual(worker_mock.call_count, 1)
        self.assertEqual(first.text, "缓存文本")
        self.assertEqual(second.text, "缓存文本")

    def test_start_capture_daemon_uses_lightweight_module_entry(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"

            with (
                patch("openmy.services.screen_recognition.capture_engine.is_capture_supported", return_value=True),
                patch("openmy.services.screen_recognition.capture_engine._pid_is_running", return_value=False),
                patch("openmy.services.screen_recognition.capture_engine.subprocess.Popen") as popen_mock,
            ):
                popen_mock.return_value.pid = 12345
                status = start_capture_daemon(data_root=data_root, interval_seconds=15, retention_hours=24)

        launched_cmd = " ".join(popen_mock.call_args.args[0])
        self.assertIn("openmy.services.screen_recognition.capture_tick", launched_cmd)
        self.assertEqual(status.pid, 12345)

    def test_start_capture_daemon_backoff_after_repeated_failures(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            with (
                patch("openmy.services.screen_recognition.capture_engine.is_capture_supported", return_value=True),
                patch("openmy.services.screen_recognition.capture_engine._pid_is_running", return_value=False),
                patch("openmy.services.screen_recognition.capture_engine.subprocess.Popen") as popen_mock,
            ):
                popen_mock.return_value.pid = 12345
                start_capture_daemon(data_root=data_root, interval_seconds=15, retention_hours=24)

        launched_cmd = " ".join(popen_mock.call_args.args[0])
        self.assertIn("fail=0;", launched_cmd)
        self.assertIn("sleep 60", launched_cmd)

    def test_capture_once_skips_event_when_screen_is_locked(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            with (
                patch("openmy.services.screen_recognition.capture_engine._is_screen_locked", return_value=True),
                patch("openmy.services.screen_recognition.capture_engine.capture_screen_event") as capture_mock,
            ):
                event, window_id, is_duplicate = capture_once(data_root=data_root)

        capture_mock.assert_not_called()
        self.assertTrue(event.screen_locked)
        self.assertEqual(window_id, "")
        self.assertFalse(is_duplicate)
        self.assertFalse((data_root / "screen_events.json").exists())


if __name__ == "__main__":
    unittest.main()
