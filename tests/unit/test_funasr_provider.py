#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openmy.providers.stt.funasr import FunASRSTTProvider, _MODEL_CACHE, _get_model


class TestFunASRProvider(unittest.TestCase):
    def tearDown(self):
        _MODEL_CACHE.clear()

    def test_missing_dependency_raises_friendly_error(self):
        provider = FunASRSTTProvider(api_key="", model="paraformer-zh")

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "sample.wav"
            audio_path.write_bytes(b"wav")

            with patch("openmy.providers.stt.funasr.AutoModel", None):
                with self.assertRaises(RuntimeError) as ctx:
                    provider.transcribe(audio_path, timeout_seconds=30)

        self.assertIn("FunASR", str(ctx.exception))
        self.assertIn("uv pip install", str(ctx.exception))

    def test_transcribe_normalizes_sentence_timestamps(self):
        provider = FunASRSTTProvider(api_key="", model="paraformer-zh")
        fake_model = SimpleNamespace(
            generate=lambda **_: [
                {
                    "text": "你好世界",
                    "timestamp": [[0, 620, "你好"], [620, 1100, "世界"]],
                    "sentence_info": [
                        {"text": "你好", "start": 0, "end": 620},
                        {"text": "世界", "start": 620, "end": 1100},
                    ],
                }
            ]
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "sample.wav"
            audio_path.write_bytes(b"wav")

            with patch("openmy.providers.stt.funasr._get_model", return_value=fake_model):
                result = provider.transcribe(
                    audio_path,
                    timeout_seconds=30,
                    vad_filter=True,
                    word_timestamps=True,
                    vocab_terms="OpenMy",
                )

        self.assertEqual(result.text, "你好世界")
        self.assertEqual(result.language, "zh")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0].text, "你好")
        self.assertEqual(result.segments[0].start, 0.0)
        self.assertEqual(result.segments[0].end, 0.62)
        self.assertEqual(result.provider_metadata["provider"], "funasr")
        self.assertTrue(result.provider_metadata["vad_filter"])
        self.assertTrue(result.provider_metadata["word_timestamps"])

    def test_get_model_does_not_enable_punc_model_by_default(self):
        fake_model = object()

        with (
            patch("openmy.providers.stt.funasr.AutoModel", return_value=fake_model) as auto_model,
            patch.dict("os.environ", {}, clear=True),
        ):
            resolved = _get_model("paraformer-zh", "cpu", False)

        self.assertIs(resolved, fake_model)
        kwargs = auto_model.call_args.kwargs
        self.assertNotIn("punc_model", kwargs)
