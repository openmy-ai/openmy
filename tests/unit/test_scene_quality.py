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

    def test_detects_assistant_reply_tail(self):
        quality = inspect_scene_text(
            "你把它这个用户门槛，为什么我今天我真的累了，我去审核的时候发现有这么多的问题。"
            "请提供您需要转写的音频文件。目前我无法直接接收或播放音频文件，请您将音频的内容粘贴在这里。"
        )
        self.assertTrue(quality["suspicious_content"])
        self.assertIn("assistant_reply", quality["quality_flags"])

    def test_detects_low_signal_fragment(self):
        quality = inspect_scene_text("Claude")
        self.assertFalse(quality["suspicious_content"])
        self.assertIn("low_signal_fragment", quality["quality_flags"])
        self.assertFalse(quality["usable_for_downstream"])

    def test_annotate_scene_payload_keeps_normal_scene_usable(self):
        scene = annotate_scene_payload({"scene_id": "s01", "text": "今天继续推进 OpenMy 的前端可读性。"})
        self.assertTrue(scene["usable_for_downstream"])
        self.assertTrue(scene_is_usable_for_downstream(scene))


class TestMarkerAwareSceneQuality(unittest.TestCase):
    """U4: 标记防误伤——质量检测按净文本判定。"""

    def test_all_playback_tech_lecture_stays_usable(self):
        """全场 外：技术讲解场景不被 technical_crosstalk 拦下。"""
        text = (
            "外：最近我看了一个 TED Talk，还看了 PostgreSQL 的演示。\n"
            "外：里面一直在讲 SQL 和 JSONB，这些数据库特性让我觉得很有意思。"
        )
        quality = inspect_scene_text(text)
        self.assertNotIn("technical_crosstalk", quality["quality_flags"])
        self.assertFalse(quality["suspicious_content"])
        self.assertTrue(quality["usable_for_downstream"])

    def test_all_playback_lines_no_music_lyrics_false_positive(self):
        """10 行 外：前缀的场景——前缀字符重复不触发 music_lyrics。"""
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

    def test_uncertain_spans_not_counted_as_garbled(self):
        """[?词] 不计入 [无法识别] 占比。"""
        # 5 行中只有 1 行是真 [无法识别]，其余是存疑
        lines = [
            "我：今天去了[?宿州]",
            "人：[?张韧]也去了",
            "我：[无法识别]",
            "人：[?GL8]不错",
            "我：好的那就这样",
        ]
        quality = inspect_scene_text("\n".join(lines))
        self.assertNotIn("low_quality_garbled", quality["quality_flags"])

    def test_playback_assistant_reply_not_flagged(self):
        """外：行含助手回复固定腔不被标为 assistant_reply。"""
        text = "外：请提供您需要转写的音频文件。我无法直接接收或播放音频文件。"
        quality = inspect_scene_text(text)
        self.assertNotIn("assistant_reply", quality["quality_flags"])
        self.assertFalse(quality["suspicious_content"])

    def test_mixed_playback_and_wearer_tech_scene(self):
        """混合场景：外：行有技术词，我：行有正常内容——不被标 technical_crosstalk。"""
        text = (
            "外：这个 PostgreSQL 的 JSONB 功能很强大。\n"
            "我：听起来不错。"
        )
        quality = inspect_scene_text(text)
        # 只看非外放行——"听起来不错"没有技术词
        self.assertNotIn("technical_crosstalk", quality["quality_flags"])

    def test_real_lyrics_still_caught_with_markers(self):
        """带标记的真歌词净文本仍触发 music_lyrics。"""
        lyric = "我爱你中国我爱你中国我爱你中国我爱你中国"
        lines = [f"外：{lyric}" for _ in range(3)]
        quality = inspect_scene_text("\n".join(lines))
        self.assertIn("music_lyrics", quality["quality_flags"])

    def test_legacy_scene_unchanged(self):
        """无标记的旧场景行为不变。"""
        quality = inspect_scene_text("今天继续推进 OpenMy 的前端可读性。")
        self.assertTrue(quality["usable_for_downstream"])
        self.assertEqual(quality["quality_flags"], [])

    def test_legacy_tech_crosstalk_still_detected(self):
        """无标记的技术串台场景仍被检测。"""
        quality = inspect_scene_text(
            "最近我看了一个 TED Talk，还看了 PostgreSQL 的演示，里面一直在讲 SQL 和 JSONB。"
            " 这些数据库特性让我觉得很有意思。"
        )
        self.assertIn("technical_crosstalk", quality["quality_flags"])
