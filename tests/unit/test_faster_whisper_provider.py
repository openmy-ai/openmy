#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openmy.providers.stt.faster_whisper import FasterWhisperSTTProvider


class TestFasterWhisperProvider(unittest.TestCase):
    def test_missing_dependency_raises_friendly_error(self):
        provider = FasterWhisperSTTProvider(api_key="", model="small")

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "sample.wav"
            audio_path.write_bytes(b"wav")

            with patch("openmy.providers.stt.faster_whisper.WhisperModel", None):
                with self.assertRaises(RuntimeError) as ctx:
                    provider.transcribe(audio_path, timeout_seconds=30)

        self.assertIn("faster-whisper", str(ctx.exception))
        self.assertIn("uv pip install", str(ctx.exception))
