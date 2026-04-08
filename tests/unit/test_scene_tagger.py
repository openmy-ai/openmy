#!/usr/bin/env python3
"""test_scene_tagger.py — 场景切分和角色标注测试"""

import unittest

from openmy.domain.models import RoleTag, SceneBlock
from openmy.services.roles.resolver import (
    ROLE_SIGNAL_WORDS,
    check_declarations,
    check_keyword_rules,
    tag_all_scenes,
    tag_scene_role,
)
from openmy.services.segmentation.segmenter import parse_time_segments, split_into_scenes


class TestParseTimeSegments(unittest.TestCase):
    def test_basic(self):
        md = "## 12:12\n\n你好老婆\n\n## 13:00\n\n去买菜"
        segs = parse_time_segments(md)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["time"], "12:12")
        self.assertEqual(segs[1]["time"], "13:00")

    def test_no_time_headers(self):
        md = "就是一段纯文本"
        segs = parse_time_segments(md)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["time"], "00:00")

    def test_empty_segment_skipped(self):
        md = "## 12:00\n\n## 13:00\n\n有内容"
        segs = parse_time_segments(md)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["time"], "13:00")


class TestDeclarations(unittest.TestCase):
    def test_wife_declaration(self):
        result = check_declarations("报告老婆，我到了")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "interpersonal")
        self.assertGreater(result[1], 0.9)

    def test_ai_declaration(self):
        result = check_declarations("小小得，主家你好，播放音乐")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "ai")

    def test_merchant_declaration(self):
        result = check_declarations("老板，来两碗面")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "merchant")

    def test_pet_declaration(self):
        result = check_declarations("嗨，小狗，过来")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "pet")

    def test_no_declaration(self):
        result = check_declarations("今天天气真好")
        self.assertIsNone(result)


class TestKeywordRules(unittest.TestCase):
    def test_ai_keywords(self):
        result = check_keyword_rules("这个 Claude 的 prompt 要改一下")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "ai")

    def test_merchant_keywords(self):
        result = check_keyword_rules("物流单号发给他，快递明天到")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "merchant")

    def test_pet_keywords(self):
        result = check_keyword_rules("今天遛狗回来买了狗粮")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "pet")

    def test_self_keywords(self):
        result = check_keyword_rules("我得先把这个记一下，待会儿处理")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "self")

    def test_no_keywords(self):
        result = check_keyword_rules("今天天气真好")
        self.assertIsNone(result)


class TestInheritance(unittest.TestCase):
    def test_inherits_from_previous(self):
        scene = SceneBlock(scene_id="s02", text="好的没问题那就这样")
        prev_role = RoleTag(
            scene_type="merchant",
            scene_type_label="跟商家",
            confidence=0.85,
            source="rule_matched",
            source_label="一看就知道",
        )
        tag_scene_role(scene, prev_role)
        self.assertEqual(scene.role.scene_type, "merchant")
        self.assertEqual(scene.role.source, "inherited")
        self.assertLess(scene.role.confidence, prev_role.confidence)

    def test_no_inherit_from_low_confidence(self):
        scene = SceneBlock(scene_id="s02", text="天气真好")
        prev_role = RoleTag(
            scene_type="merchant",
            scene_type_label="跟商家",
            confidence=0.3,
        )
        tag_scene_role(scene, prev_role)
        self.assertEqual(scene.role.scene_type, "uncertain")

    def test_no_inherit_from_uncertain(self):
        scene = SceneBlock(scene_id="s02", text="天气真好")
        prev_role = RoleTag(scene_type="uncertain", confidence=0.0)
        tag_scene_role(scene, prev_role)
        self.assertEqual(scene.role.scene_type, "uncertain")


class TestFullPipeline(unittest.TestCase):
    def test_mixed_conversation(self):
        md = """## 12:00

小小得，主家你好，播放音乐。

## 12:30

报告老婆，我到了，你在哪

## 13:00

老板，来两碗蒸菜，一碗胡辣汤

## 13:30

这个烧饼真好吃
"""
        segs = parse_time_segments(md)
        scenes = split_into_scenes(segs)
        scenes = tag_all_scenes(scenes)

        self.assertEqual(len(scenes), 4)
        self.assertEqual(scenes[0].role.scene_type, "ai")
        self.assertEqual(scenes[0].role.source, "declared")
        self.assertEqual(scenes[1].role.scene_type, "interpersonal")
        self.assertEqual(scenes[2].role.scene_type, "merchant")
        self.assertEqual(scenes[3].role.scene_type, "merchant")
        self.assertEqual(scenes[3].role.source, "inherited")


class TestRoleSignalWords(unittest.TestCase):
    def test_signal_words_exist(self):
        self.assertGreater(len(ROLE_SIGNAL_WORDS), 20)

    def test_key_words_included(self):
        for word in ["老婆", "老公", "客服", "乖", "小狗", "记一下"]:
            self.assertIn(word, ROLE_SIGNAL_WORDS, f"缺少关键信号词: {word}")


if __name__ == "__main__":
    unittest.main()
