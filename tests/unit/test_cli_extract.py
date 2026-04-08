#!/usr/bin/env python3
import argparse
import io
import unittest
from unittest.mock import patch

from openmy import cli


class TestCliExtract(unittest.TestCase):
    def test_build_parser_accepts_extract_command(self):
        parser = cli.build_parser()

        args = parser.parse_args(["extract", "demo.md", "--dry-run"])

        self.assertEqual(args.command, "extract")
        self.assertEqual(args.input_file, "demo.md")
        self.assertTrue(args.dry_run)

    @patch("openmy.services.extraction.extractor.run_extraction")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_cmd_extract_dry_run_prints_json(self, stdout, run_extraction):
        run_extraction.return_value = {
            "daily_summary": "今天主要推进 Intent。",
            "events": [],
            "intents": [{"intent_id": "intent_001", "kind": "action_item", "what": "重写 README"}],
            "facts": [{"fact_type": "idea", "content": "Intent 和 facts 要分桶。"}],
            "role_hints": [],
            "todos": [{"task": "重写 README", "priority": "high", "project": "OpenMy"}],
            "decisions": [],
            "insights": [],
            "legacy_todos": [],
        }

        args = argparse.Namespace(
            input_file="demo.md",
            date="2026-04-08",
            model="gemini-test",
            vault_path=None,
            api_key="test-key",
            dry_run=True,
        )

        result = cli.cmd_extract(args)

        self.assertEqual(result, 0)
        self.assertIn('"intents"', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
