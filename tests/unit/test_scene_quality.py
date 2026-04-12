#!/usr/bin/env python3
import unittest

from openmy.services.scene_quality import annotate_scene_payload, inspect_scene_text, scene_is_usable_for_downstream


class TestSceneQuality(unittest.TestCase):
    def test_detects_assistant_reply(self):
        quality = inspect_scene_text("请提供您需要转写的音频文件。目前我无法直接接收或播放音频文件。")
        self.assertTrue(quality["suspicious_content"])
        self.assertIn("assistant_reply", quality["quality_flags"])

    def test_detects_technical_crosstalk(self):
        quality = inspect_scene_text(
            "最近我看了一个 TED Talk，还看了 PostgreSQL 的演示，里面一直在讲 SQL 和 JSONB。"
            " 这些数据库特性让我觉得很有意思。"
        )
        self.assertTrue(quality["suspicious_content"])
        self.assertIn("technical_crosstalk", quality["quality_flags"])

    def test_detects_report_sample_about_data_sources(self):
        quality = inspect_scene_text(
            "我来给你展示一下，其实它就是非常简单。你可以看到，我这里已经有了两个数据源。"
            "接下来我就需要创建一个订阅，然后把这些数据同步过去。"
        )
        self.assertTrue(quality["suspicious_content"])
        self.assertIn("technical_crosstalk", quality["quality_flags"])

    def test_detects_mixed_real_and_crosstalk_segment(self):
        quality = inspect_scene_text(
            "你帮我看一下这个OMX是不是在原地打转啊，他为什么一直没让我提交呢？"
            "今天他妈的这个事太多了。Claude 现在的性能比去年好多了，你看过最新的 TED Talk 吗？"
            "关于数据库的，提到 Postgres 架构的部分我觉得非常有意思。"
        )
        self.assertTrue(quality["suspicious_content"])
        self.assertIn("technical_crosstalk", quality["quality_flags"])

    def test_detects_low_signal_fragment(self):
        quality = inspect_scene_text("Claude")
        self.assertFalse(quality["suspicious_content"])
        self.assertIn("low_signal_fragment", quality["quality_flags"])
        self.assertFalse(quality["usable_for_downstream"])

    def test_annotate_scene_payload_keeps_normal_scene_usable(self):
        scene = annotate_scene_payload({"scene_id": "s01", "text": "今天继续推进 OpenMy 的前端可读性。"})
        self.assertTrue(scene["usable_for_downstream"])
        self.assertTrue(scene_is_usable_for_downstream(scene))
