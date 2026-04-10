#!/usr/bin/env python3
import json
import unittest
from unittest.mock import patch

import openmy.cli as openmy_cli


class TestContextQueryCli(unittest.TestCase):
    def test_skill_context_query_outputs_json(self):
        parser = openmy_cli.build_parser()
        args = parser.parse_args(
            ["skill", "context.query", "--kind", "project", "--query", "OpenMy", "--json"]
        )

        payload = {"kind": "project", "query": "OpenMy", "summary": "OpenMy 最近在补查询接口。"}

        with (
            patch("openmy.cli.query_context", return_value=payload),
            patch("openmy.cli._print_json") as print_json,
        ):
            result = openmy_cli.main_with_args(args)

        self.assertEqual(result, 0)
        response = print_json.call_args.args[0]
        self.assertEqual(response["action"], "context.query")
        self.assertEqual(response["result"]["summary"], payload["summary"])

    def test_agent_query_routes_to_query_command(self):
        parser = openmy_cli.build_parser()
        args = parser.parse_args(
            ["agent", "--query", "OpenMy", "--query-kind", "project", "--limit", "3"]
        )

        with patch("openmy.cli.cmd_query", return_value=0) as query_mock:
            result = openmy_cli.main_with_args(args)

        self.assertEqual(result, 0)
        forwarded_args = query_mock.call_args.args[0]
        self.assertEqual(forwarded_args.kind, "project")
        self.assertEqual(forwarded_args.query, "OpenMy")
        self.assertEqual(forwarded_args.limit, 3)


if __name__ == "__main__":
    unittest.main()
