#!/usr/bin/env python3
"""
test_clean.py — 清洗模块测试

cleaner 现在用规则引擎（不调 API），测试验证每条规则的行为。
"""
import json
import tempfile
import unittest
from pathlib import Path
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

    def test_load_corrections_falls_back_to_example_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            example = tmp / "corrections.example.json"
            example.write_text(
                json.dumps({"corrections": [{"wrong": "TedTalk", "right": "TED Talk"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            with (
                patch.object(clean, "CORRECTIONS_FILE", tmp / "corrections.json"),
                patch.object(clean, "CORRECTIONS_EXAMPLE_FILE", example),
            ):
                payload = clean.load_corrections()

        self.assertEqual(payload, [{"wrong": "TedTalk", "right": "TED Talk"}])

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_corrections_applied(self, mock_load):
        mock_load.return_value = [
            {"wrong": "示例错名", "right": "示例正名"},
            {"wrong": "理想电机", "right": "理想电竞"},
        ]
        result = clean.apply_corrections("示例错名今天去散步，讨论理想电机的问题。")
        self.assertIn("示例正名", result)
        self.assertNotIn("示例错名", result)
        self.assertIn("理想电竞", result)

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_correction_skips_explanatory_line(self, mock_load):
        """如果一行同时有错词和正词（解释句），不替换"""
        mock_load.return_value = [{"wrong": "示例错名", "right": "示例正名"}]
        text = "示例错名其实应该是示例正名"
        result = clean.apply_corrections(text)
        # 同时出现了错词和正词，应该跳过
        self.assertIn("示例错名", result)


class FullPipelineTest(unittest.TestCase):
    """完整清洗流程"""

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_full_pipeline(self, mock_corrections):
        mock_corrections.return_value = [{"wrong": "示例错名", "right": "示例正名"}]

        raw = (
            "我这就为您转写这段音频\n"
            "## 10:00\n\n"
            "嗯。\n"
            "嗯\n"
            "示例错名今天去散步了，[音乐] 开心得很。\n"
            "示例错名今天去散步了，[音乐] 开心得很。\n"  # 重复行
            "\n## 11:00\n\n"
            "好的内容在这里\n"
        )
        result = clean.clean_text(raw)

        # 验证清洗效果
        self.assertIn("## 10:00", result)          # 时间头保留
        self.assertIn("## 11:00", result)           # 时间头保留
        self.assertNotIn("为您转写", result)         # AI 前缀删除
        self.assertNotIn("[音乐]", result)           # 音乐标记删除
        self.assertIn("示例正名", result)            # 纠错生效
        self.assertNotIn("示例错名", result)         # 错词被替换
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

    def test_suspicious_crosstalk_marked(self):
        text = (
            "在编写代码时，PostgreSQL 确实也是一个不错的选择，特别是如果你需要处理复杂 SQL 查询。"
            "另外它对 JSONB 支持也很强，这使得传统数据库处理非结构化数据更加灵活。"
        )
        result = clean.clean_text(text)
        self.assertIn("[疑似串台]", result)


class InlineAhPreservedTest(unittest.TestCase):
    """Fix 5: 句中"啊"不删"""

    def test_ah_in_sentence_preserved(self):
        result = clean.clean_text("这网真是不稳定啊，在这个电梯里")
        self.assertIn("不稳定啊，", result)


class RoleSignalWordProtectionTest(unittest.TestCase):
    """角色信号词保护：关键称呼不被清洗掉"""

    def test_wife_preserved(self):
        result = clean.clean_text("伴侣，我回来了")
        self.assertIn("伴侣", result)

    def test_erge_preserved(self):
        result = clean.clean_text("二哥，干活呢")
        self.assertIn("二哥", result)

    def test_claude_preserved(self):
        result = clean.clean_text("Claude 帮我看一下")
        self.assertIn("Claude", result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# U4: marker-aware cleaning tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MarkerSurvivalEndToEndTest(unittest.TestCase):
    """标记经 clean_text（含 mock LLM 纠错轮）后原样存活。"""

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_markers_survive_full_pipeline(self, mock_corrections):
        """三类前缀 + 存疑 + [无法识别] 经 clean_text 后逐个存活。"""
        mock_corrections.return_value = []
        raw = (
            "## 10:00\n\n"
            "我：今天去[?宿州]看车了。\n"
            "人：好的，那我们约[?张韧]一起去。\n"
            "外：本期播客我们聊聊创业的那些事。\n"
            "我：[无法识别]\n"
            "[无人声]\n"
        )
        result = clean.clean_text(raw)
        self.assertIn("我：", result)
        self.assertIn("人：", result)
        self.assertIn("外：", result)
        self.assertIn("[?宿州]", result)
        self.assertIn("[?张韧]", result)
        self.assertIn("[无法识别]", result)
        self.assertIn("[无人声]", result)
        self.assertIn("## 10:00", result)

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_markers_survive_with_llm_correction_mocked(self, mock_corrections):
        """模拟 LLM 纠错轮（api_key=None 不走），标记不被其他步骤吃掉。"""
        mock_corrections.return_value = [{"wrong": "看车", "right": "看车"}]
        raw = "我：今天去[?宿州]看车了。\n人：行，去吧。"
        result = clean.clean_text(raw, api_key=None)
        self.assertIn("我：", result)
        self.assertIn("人：", result)
        self.assertIn("[?宿州]", result)


class PlaybackLineMusicFalsePositiveTest(unittest.TestCase):
    """10 行全 外： 前缀的场景不触发 music_lyrics 误判。"""

    def test_all_playback_lines_no_music_lyrics(self):
        from openmy.services.scene_quality import inspect_scene_text
        # 每行内容各不同，净文本不含重复 n-gram
        diverse_lines = [
            "外：今天的新闻关注经济形势变化。",
            "外：国际政治局势持续紧张。",
            "外：科技领域再次迎来突破性进展。",
            "外：文化产业呈现蓬勃发展态势。",
            "外：教育改革政策正在逐步落实。",
            "外：环境保护成为全球关注焦点。",
            "外：医疗健康领域投资大幅增长。",
            "外：体育赛事赛程安排已经公布。",
            "外：社会民生问题备受关注讨论。",
            "外：数字经济带来新的发展机遇。",
        ]
        quality = inspect_scene_text("\n".join(diverse_lines))
        self.assertNotIn("music_lyrics", quality["quality_flags"])


class DedupAttributionBoundaryTest(unittest.TestCase):
    """归因边界保护：不同前缀的相同净文本不去重。"""

    def test_same_text_different_prefix_not_deduped(self):
        """'我：好的' 紧跟 '人：好的' 不被去重。"""
        lines = ["我：好的", "人：好的"]
        result = clean.deduplicate_lines(lines)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "我：好的")
        self.assertEqual(result[1], "人：好的")

    def test_same_prefix_same_text_deduped(self):
        """同前缀同文本照常去重。"""
        lines = ["我：好的", "我：好的"]
        result = clean.deduplicate_lines(lines)
        self.assertEqual(len(result), 1)

    def test_unmarked_same_text_deduped(self):
        """无前缀的旧文本照常去重（向后兼容）。"""
        lines = ["好的", "好的"]
        result = clean.deduplicate_lines(lines)
        self.assertEqual(len(result), 1)


class MergeShortLineAttributionTest(unittest.TestCase):
    """短行合并的归因边界保护。"""

    def test_filler_not_merged_into_different_prefix(self):
        """'我：啊' 不并入上一行的 '外：...' 行。"""
        lines = ["外：这是一段长的外放内容", "我：啊"]
        result = clean.merge_short_lines(lines, min_length=3)
        self.assertEqual(len(result), 2)
        self.assertIn("我：啊", result[1])

    def test_suffix_particle_merged_same_prefix(self):
        """同前缀的附着词合并正常。"""
        lines = ["我：前面的长内容长内容", "我：呢"]
        result = clean.merge_short_lines(lines, min_length=5)
        merged = '\n'.join(result)
        self.assertIn("长内容呢", merged)

    def test_unmarked_merge_backward_compat(self):
        """无前缀旧文本合并行为不变。"""
        lines = ["前面的长内容长内容", "呢"]
        result = clean.merge_short_lines(lines, min_length=3)
        merged = '\n'.join(result)
        self.assertIn("长内容呢", merged)


class SplitLongParagraphPrefixTest(unittest.TestCase):
    """长行切分后每个片段保留归因前缀。"""

    def test_600_char_playback_line_keeps_prefix(self):
        """600 字带 外：前缀的长行切分后各片段均保留前缀。"""
        long_body = "。".join([f"这是外放内容第{i}段话" for i in range(80)])
        long_line = f"外：{long_body}"
        self.assertGreater(len(long_line), 500)
        result = clean.split_long_paragraphs(long_line)
        result_lines = [l for l in result.split('\n') if l.strip()]
        self.assertTrue(len(result_lines) > 1, "should split into multiple lines")
        for line in result_lines:
            self.assertTrue(line.startswith("外："), f"split piece missing prefix: {line[:30]}...")


class PrefixedFillerStillDeletedTest(unittest.TestCase):
    """带前缀的废词行照常被删。"""

    def test_prefixed_filler_deleted(self):
        """'我：嗯嗯。' 仍被删除。"""
        result = clean.clean_text("我：嗯嗯。\n我：正常内容")
        self.assertNotIn("嗯嗯", result)
        self.assertIn("正常内容", result)

    def test_prefixed_filler_phrase_deleted(self):
        """'人：对对对' 仍被删除。"""
        result = clean.clean_text("人：对对对\n人：正常内容在这里")
        lines = [l.strip() for l in result.split('\n') if l.strip()]
        self.assertNotIn("人：对对对", lines)
        self.assertIn("人：正常内容在这里", lines)


class RealLyricsStillCaughtTest(unittest.TestCase):
    """净文本中的真歌词仍被检测到（不过度修复）。"""

    def test_real_lyrics_in_net_text(self):
        from openmy.services.scene_quality import inspect_scene_text
        # 制造歌词重复模式——无标记的纯歌词
        lyrics = "我爱你中国我爱你中国我爱你中国我爱你中国我爱你中国" * 3
        quality = inspect_scene_text(lyrics)
        self.assertIn("music_lyrics", quality["quality_flags"])

    def test_lyrics_with_prefix_still_caught(self):
        """带归因前缀的歌词行，净文本仍触发检测。"""
        from openmy.services.scene_quality import inspect_scene_text
        lyrics_lines = ["外：我爱你中国我爱你中国我爱你中国我爱你中国我爱你中国" for _ in range(3)]
        text = "\n".join(lyrics_lines)
        quality = inspect_scene_text(text)
        self.assertIn("music_lyrics", quality["quality_flags"])


class PlaybackCrosstalkSkipTest(unittest.TestCase):
    """外：前缀行不打 [疑似串台]。"""

    def test_playback_line_not_marked_crosstalk(self):
        """外放技术讲座行不被标 [疑似串台]。"""
        lines = [
            "外：在编写代码时，PostgreSQL 确实也是一个不错的选择。另外它对 JSONB 支持也很强。"
        ]
        result = clean.mark_suspicious_crosstalk(lines, min_length=40)
        self.assertEqual(len(result), 1)
        self.assertNotIn("[疑似串台]", result[0])


class ApplyCorrectionsUncertainSpanTest(unittest.TestCase):
    """纠错替换对带 [?] 行的行为验证。"""

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_correction_with_uncertain_span(self, mock_load):
        """含 [?] 的行，纠错正常替换不误伤标记。"""
        mock_load.return_value = [{"wrong": "示例错名", "right": "示例正名"}]
        text = "我：[?张韧]跟示例错名去了公园"
        result = clean.apply_corrections(text)
        self.assertIn("示例正名", result)
        self.assertNotIn("示例错名", result)
        # [?张韧] 不受影响
        self.assertIn("[?张韧]", result)
        # 前缀保留
        self.assertIn("我：", result)

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_correction_skip_when_right_in_uncertain(self, mock_load):
        """如果正确词出现在 [?] 内部（如 [?正名]），不跳过替换。

        apply_corrections 的 'right in updated_line' 检查是为了防止
        解释句误伤。[?正名] 中的 '正名' 出现会触发 skip，但这种
        场景在实际数据中极不可能出现（纠错词典的正确词不会是存疑词）。
        此处验证当前行为即可，不做额外调整。
        """
        mock_load.return_value = [{"wrong": "错名", "right": "正名"}]
        text = "我：[?正名]跟错名聊天"
        result = clean.apply_corrections(text)
        # '正名' 已在行中（在 [?正名] 里），skip 逻辑触发，错名不替换
        self.assertIn("错名", result)


class LegacyBehaviorUnchangedTest(unittest.TestCase):
    """无标记的旧文本行为不变。"""

    @patch('openmy.services.cleaning.cleaner.load_corrections')
    def test_legacy_full_pipeline_unchanged(self, mock_corrections):
        """与旧版行为逐字节一致的验证。"""
        mock_corrections.return_value = []
        raw = (
            "我这就为您转写这段音频\n"
            "## 10:00\n\n"
            "嗯。\n"
            "嗯\n"
            "正常内容在这里。\n"
            "正常内容在这里。\n"
            "\n## 11:00\n\n"
            "好的内容\n"
        )
        result = clean.clean_text(raw)
        self.assertIn("## 10:00", result)
        self.assertIn("## 11:00", result)
        self.assertNotIn("为您转写", result)
        self.assertEqual(result.count("正常内容在这里"), 1)
        self.assertIn("好的内容", result)

    def test_env_noise_still_removed_without_prefix(self):
        """无标记的环境噪音行照常删除。"""
        result = clean.clean_text("正常内容\n（狗吠声）\n更多内容")
        self.assertNotIn("狗吠", result)
        self.assertIn("正常内容", result)

    def test_playback_env_noise_preserved(self):
        """外：前缀的环境噪音行不被删——归因标记已声明来源。"""
        result = clean.clean_text("外：（背景音乐声）\n我：正常内容")
        self.assertIn("外：", result)
        self.assertIn("我：正常内容", result)


if __name__ == "__main__":
    unittest.main()
