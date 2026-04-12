#!/usr/bin/env python3
import unittest
from unittest.mock import patch


class TestProviderRegistry(unittest.TestCase):
    def test_registry_builds_local_faster_whisper_provider_without_api_key(self):
        with patch.dict(
            "os.environ",
            {
                "OPENMY_STT_PROVIDER": "faster-whisper",
                "OPENMY_STT_MODEL": "small",
                "OPENMY_LLM_PROVIDER": "gemini",
                "OPENMY_LLM_API_KEY": "llm-key",
            },
            clear=True,
        ):
            from openmy.providers.registry import ProviderRegistry

            registry = ProviderRegistry.from_env()
            stt = registry.get_stt_provider()

        self.assertEqual(stt.name, "faster-whisper")
        self.assertEqual(stt.model, "small")
        self.assertEqual(stt.api_key, "")

    def test_registry_prefers_openmy_provider_env(self):
        with patch.dict(
            "os.environ",
            {
                "OPENMY_STT_PROVIDER": "gemini",
                "OPENMY_STT_MODEL": "gemini-stt-custom",
                "OPENMY_STT_API_KEY": "stt-key",
                "OPENMY_LLM_PROVIDER": "gemini",
                "OPENMY_LLM_MODEL": "gemini-llm-custom",
                "OPENMY_LLM_API_KEY": "llm-key",
            },
            clear=True,
        ):
            from openmy.providers.registry import ProviderRegistry

            registry = ProviderRegistry.from_env()
            stt = registry.get_stt_provider()
            llm = registry.get_llm_provider()

        self.assertEqual(stt.name, "gemini")
        self.assertEqual(stt.model, "gemini-stt-custom")
        self.assertEqual(stt.api_key, "stt-key")
        self.assertEqual(llm.name, "gemini")
        self.assertEqual(llm.model, "gemini-llm-custom")
        self.assertEqual(llm.api_key, "llm-key")

    def test_registry_defaults_stt_to_local_faster_whisper(self):
        """No default STT provider — must raise if not configured."""
        with patch.dict("os.environ", {}, clear=True):
            from openmy.providers.registry import ProviderRegistry

            registry = ProviderRegistry.from_env()
            with self.assertRaises(ValueError):
                registry.get_stt_provider()

    def test_registry_builds_local_funasr_provider_without_api_key(self):
        with patch.dict(
            "os.environ",
            {
                "OPENMY_STT_PROVIDER": "funasr",
                "OPENMY_STT_MODEL": "paraformer-zh",
                "OPENMY_LLM_PROVIDER": "gemini",
                "OPENMY_LLM_API_KEY": "llm-key",
            },
            clear=True,
        ):
            from openmy.providers.registry import ProviderRegistry

            registry = ProviderRegistry.from_env()
            stt = registry.get_stt_provider()

        self.assertEqual(stt.name, "funasr")
        self.assertEqual(stt.model, "paraformer-zh")
        self.assertEqual(stt.api_key, "")

    def test_registry_falls_back_to_gemini_compat_env_when_provider_is_gemini(self):
        with patch.dict(
            "os.environ",
            {
                "OPENMY_STT_PROVIDER": "gemini",
                "OPENMY_LLM_PROVIDER": "gemini",
                "GEMINI_API_KEY": "compat-key",
                "GEMINI_MODEL": "gemini-compat-model",
            },
            clear=True,
        ):
            from openmy.providers.registry import ProviderRegistry

            registry = ProviderRegistry.from_env()
            stt = registry.get_stt_provider()
            llm = registry.get_llm_provider()

        self.assertEqual(stt.api_key, "compat-key")
        self.assertEqual(llm.api_key, "compat-key")
        self.assertEqual(stt.model, "gemini-compat-model")
        self.assertEqual(llm.model, "gemini-compat-model")

    def test_registry_rejects_unknown_provider(self):
        with patch.dict("os.environ", {"OPENMY_LLM_PROVIDER": "unknown"}, clear=True):
            from openmy.providers.registry import ProviderRegistry

            registry = ProviderRegistry.from_env()
            with self.assertRaises(ValueError):
                registry.get_llm_provider()
