#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from openmy.adapters.transcription import gemini_cli as gemini_cli_transcribe


class GeminiCliTranscribeTest(unittest.TestCase):
    def test_load_vocab_terms_ignores_comments_and_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vocab_path = Path(tmpdir) / 'vocab.txt'
            vocab_path.write_text(
                '# 注释\nClaude | note\n\nStreamDeck | note\n',
                encoding='utf-8',
            )
            self.assertEqual(
                gemini_cli_transcribe.load_vocab_terms(vocab_path),
                'Claude、StreamDeck',
            )

    def test_build_prompt_mentions_audio_and_vocab(self):
        prompt = gemini_cli_transcribe.build_prompt('audio.wav', 'Claude、StreamDeck')
        self.assertIn('@audio.wav', prompt)
        self.assertIn('Claude、StreamDeck', prompt)
        self.assertIn('不要脑补', prompt)

    def test_prepare_isolated_home_copies_auth_and_writes_minimal_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_home = Path(tmpdir) / 'source'
            source_home.mkdir()
            for name in gemini_cli_transcribe.REQUIRED_GEMINI_HOME_FILES:
                (source_home / name).write_text('{}', encoding='utf-8')

            isolated_root = gemini_cli_transcribe.prepare_isolated_home(
                source_home,
                'gemini-3-flash-preview',
            )
            try:
                gemini_dir = isolated_root / '.gemini'
                for name in gemini_cli_transcribe.REQUIRED_GEMINI_HOME_FILES:
                    self.assertTrue((gemini_dir / name).exists(), name)

                settings = json.loads((gemini_dir / 'settings.json').read_text(encoding='utf-8'))
                self.assertEqual(settings['model']['name'], 'gemini-3-flash-preview')
                self.assertEqual(settings['general']['approvalMode'], 'yolo')
                self.assertEqual(settings['security']['auth']['selectedType'], 'oauth-personal')
            finally:
                import shutil

                shutil.rmtree(isolated_root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
