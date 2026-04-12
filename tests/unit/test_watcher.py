#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openmy.services import watcher


class TestWatcher(unittest.TestCase):
    def test_resolve_watch_directory_uses_env_when_directory_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            with patch.object(watcher, "get_audio_source_dir", return_value=str(root)):
                resolved = watcher.resolve_watch_directory(None)

            self.assertEqual(resolved, root.resolve())

    def test_scan_finds_new_stable_wav_without_event(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            wav_path = root / "TX01_MIC001_20260401_104056_orig.wav"
            wav_path.write_bytes(b"wav-data")

            handler = watcher.AudioFileHandler(cooldown_seconds=30)
            handler.scan_directory(root)
            self.assertEqual(handler._pending, {})

            handler.scan_directory(root)
            self.assertIn("2026-04-01", handler._pending)
            self.assertIn(str(wav_path.resolve()), handler._pending["2026-04-01"])

    def test_scan_ignores_file_until_stable(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            wav_path = root / "TX01_MIC001_20260401_104056_orig.wav"
            wav_path.write_bytes(b"wav-data")

            handler = watcher.AudioFileHandler(cooldown_seconds=30)
            handler.scan_directory(root)
            wav_path.write_bytes(b"wav-data-updated")
            handler.scan_directory(root)
            self.assertEqual(handler._pending, {})

            handler.scan_directory(root)
            self.assertIn("2026-04-01", handler._pending)

    def test_create_observer_returns_none_without_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            handler = watcher.AudioFileHandler(cooldown_seconds=30)

            with patch.object(watcher, "Observer", None):
                observer = watcher.create_observer(root, handler)

            self.assertIsNone(observer)

    def test_events_do_not_mark_file_ready_before_scan_confirms_stability(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            wav_path = root / "TX01_MIC001_20260401_104056_orig.wav"
            wav_path.write_bytes(b"wav-data")
            event = SimpleNamespace(is_directory=False, src_path=str(wav_path))

            handler = watcher.AudioFileHandler(cooldown_seconds=30)
            handler.on_created(event)
            handler.on_modified(event)
            self.assertEqual(handler._pending, {})

            handler.scan_directory(root)
            self.assertEqual(handler._pending, {})

            handler.scan_directory(root)
            self.assertIn("2026-04-01", handler._pending)


if __name__ == "__main__":
    unittest.main()
