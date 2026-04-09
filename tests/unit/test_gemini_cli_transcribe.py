#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

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

    def test_build_prompt_no_at_prefix(self):
        """SDK 版本不需要 @文件名 前缀。"""
        prompt = gemini_cli_transcribe.build_prompt('常见词')
        self.assertNotIn('@', prompt)

    def test_run_gemini_cli_backward_compat_requires_api_key(self):
        """向后兼容接口在缺少 API key 时应报错。"""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                gemini_cli_transcribe.run_gemini_cli(
                    audio_path=Path('/tmp/fake.mp3'),
                    model='gemini-3.1-flash-lite-preview',
                    vocab_terms='',
                    timeout_seconds=10,
                )
            self.assertIn('GEMINI_API_KEY', str(ctx.exception))

    def test_transcribe_audio_calls_sdk(self):
        """验证 transcribe_audio 调用了 genai SDK。"""
        mock_client = MagicMock()
        mock_uploaded = MagicMock()
        mock_uploaded.state = "ACTIVE"
        mock_uploaded.uri = "gs://fake"
        mock_uploaded.mime_type = "audio/mp3"
        mock_uploaded.name = "files/fake"
        mock_client.files.upload.return_value = mock_uploaded

        mock_response = MagicMock()
        mock_response.text = "转写结果文本"
        mock_client.models.generate_content.return_value = mock_response

        with patch('openmy.adapters.transcription.gemini_cli.genai') as mock_genai:
            mock_genai.Client.return_value = mock_client

            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                result = gemini_cli_transcribe.transcribe_audio(
                    audio_path=Path(f.name),
                    api_key='fake-key',
                    model='gemini-3.1-flash-lite-preview',
                    vocab_terms='测试',
                    timeout_seconds=10,
                )

            self.assertEqual(result, "转写结果文本")
            mock_client.files.upload.assert_called_once()
            mock_client.models.generate_content.assert_called_once()


if __name__ == '__main__':
    unittest.main()
