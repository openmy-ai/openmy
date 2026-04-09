#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openmy.services.extraction import extractor


class TestExtractorCompatibility(unittest.TestCase):
    def make_payload(self) -> dict:
        return {
            "daily_summary": "今天主要推进 Intent 系统。",
            "events": [{"time": "11:37", "project": "OpenMy", "summary": "继续做 Intent 系统。"}],
            "intents": [
                {
                    "intent_id": "intent_user_task",
                    "kind": "action_item",
                    "what": "重写 README",
                    "status": "open",
                    "who": {"kind": "user", "label": "老板"},
                    "confidence_label": "high",
                    "confidence_score": 0.92,
                    "needs_review": False,
                    "evidence_quote": "今天把 README 重写一下。",
                    "source_scene_id": "scene_001",
                    "topic": "OpenMy",
                    "project_hint": "OpenMy",
                },
                {
                    "intent_id": "intent_agent_task",
                    "kind": "action_item",
                    "what": "同步状态到 Obsidian",
                    "status": "open",
                    "who": {"kind": "agent", "label": "Claude"},
                    "confidence_label": "high",
                    "confidence_score": 0.85,
                    "needs_review": False,
                    "evidence_quote": "让 Claude 去同步。",
                    "source_scene_id": "scene_002",
                    "topic": "OpenMy",
                    "project_hint": "OpenMy",
                },
                {
                    "intent_id": "intent_decision",
                    "kind": "decision",
                    "what": "先做 Intent，再做前端。",
                    "status": "active",
                    "who": {"kind": "user", "label": "老板"},
                    "confidence_label": "high",
                    "confidence_score": 0.88,
                    "needs_review": False,
                    "evidence_quote": "先做 Intent。",
                    "source_scene_id": "scene_003",
                    "topic": "OpenMy",
                    "project_hint": "OpenMy",
                },
                {
                    "intent_id": "intent_low",
                    "kind": "commitment",
                    "what": "回头看看这个",
                    "status": "open",
                    "who": {"kind": "user", "label": "老板"},
                    "confidence_label": "low",
                    "confidence_score": 0.31,
                    "needs_review": True,
                    "evidence_quote": "回头看看。",
                    "source_scene_id": "scene_004",
                    "topic": "杂项",
                },
            ],
            "facts": [
                {"fact_type": "idea", "content": "真正的问题是 Intent 和 facts 要分桶。", "topic": "OpenMy"},
                {"fact_type": "observation", "content": "今天高频互动对象是 AI助手。", "topic": "上下文"},
            ],
            "role_hints": [],
        }

    def test_save_meta_json_adds_legacy_compat_fields(self):
        payload = self.make_payload()

        with tempfile.TemporaryDirectory() as tmp_dir:
            extractor.save_meta_json(payload, "2026-04-08", tmp_dir)
            saved = json.loads((Path(tmp_dir) / "2026-04-08.meta.json").read_text(encoding="utf-8"))

        self.assertIn("intents", saved)
        self.assertIn("facts", saved)
        self.assertIn("legacy_todos", saved)
        self.assertIn("todos", saved)
        self.assertIn("decisions", saved)
        self.assertEqual([item["task"] for item in saved["legacy_todos"]], ["重写 README"])
        self.assertEqual([item["task"] for item in saved["todos"]], ["重写 README"])
        self.assertEqual([item["what"] for item in saved["decisions"]], ["先做 Intent，再做前端。"])
        self.assertEqual(len(saved["insights"]), 2)

    def test_distribute_to_vault_uses_intents_and_facts(self):
        payload = self.make_payload()

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault = Path(tmp_dir) / "vault"
            extractor.distribute_to_vault(payload, "2026-04-08", str(vault))

            inbox = (vault / "收件箱" / "灵感速记.md").read_text(encoding="utf-8")
            log_text = (vault / "日志" / "2026-04-08-上下文.md").read_text(encoding="utf-8")

        self.assertIn("重写 README", inbox)
        self.assertNotIn("同步状态到 Obsidian", inbox)
        self.assertIn("真正的问题是 Intent 和 facts 要分桶", inbox)
        self.assertIn("先做 Intent，再做前端。", log_text)


class TestExtractorCallGemini(unittest.TestCase):
    def test_normalize_extraction_payload_resolves_relative_due_dates_against_reference_date(self):
        payload = extractor.normalize_extraction_payload(
            {
                "daily_summary": "ok",
                "events": [],
                "intents": [
                    {
                        "intent_id": "intent_001",
                        "kind": "action_item",
                        "what": "提醒给张总回电话",
                        "status": "open",
                        "who": {"kind": "user", "label": "老板"},
                        "confidence_label": "high",
                        "confidence_score": 0.95,
                        "needs_review": False,
                        "evidence_quote": "明天下午三点提醒我给张总回电话。",
                        "source_scene_id": "scene_001",
                        "topic": "合同对接",
                        "due": {
                            "raw_text": "明天下午三点",
                            "iso_date": "2023-10-27T15:00:00",
                            "granularity": "time",
                        },
                    }
                ],
                "facts": [],
                "role_hints": [],
            },
            reference_date="2026-04-08",
        )

        due = payload["intents"][0]["due"]
        self.assertEqual(due["iso_date"], "2026-04-09T15:00:00")
        self.assertEqual(due["granularity"], "time")

    @patch("openmy.services.extraction.extractor.call_gemini")
    def test_run_extraction_passes_reference_date_to_gemini(self, call_gemini):
        call_gemini.return_value = {
            "daily_summary": "ok",
            "events": [],
            "intents": [],
            "facts": [],
            "role_hints": [],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "cleaned.md"
            input_path.write_text("今天记一下。", encoding="utf-8")

            result = extractor.run_extraction(input_path, date="2026-04-08", dry_run=True, api_key="test-key")

        self.assertIsNotNone(result)
        call_gemini.assert_called_once_with("今天记一下。", "test-key", extractor.GEMINI_MODEL, "2026-04-08")

    @patch("openmy.services.extraction.extractor.genai.Client")
    def test_call_gemini_uses_sdk_and_parses_json(self, client_cls):
        client = client_cls.return_value
        client.models.generate_content.return_value.text = json.dumps(
            {"daily_summary": "ok", "events": [], "intents": [], "facts": [], "role_hints": []},
            ensure_ascii=False,
        )

        payload = extractor.call_gemini("你好", api_key="test-key", model="gemini-test", reference_date="2026-04-08")

        self.assertEqual(payload["daily_summary"], "ok")
        self.assertTrue(client.models.generate_content.called)
        self.assertIn("2026-04-08", client.models.generate_content.call_args.kwargs["contents"])


if __name__ == "__main__":
    unittest.main()
