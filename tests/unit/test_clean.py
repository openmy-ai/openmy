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

    def test_suffix_particle_merged(self):
        """Fix 1: 句尾附着词（啊、呀、呢）合并到上一行"""
        # 直接测 merge_short_lines，不走完整清洗流程（避免 filler 先删掉）
        lines = ["前面的长内容长内容", "呢", "后面的长内容"]
        result = clean.merge_short_lines(lines, min_length=3)
        merged = '\n'.join(result)
        self.assertIn("长内容呢", merged)

    def test_reply_word_stays_independent(self):
        """Fix 1: 回合词（好、对、行）保持独立行"""
        result = clean.clean_text("你觉得怎么样？\n好\n那就这样吧")
        lines = [l for l in result.split('\n') if l.strip()]
        self.assertIn("好", [l.strip() for l in lines])


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


class ContextAwareFillerTest(unittest.TestCase):
    """Fix 2: 嗯/哦 上下文感知"""

    def test_en_after_question_preserved(self):
        """问句后面的"嗯。"是肯定回答，不删"""
        result = clean.clean_text("你确定吗？\n嗯。\n那好吧")
        self.assertIn("嗯", result)

    def test_en_standalone_removed(self):
        """没有问句时，独立的"嗯。"是废词，删掉"""
        result = clean.clean_text("今天天气不错\n嗯。\n明天也不错")
        # "嗯。" 前面不是问句，应该被删
        lines = [l.strip() for l in result.split('\n') if l.strip()]
        self.assertNotIn("嗯。", lines)


class EnvNoiseTest(unittest.TestCase):
    """Fix 3: 环境噪音行清除"""

    def test_noise_in_parens_removed(self):
        result = clean.clean_text("正常内容\n（狗吠声）\n更多内容")
        self.assertNotIn("狗吠", result)
        self.assertIn("正常内容", result)

    def test_noise_in_brackets_removed(self):
        result = clean.clean_text("正常内容\n（背景粤语对话）\n更多内容")
        self.assertNotIn("背景", result)

    def test_normal_parens_preserved(self):
        """普通括号内容不删"""
        result = clean.clean_text("这是（非常重要的）内容")
        self.assertIn("非常重要", result)


class AssistantReplyTest(unittest.TestCase):
    """Fix 4: 助手回复标记"""

    def test_assistant_reply_marked(self):
        question = "你帮我看一下这个架构？"
        long_reply = "从 agent 架构来看，你的项目本质是一个上下文引擎。" + "后面补充内容。" * 10
        result = clean.clean_text(f"{question}\n{long_reply}")
        self.assertIn("[助手回复]", result)

    def test_normal_long_line_not_marked(self):
        """没有讲解式句型的长行不标记"""
        long_line = "我今天跟二哥聊了很多关于创业的话题讨论了很久很久很久很久很久很久很久很久很久。"
        result = clean.clean_text(f"你觉得呢？\n{long_line}")
        self.assertNotIn("[助手回复]", result)


class InlineAhPreservedTest(unittest.TestCase):
    """Fix 5: 句中"啊"不删"""

    def test_ah_in_sentence_preserved(self):
        result = clean.clean_text("这网真是不稳定啊，在这个电梯里")
        self.assertIn("不稳定啊，", result)


class RoleSignalWordProtectionTest(unittest.TestCase):
    """角色信号词保护：关键称呼不被清洗掉"""

    def test_wife_preserved(self):
        result = clean.clean_text("老婆，我回来了")
        self.assertIn("老婆", result)

    def test_erge_preserved(self):
        result = clean.clean_text("二哥，干活呢")
        self.assertIn("二哥", result)

    def test_claude_preserved(self):
        result = clean.clean_text("Claude 帮我看一下")
        self.assertIn("Claude", result)


if __name__ == "__main__":
    unittest.main()
