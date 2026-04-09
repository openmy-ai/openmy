#!/usr/bin/env python3
"""
test_clean.py — 清洗模块测试

cleaner 现在全部交给 Gemini CLI 做语义级清洗，
所以测试用 mock 验证调用行为，而不是测正则规则。
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from openmy.services.cleaning import cleaner as clean


class CleanTextCallsGeminiCLITest(unittest.TestCase):
    """验证 clean_text 会调用 Gemini CLI"""

    @patch('openmy.services.cleaning.cleaner.clean_with_gemini_cli')
    def test_clean_text_delegates_to_gemini(self, mock_gemini):
        mock_gemini.return_value = "清洗后的文本"
        result = clean.clean_text("原始文本")
        mock_gemini.assert_called_once_with("原始文本")
        self.assertEqual(result, "清洗后的文本")


class CleanPromptTest(unittest.TestCase):
    """验证 prompt 模板包含关键约束"""

    def test_prompt_prohibits_bold(self):
        self.assertIn("不加粗", clean.CLEAN_PROMPT)

    def test_prompt_preserves_profanity(self):
        self.assertIn("不要删脏话", clean.CLEAN_PROMPT)

    def test_prompt_preserves_time_headers(self):
        self.assertIn("## HH:MM", clean.CLEAN_PROMPT)

    def test_prompt_preserves_background_sounds(self):
        self.assertIn("背景音标注", clean.CLEAN_PROMPT)

    def test_prompt_has_text_placeholder(self):
        self.assertIn("{text}", clean.CLEAN_PROMPT)


class GeminiCLICallTest(unittest.TestCase):
    """验证 Gemini CLI 调用的参数和错误处理"""

    @patch('openmy.services.cleaning.cleaner.prepare_isolated_home')
    @patch('subprocess.run')
    def test_successful_call(self, mock_run, mock_home):
        mock_home.return_value = Path("/tmp/fake-home")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  清洗后文本  ",
            stderr="",
        )

        result = clean.clean_with_gemini_cli("原始文本")
        self.assertEqual(result, "清洗后文本")

        # 验证调用了 gemini 命令
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        self.assertEqual(cmd[0], "gemini")
        self.assertIn("-m", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("text", cmd)

    @patch('openmy.services.cleaning.cleaner.prepare_isolated_home')
    @patch('subprocess.run')
    def test_nonzero_exit_raises(self, mock_run, mock_home):
        mock_home.return_value = Path("/tmp/fake-home")
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error message",
        )

        with self.assertRaises(RuntimeError) as ctx:
            clean.clean_with_gemini_cli("原始文本")
        self.assertIn("清洗失败", str(ctx.exception))

    @patch('openmy.services.cleaning.cleaner.prepare_isolated_home')
    @patch('subprocess.run')
    def test_empty_output_raises(self, mock_run, mock_home):
        mock_home.return_value = Path("/tmp/fake-home")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        with self.assertRaises(RuntimeError) as ctx:
            clean.clean_with_gemini_cli("原始文本")
        self.assertIn("没有返回内容", str(ctx.exception))


class CorrectionUtilsTest(unittest.TestCase):
    """纠错工具函数保留，验证基本功能"""

    def test_load_corrections_returns_list_when_missing(self):
        result = clean.load_corrections()
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
