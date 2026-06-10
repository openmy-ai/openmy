#!/usr/bin/env python3
"""markers.py 单测：标记解析单一来源（U3）。"""
import unittest

from openmy.services import markers


class ParseAttributionTest(unittest.TestCase):
    def test_three_prefixes(self):
        self.assertEqual(markers.parse_attribution("我：明天去看车"), (markers.SOURCE_WEARER, "明天去看车"))
        self.assertEqual(markers.parse_attribution("人：好的"), (markers.SOURCE_OTHERS, "好的"))
        self.assertEqual(markers.parse_attribution("外：本期播客我们聊聊"), (markers.SOURCE_PLAYBACK, "本期播客我们聊聊"))

    def test_unmarked_line(self):
        source, body = markers.parse_attribution("没有前缀的旧转写")
        self.assertEqual(source, markers.SOURCE_UNMARKED)
        self.assertEqual(body, "没有前缀的旧转写")

    def test_leading_whitespace_tolerated(self):
        source, body = markers.parse_attribution("  我：缩进的行")
        self.assertEqual(source, markers.SOURCE_WEARER)
        self.assertEqual(body, "缩进的行")


class StripMarkersTest(unittest.TestCase):
    def test_strips_prefix_and_uncertain(self):
        self.assertEqual(markers.strip_markers("我：明天去[?宿州]看车"), "明天去宿州看车")

    def test_nested_same_line(self):
        # 前缀 + 多个存疑同行
        self.assertEqual(
            markers.strip_markers("人：他说[?张韧]要去[?瓦矿]上班"),
            "他说张韧要去瓦矿上班",
        )

    def test_unrecognized_and_no_speech_preserved(self):
        self.assertEqual(markers.strip_markers("人：[无法识别]"), "[无法识别]")
        self.assertEqual(markers.strip_markers("[无人声]"), "[无人声]")

    def test_legacy_text_returned_unchanged(self):
        legacy = "没有任何新标记的旧转写文本。\n[无法识别]也保持原样。"
        self.assertEqual(markers.strip_markers(legacy), legacy)

    def test_unclosed_uncertain_closed_at_eol(self):
        self.assertEqual(markers.strip_markers("我：明天去[?宿州"), "明天去宿州")

    def test_empty_uncertain_dropped(self):
        self.assertEqual(markers.strip_markers("我：明天[?]去"), "明天去")


class StripUncertainReplacementTest(unittest.TestCase):
    def test_replace_with_unrecognized_for_distillation(self):
        # 蒸馏前确定性排除：[?X] → [无法识别]
        self.assertEqual(
            markers.strip_uncertain_marks("明天去[?宿州]看车", replace_with_content=False),
            "明天去[无法识别]看车",
        )

    def test_unclosed_also_replaced(self):
        self.assertEqual(
            markers.strip_uncertain_marks("明天去[?宿州", replace_with_content=False),
            "明天去[无法识别]",
        )


class IterUncertainSpansTest(unittest.TestCase):
    def test_multiple_same_line_and_cross_line(self):
        text = "我：去[?宿州]看[?GL8]\n人：好的\n人：[?郑晚秋]也去"
        spans = list(markers.iter_uncertain_spans(text))
        self.assertEqual([s.text for s in spans], ["宿州", "GL8", "郑晚秋"])
        self.assertEqual([s.line_index for s in spans], [0, 0, 2])
        self.assertEqual(spans[0].raw, "[?宿州]")

    def test_unrecognized_not_treated_as_uncertain(self):
        spans = list(markers.iter_uncertain_spans("人：[无法识别]\n我：真的[?么]"))
        self.assertEqual([s.text for s in spans], ["么"])

    def test_unclosed_yielded(self):
        spans = list(markers.iter_uncertain_spans("我：去[?宿州"))
        self.assertEqual(spans[0].text, "宿州")
        self.assertEqual(spans[0].raw, "[?宿州")

    def test_context_is_clean_text(self):
        spans = list(markers.iter_uncertain_spans("我：明天去[?宿州]看车"))
        self.assertEqual(spans[0].line_text, "明天去宿州看车")


class HasAttributionMarkersTest(unittest.TestCase):
    def test_detects_markers(self):
        self.assertTrue(markers.has_attribution_markers("我：你好\n人：你好"))

    def test_legacy_text_has_none(self):
        self.assertFalse(markers.has_attribution_markers("旧转写一行\n另一行 [无法识别]"))


if __name__ == "__main__":
    unittest.main()
