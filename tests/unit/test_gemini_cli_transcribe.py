#!/usr/bin/env python3
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

    def test_build_prompt_contains_vocab_and_instructions(self):
        prompt = gemini_cli_transcribe.build_prompt('Claude、StreamDeck')
        self.assertIn('Claude、StreamDeck', prompt)
        self.assertIn('不要脑补', prompt)
        self.assertIn('逐字转写', prompt)
        self.assertNotIn('个人归档系统', prompt)
        self.assertNotIn('伴侣、家人、朋友、商家、AI、宠物', prompt)

    def test_build_prompt_no_at_prefix(self):
        """SDK 版本不需要 @文件名 前缀。"""
        prompt = gemini_cli_transcribe.build_prompt('常见词')
        self.assertNotIn('@', prompt)


if __name__ == '__main__':
    unittest.main()
