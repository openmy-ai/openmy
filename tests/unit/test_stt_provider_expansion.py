#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestExpandedSttProviders(unittest.TestCase):
    def test_registry_builds_groq_provider_with_compat_key(self):
        with patch.dict(
            "os.environ",
            {
                "OPENMY_STT_PROVIDER": "groq",
                "GROQ_API_KEY": "groq-key",
                "OPENMY_LLM_PROVIDER": "gemini",
                "OPENMY_LLM_API_KEY": "llm-key",
            },
            clear=True,
        ):
            from openmy.providers.registry import ProviderRegistry

            provider = ProviderRegistry.from_env().get_stt_provider()

        self.assertEqual(provider.name, "groq")
        self.assertEqual(provider.api_key, "groq-key")
        self.assertEqual(provider.model, "whisper-large-v3-turbo")

    def test_registry_builds_dashscope_provider_with_compat_key(self):
        with patch.dict(
            "os.environ",
            {
                "OPENMY_STT_PROVIDER": "dashscope",
                "DASHSCOPE_API_KEY": "dash-key",
                "OPENMY_LLM_PROVIDER": "gemini",
                "OPENMY_LLM_API_KEY": "llm-key",
            },
            clear=True,
        ):
            from openmy.providers.registry import ProviderRegistry

            provider = ProviderRegistry.from_env().get_stt_provider()

        self.assertEqual(provider.name, "dashscope")
        self.assertEqual(provider.api_key, "dash-key")
        self.assertEqual(provider.model, "qwen3-asr-1.7b")

    def test_registry_builds_deepgram_provider_with_compat_key(self):
        with patch.dict(
            "os.environ",
            {
                "OPENMY_STT_PROVIDER": "deepgram",
                "DEEPGRAM_API_KEY": "deep-key",
                "OPENMY_LLM_PROVIDER": "gemini",
                "OPENMY_LLM_API_KEY": "llm-key",
            },
            clear=True,
        ):
            from openmy.providers.registry import ProviderRegistry

            provider = ProviderRegistry.from_env().get_stt_provider()

        self.assertEqual(provider.name, "deepgram")
        self.assertEqual(provider.api_key, "deep-key")
        self.assertEqual(provider.model, "nova-3")

    def test_groq_provider_missing_key(self):
        from openmy.providers.stt.groq_whisper import GroqWhisperSTTProvider

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            provider = GroqWhisperSTTProvider(api_key="", model="whisper-large-v3-turbo")
            with self.assertRaises(RuntimeError) as ctx:
                provider.transcribe(Path(audio_file.name), timeout_seconds=5)
        self.assertIn("GROQ_API_KEY", str(ctx.exception))

    def test_dashscope_provider_missing_key(self):
        from openmy.providers.stt.dashscope_asr import DashScopeASRProvider

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            provider = DashScopeASRProvider(api_key="", model="qwen3-asr-1.7b")
            with self.assertRaises(RuntimeError) as ctx:
                provider.transcribe(Path(audio_file.name), timeout_seconds=5)
        self.assertIn("DASHSCOPE_API_KEY", str(ctx.exception))

    def test_deepgram_provider_missing_key(self):
        from openmy.providers.stt.deepgram import DeepgramSTTProvider

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            provider = DeepgramSTTProvider(api_key="", model="nova-3")
            with self.assertRaises(RuntimeError) as ctx:
                provider.transcribe(Path(audio_file.name), timeout_seconds=5)
        self.assertIn("DEEPGRAM_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
