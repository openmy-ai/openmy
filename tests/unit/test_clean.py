#!/usr/bin/env python3
import unittest

from daytape.services.cleaning import cleaner as clean


class CleanLyricsTest(unittest.TestCase):
    def test_removes_long_english_lyric_sentence(self):
        text = (
            "这是中文说明。 "
            "I love you like a love song baby I love you like a love song baby. "
            "这里继续中文讨论。"
        )
        cleaned = clean.clean_text(text)
        self.assertIn("这是中文说明", cleaned)
        self.assertIn("这里继续中文讨论", cleaned)
        self.assertNotIn("love song", cleaned)

    def test_keeps_product_terms_and_short_english_phrases(self):
        text = "这个插件里面有个配置叫 Cloud AI。然后 window mover 这个插件也要看一下。"
        cleaned = clean.clean_text(text)
        self.assertIn("Cloud AI", cleaned)
        self.assertIn("window mover", cleaned)

    def test_removes_lyric_sentence_without_spaces_after_periods(self):
        text = "这是中文说明。I love you like a love song baby.这里继续中文讨论。"
        cleaned = clean.clean_text(text)
        self.assertIn("这是中文说明", cleaned)
        self.assertIn("这里继续中文讨论", cleaned)
        self.assertNotIn("love song", cleaned)

    def test_removes_mostly_english_chorus_paragraph(self):
        text = (
            "I I, there's no place I'd rather be. I I, there's no place I'd rather be.\n\n"
            "我们还是先把技能书插件做好。"
        )
        cleaned = clean.clean_text(text)
        self.assertNotIn("there's no place", cleaned)
        self.assertIn("我们还是先把技能书插件做好", cleaned)

    def test_removes_short_english_fragments_inside_lyric_paragraph(self):
        text = (
            "先说中文需求。 "
            "I love you like a love song baby. "
            "And I keep hitting you. "
            "然后继续说中文结论。"
        )
        cleaned = clean.clean_text(text)
        self.assertIn("先说中文需求", cleaned)
        self.assertIn("然后继续说中文结论", cleaned)
        self.assertNotIn("I keep hitting you", cleaned)

    def test_removes_single_word_english_fragments_in_lyric_context(self):
        text = "先说中文。 I love you like a love song baby. Oh, yeah. Stay. 然后继续中文。"
        cleaned = clean.clean_text(text)
        self.assertIn("先说中文", cleaned)
        self.assertIn("然后继续中文", cleaned)
        self.assertNotIn("Oh, yeah", cleaned)
        self.assertNotIn("Stay", cleaned)


class CleanMusicMarkerTest(unittest.TestCase):
    def test_removes_pure_music_marker_line(self):
        text = "这是中文口述。\n[音乐]\n继续说话。"
        cleaned = clean.clean_text(text)
        self.assertIn("这是中文口述", cleaned)
        self.assertIn("继续说话", cleaned)
        self.assertNotIn("[音乐]", cleaned)

    def test_removes_inline_music_marker(self):
        text = "说话内容 [音乐] 然后继续说话。"
        cleaned = clean.clean_text(text)
        self.assertIn("说话内容", cleaned)
        self.assertIn("然后继续说话", cleaned)
        self.assertNotIn("[音乐]", cleaned)

    def test_removes_repeated_music_markers(self):
        text = "[音乐] [音乐] [音乐]"
        cleaned = clean.clean_text(text)
        self.assertNotIn("[音乐]", cleaned)

    def test_removes_music_marker_with_punctuation(self):
        text = "[音乐]。\n我继续说重要的事情。"
        cleaned = clean.clean_text(text)
        self.assertNotIn("[音乐]", cleaned)
        self.assertIn("我继续说重要的事情", cleaned)


class CleanTimeHeaderTest(unittest.TestCase):
    def test_preserves_time_headers(self):
        text = "## 10:40\n\n这是一段口述内容。\n\n## 11:27\n\n这是另一段口述。"
        cleaned = clean.clean_text(text)
        self.assertIn("## 10:40", cleaned)
        self.assertIn("## 11:27", cleaned)
        self.assertIn("这是一段口述内容", cleaned)

    def test_time_header_not_merged_into_previous_line(self):
        text = "说完了。\n## 14:09\n继续说话。"
        cleaned = clean.clean_text(text)
        lines = cleaned.split('\n')
        time_lines = [line for line in lines if line.strip().startswith('## 14:09')]
        self.assertEqual(len(time_lines), 1)


class SplitLongParagraphsTest(unittest.TestCase):
    def test_splits_long_paragraph(self):
        sentences = [f"这是第{i}个用来测试段落切分功能的完整句子包含足够多的汉字来确保超过阈值。" for i in range(20)]
        long_text = ''.join(sentences)
        self.assertGreater(len(long_text), 500, f"测试输入只有{len(long_text)}字")
        result = clean.split_long_paragraphs(long_text, max_chars=500)
        paragraphs = [paragraph for paragraph in result.split('\n\n') if paragraph.strip()]
        self.assertGreater(len(paragraphs), 1)

    def test_keeps_short_paragraph(self):
        text = "这是一段很短的文字。不需要切分。"
        result = clean.split_long_paragraphs(text, max_chars=500)
        paragraphs = [paragraph for paragraph in result.split('\n\n') if paragraph.strip()]
        self.assertEqual(len(paragraphs), 1)

    def test_protects_time_headers(self):
        text = "## 14:30\n\n" + "这是一段很长的文字。" * 30
        result = clean.split_long_paragraphs(text, max_chars=500)
        self.assertIn("## 14:30", result)


class BoldKeywordsTest(unittest.TestCase):
    def test_bolds_english_proper_nouns(self):
        text = "我在用 StreamDeck 配置技能书，然后用 Obsidian 做笔记。"
        result = clean.bold_keywords(text)
        self.assertIn("**StreamDeck**", result)
        self.assertIn("**Obsidian**", result)

    def test_skips_common_english_words(self):
        text = "I like this tool very much and it is good."
        result = clean.bold_keywords(text)
        self.assertNotIn("**like**", result)
        self.assertNotIn("**good**", result)
        self.assertNotIn("**this**", result)

    def test_bolds_high_freq_chinese_terms(self):
        text = "技能书很好用。我喜欢技能书。技能书是核心功能。然后技能书还能扩展。"
        result = clean.bold_keywords(text)
        self.assertIn("**技能书**", result)


class ProfanityFilterTest(unittest.TestCase):
    def test_removes_inline_profanity(self):
        text = "我操他妈这个功能太好了"
        result = clean.remove_profanity(text)
        self.assertNotIn("操", result)
        self.assertNotIn("他妈", result)
        self.assertIn("功能", result)

    def test_removes_pure_profanity_line(self):
        text = "这是正常内容。\n傻逼\n继续说话。"
        result = clean.remove_profanity(text)
        self.assertNotIn("傻逼", result)
        self.assertIn("正常内容", result)
        self.assertIn("继续说话", result)

    def test_protects_time_headers(self):
        text = "## 14:30\n我操这个太牛逼了"
        result = clean.remove_profanity(text)
        self.assertIn("## 14:30", result)
        self.assertNotIn("我操", result)
        self.assertNotIn("牛逼", result)

    def test_removes_wo_cao(self):
        text = "卧槽这也太厉害了吧"
        result = clean.remove_profanity(text)
        self.assertNotIn("卧槽", result)
        self.assertIn("厉害", result)


if __name__ == "__main__":
    unittest.main()
