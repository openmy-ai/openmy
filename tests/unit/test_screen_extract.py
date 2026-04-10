#!/usr/bin/env python3
import unittest

from openmy.services.extraction.extractor import apply_screen_context_to_payload


class TestScreenExtract(unittest.TestCase):
    def test_screen_summary_can_fill_project_hint_and_emit_completion_candidates(self):
        payload = {
            "daily_summary": "今天主要在改代码。",
            "intents": [
                {
                    "intent_id": "intent_001",
                    "kind": "action_item",
                    "what": "这个我待会儿弄",
                    "status": "open",
                    "who": {"kind": "user", "label": "我"},
                    "confidence_label": "medium",
                    "confidence_score": 0.7,
                    "evidence_quote": "这个我待会儿弄",
                    "source_scene_id": "scene_001",
                    "topic": "待处理",
                    "project_hint": "",
                    "due": {"raw_text": ""},
                }
            ],
            "facts": [],
        }
        scenes = [
            {
                "scene_id": "scene_001",
                "screen_context": {
                    "summary": "当时正在 Cursor 修改 OpenMy 的屏幕上下文主链",
                    "primary_app": "Cursor",
                    "tags": ["development"],
                    "completion_candidates": [
                        {
                            "kind": "saved",
                            "label": "保存成功",
                            "confidence": 0.9,
                            "evidence": "保存成功",
                        }
                    ],
                },
            }
        ]

        enriched = apply_screen_context_to_payload(payload, scenes)

        self.assertEqual(enriched["intents"][0]["project_hint"], "OpenMy")
        self.assertEqual(enriched["screen_evidence"][0]["primary_app"], "Cursor")
        self.assertEqual(enriched["completion_candidates"][0]["kind"], "saved")


if __name__ == "__main__":
    unittest.main()
