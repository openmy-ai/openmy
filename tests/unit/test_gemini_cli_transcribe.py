#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from openmy.adapters.transcription import gemini_cli as gemini_cli_transcribe


class GeminiCliTranscribeTest(unittest.TestCase):
    def test_load_vocab_terms_includes_hints(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vocab_path = Path(tmpdir) / 'vocab.txt'
            vocab_path.write_text(
                '# 注释\nClaude | Anthropic AI model\n\nStreamDeck\n',
                encoding='utf-8',
            )
            self.assertEqual(
                gemini_cli_transcribe.load_vocab_terms(vocab_path),
                'Claude（Anthropic AI model）、StreamDeck',
            )

    def test_build_prompt_contains_vocab_and_instructions(self):
        prompt = gemini_cli_transcribe.build_prompt('Claude、StreamDeck')
        self.assertIn('Claude、StreamDeck', prompt)
        self.assertIn('人声口述', prompt)
        self.assertIn('优先匹配', prompt)
        self.assertNotIn('个人归档系统', prompt)
        self.assertNotIn('伴侣、家人、朋友、商家、AI、宠物', prompt)

    def test_build_prompt_no_at_prefix(self):
        """SDK 版本不需要 @文件名 前缀。"""
        prompt = gemini_cli_transcribe.build_prompt('常见词')
        self.assertNotIn('@', prompt)

    def test_system_instruction_is_attribution_based(self):
        """冻结的归因式 prompt（ADR-0001）：三类前缀 + 存疑记号，旧过滤式规则不得回潮。"""
        from openmy.providers.stt.gemini import SYSTEM_INSTRUCTION

        # 三类来源前缀与存疑记号
        self.assertIn('我：', SYSTEM_INSTRUCTION)
        self.assertIn('人：', SYSTEM_INSTRUCTION)
        self.assertIn('外：', SYSTEM_INSTRUCTION)
        self.assertIn('[?]', SYSTEM_INSTRUCTION)
        self.assertIn('[无法识别]', SYSTEM_INSTRUCTION)
        self.assertIn('[无人声]', SYSTEM_INSTRUCTION)
        # 通话归类规则（通话对方 → 人：）
        self.assertIn('通话', SYSTEM_INSTRUCTION)
        # 防复读规则
        self.assertIn('重复', SYSTEM_INSTRUCTION)
        # 旧过滤式规则不得回潮
        self.assertNotIn('不添加说话人标注', SYSTEM_INSTRUCTION)
        self.assertNotIn('不转写该段', SYSTEM_INSTRUCTION)

    def test_run_gemini_cli_backward_compat_requires_api_key(self):
        """向后兼容接口在缺少 API key 时应报错。"""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                gemini_cli_transcribe.run_gemini_cli(
                    audio_path=Path('/tmp/fake.mp3'),
                    model='gemini-3.5-flash',
                    vocab_terms='',
                    timeout_seconds=10,
                )
            self.assertIn('GEMINI_API_KEY', str(ctx.exception))

    def test_transcribe_audio_calls_sdk(self):
        """验证 transcribe_audio 通过 provider registry 调用转写层。"""
        mock_provider = MagicMock()
        mock_provider.transcribe.return_value = "转写结果文本"

        with patch('openmy.adapters.transcription.gemini_cli.ProviderRegistry.from_env') as registry_factory:
            registry_factory.return_value.get_stt_provider.return_value = mock_provider

            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                result = gemini_cli_transcribe.transcribe_audio(
                    audio_path=Path(f.name),
                    api_key='fake-key',
                    model='gemini-3.5-flash',
                    vocab_terms='测试',
                    timeout_seconds=10,
                )

            self.assertEqual(result, "转写结果文本")
            registry_factory.return_value.get_stt_provider.assert_called_once_with(
                model='gemini-3.5-flash',
                api_key='fake-key',
            )
            mock_provider.transcribe.assert_called_once()


if __name__ == '__main__':
    unittest.main()
