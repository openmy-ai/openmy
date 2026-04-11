#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from openmy.utils.io import safe_write_json


class TestSafeWriteJson(unittest.TestCase):
    def test_safe_write_json_replaces_file_atomically(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "payload.json"
            path.write_text('{"old": true}', encoding="utf-8")

            safe_write_json(path, {"new": True})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"new": True})
            self.assertFalse(any(child.suffix == ".tmp" for child in path.parent.iterdir()))


if __name__ == "__main__":
    unittest.main()
