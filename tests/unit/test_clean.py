#!/usr/bin/env python3
"""
test_clean.py — 清洗模块测试

cleaner 现在用规则引擎（不调 API），测试验证每条规则的行为。
"""
import unittest
from unittest.mock import patch

from openmy.services.cleaning import cleaner as clean


class FillerRemovalTest(unittest.TestCase):
    """废词删除"""

    def test_standalone_filler_removed(self):
        result = clean.clean_text("## 10:00\n\n嗯。\n说正事了\n嗯\n啊\n好的内容")
        self.assertNotIn("嗯。", result)
        self.assertNotIn("\n嗯\n", result)
        self.assertNotIn("\n啊\n", result)
        self.assertIn("说正事了", result)
        self.assertIn("好的内容", result)

    def test_chatty_filler_removed(self):
        result = clean.clean_text("对对对\n那个\n就是说\n真正的内容在这里")
        self.assertIn("真正的内容在这里", result)

    def test_time_header_never_removed(self):
        result = clean.clean_text("## 10:00\n\n嗯\n内容\n## 11:00\n\n更多内容")
        self.assertIn("## 10:00", result)
        self.assertIn("## 11:00", result)


class InlineFillerTest(unittest.TestCase):
    """句中废词清理"""

    def test_leading_filler_stripped(self):
        result = clean.clean_text("嗯，然后我去吃饭了")
        self.assertIn("然后我去吃饭了", result)
        # "嗯，" 应被删
        self.assertNotIn("嗯，然后", result)


class AIPreambleTest(unittest.TestCase):
    """AI 转写引擎前缀删除"""

    def test_preamble_removed(self):
        text = "我这就为您转写这段音频\n## 10:00\n\n真正的内容"
        result = clean.clean_text(text)
        self.assertNotIn("为您转写", result)
        self.assertIn("真正的内容", result)

    def test_sub_wav_removed(self):
        text = "这是 sub_001.wav 的转写结果\n正文内容"
        result = clean.clean_text(text)
        self.assertNotIn("sub_001.wav", result)
        self.assertIn("正文内容", result)


class MusicMarkerTest(unittest.TestCase):
    """[音乐] 标记删除"""

    def test_music_removed(self):
        result = clean.clean_text("[音乐] 你好世界")
        self.assertNotIn("[音乐]", result)
        self.assertIn("你好世界", result)


class DeduplicationTest(unittest.TestCase):
    """连续重复行删除"""

    def test_consecutive_duplicates(self):
        result = clean.clean_text("这句话很重要\n这句话很重要\n这句话很重要\n另一句话")
        self.assertEqual(result.count("这句话很重要"), 1)
        self.assertIn("另一句话", result)


class ShortLineMergeTest(unittest.TestCase):
    """碎句合并"""

    def test_short_fragment_merged(self):
        result = clean.clean_text("前面的长内容长内容\n好\n后面的长内容")
        # "好" 只有 1 字，应该被合并到上一行
        lines = [l for l in result.split('\n') if l.strip()]
        self.assertTrue(all(len(l.strip()) >= 2 for l in lines if l.strip()))


class LongParagraphSplitTest(unittest.TestCase):
    """长段落切分"""

    def test_long_paragraph_split(self):
        long_text = "这是一句话。" * 100  # 远超 500 字
        result = clean.clean_text(long_text)
        lines = [l for l in result.split('\n') if l.strip()]
        self.assertTrue(len(lines) > 1)


class CorrectionTest(unittest.TestCase):
    """纠错替换"""

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_corrections_applied(self, mock_load):
        mock_load.return_value = [
            {"wrong": "青维", "right": "青梅"},
            {"wrong": "理想电机", "right": "理想电竞"},
        ]
        result = clean.apply_corrections("青维今天去散步，讨论理想电机的问题。")
        self.assertIn("青梅", result)
        self.assertNotIn("青维", result)
        self.assertIn("理想电竞", result)

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_correction_skips_explanatory_line(self, mock_load):
        """如果一行同时有错词和正词（解释句），不替换"""
        mock_load.return_value = [{"wrong": "青维", "right": "青梅"}]
        text = "青维其实应该是青梅"
        result = clean.apply_corrections(text)
        # 同时出现了错词和正词，应该跳过
        self.assertIn("青维", result)


class FullPipelineTest(unittest.TestCase):
    """完整清洗流程"""

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_full_pipeline(self, mock_corrections):
        mock_corrections.return_value = [{"wrong": "青维", "right": "青梅"}]

        raw = (
            "我这就为您转写这段音频\n"
            "## 10:00\n\n"
            "嗯。\n"
            "嗯\n"
            "青维今天去散步了，[音乐] 开心得很。\n"
            "青维今天去散步了，[音乐] 开心得很。\n"  # 重复行
            "\n## 11:00\n\n"
            "好的内容在这里\n"
        )
        result = clean.clean_text(raw)

        # 验证清洗效果
        self.assertIn("## 10:00", result)          # 时间头保留
        self.assertIn("## 11:00", result)           # 时间头保留
        self.assertNotIn("为您转写", result)         # AI 前缀删除
        self.assertNotIn("[音乐]", result)           # 音乐标记删除
        self.assertIn("青梅", result)                # 纠错生效
        self.assertNotIn("青维", result)             # 错词被替换
        self.assertEqual(result.count("开心得很"), 1) # 重复行去重
        self.assertIn("好的内容在这里", result)       # 正常内容保留

    def test_no_api_key_needed(self):
        """规则引擎不需要 API key"""
        result = clean.clean_text("嗯\n正常内容")
        self.assertIn("正常内容", result)


if __name__ == "__main__":
    unittest.main()
