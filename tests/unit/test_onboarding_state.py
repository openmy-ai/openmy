#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from openmy.services.onboarding.state import build_onboarding_state, save_onboarding_state, load_onboarding_state


class TestOnboardingState(unittest.TestCase):
    def test_build_prefers_current_ready_provider(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = build_onboarding_state(
                data_root=Path(tmp_dir),
                stt_providers=[
                    {"name": "funasr", "ready": True},
                    {"name": "faster-whisper", "ready": True},
                ],
                current_stt="faster-whisper",
                profile_exists=True,
                vocab_exists=True,
            )

        self.assertEqual(payload["recommended_provider"], "faster-whisper")
        self.assertEqual(payload["stage"], "ready")

    def test_build_falls_back_to_first_ready_priority(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = build_onboarding_state(
                data_root=Path(tmp_dir),
                stt_providers=[
                    {"name": "gemini", "ready": False},
                    {"name": "funasr", "ready": True},
                    {"name": "faster-whisper", "ready": True},
                ],
                current_stt="",
                profile_exists=False,
                vocab_exists=False,
            )

        self.assertEqual(payload["recommended_provider"], "funasr")
        self.assertEqual(payload["stage"], "choose_provider")

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = {"completed": False, "recommended_provider": "funasr"}
            save_onboarding_state(root, payload)
            loaded = load_onboarding_state(root)

        self.assertEqual(loaded["recommended_provider"], "funasr")

    def test_build_includes_choice_groups_and_headline(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = build_onboarding_state(
                data_root=Path(tmp_dir),
                stt_providers=[
                    {"name": "funasr", "ready": True, "type": "local", "is_active": False, "needs_api_key": False},
                    {"name": "faster-whisper", "ready": True, "type": "local", "is_active": False, "needs_api_key": False},
                    {"name": "gemini", "ready": False, "type": "api", "is_active": False, "needs_api_key": True},
                    {"name": "groq", "ready": False, "type": "api", "is_active": False, "needs_api_key": True},
                    {"name": "dashscope", "ready": False, "type": "api", "is_active": False, "needs_api_key": True},
                    {"name": "deepgram", "ready": False, "type": "api", "is_active": False, "needs_api_key": True},
                ],
                current_stt="",
                profile_exists=True,
                vocab_exists=True,
            )

        self.assertIn("先别自己挑", payload["headline"])
        self.assertIn("profile.set --stt-provider funasr", payload["primary_action"])
        self.assertEqual(payload["choices"]["local"][0]["name"], "funasr")
        self.assertTrue(payload["choices"]["local"][0]["is_recommended"])
