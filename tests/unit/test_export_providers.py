#!/usr/bin/env python3
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from openmy.providers.export.notion import NotionExportProvider
from openmy.providers.export.obsidian import ObsidianExportProvider
from openmy.providers.registry import ProviderRegistry


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestExportProviders(unittest.TestCase):
    def test_obsidian_export_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = ObsidianExportProvider(config={"vault_path": tmpdir})
            result = provider.export_daily_briefing(
                "2026-04-11",
                {"summary": "今天主要修 OpenMy。", "todos_open": ["补 README"]},
            )
            target = Path(result["path"])
            content = target.read_text(encoding="utf-8")
            self.assertTrue(target.exists())
            self.assertIn("source: openmy", content)
            self.assertIn("补 README", content)

    def test_obsidian_export_appends_when_file_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = ObsidianExportProvider(config={"vault_path": tmpdir})
            provider.export_daily_briefing("2026-04-11", {"summary": "第一次"})
            result = provider.export_daily_briefing("2026-04-11", {"summary": "第二次"})
            content = Path(result["path"]).read_text(encoding="utf-8")
            self.assertEqual(result["mode"], "append")
            self.assertIn("第一次", content)
            self.assertIn("第二次", content)

    def test_notion_export_retries_401_then_succeeds(self):
        provider = NotionExportProvider(config={"api_key": "key", "database_id": "db"})
        http_error = HTTPError(
            url="https://api.notion.com/v1/pages",
            code=401,
            msg="rate limit",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"rate limit"}'),
        )
        with patch("urllib.request.urlopen", side_effect=[http_error, FakeResponse({"id": "page-1", "url": "https://notion.so/page-1"})]), patch("time.sleep"):
            result = provider.export_daily_briefing("2026-04-11", {"summary": "今天很好"})
        self.assertEqual(result["page_id"], "page-1")
        self.assertIn("notion.so", result["url"])

    def test_notion_export_missing_key_raises(self):
        provider = NotionExportProvider(config={"api_key": "", "database_id": "db"})
        with self.assertRaises(RuntimeError):
            provider.export_daily_briefing("2026-04-11", {"summary": "今天很好"})

    def test_notion_export_uses_profile_timezone_for_date_property(self):
        provider = NotionExportProvider(config={"api_key": "key", "database_id": "db"})
        with patch("openmy.providers.export.notion.iso_at", return_value="2026-04-11T08:00:00-07:00"):
            self.assertEqual(provider._notion_timestamp("2026-04-11"), "2026-04-11T08:00:00-07:00")

    def test_registry_builds_obsidian_export_provider(self):
        with patch.dict("os.environ", {"OPENMY_EXPORT_PROVIDER": "obsidian", "OPENMY_OBSIDIAN_VAULT_PATH": "/tmp/vault"}, clear=True):
            provider = ProviderRegistry.from_env().get_export_provider()
        self.assertEqual(provider.name, "obsidian")


if __name__ == "__main__":
    unittest.main()
