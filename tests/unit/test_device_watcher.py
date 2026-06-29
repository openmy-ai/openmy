#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from openmy.services import device_watcher as dw


class TestDeviceWatcher(unittest.TestCase):
    def test_group_by_date(self):
        files = [
            Path("/x/TX01_MIC001_20260629_104056_orig.wav"),
            Path("/x/TX01_MIC002_20260629_120000.wav"),
            Path("/x/TX01_MIC001_20260401_090000.wav"),
            Path("/x/random.wav"),
        ]
        grouped = dw.group_by_date(files)
        self.assertEqual(len(grouped["2026-06-29"]), 2)
        self.assertEqual(len(grouped["2026-04-01"]), 1)
        self.assertIn("unknown", grouped)

    def test_ledger_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            self.assertEqual(dw._load_ledger(path), {})
            dw._save_ledger(path, {"a:1": {"name": "a"}})
            self.assertEqual(dw._load_ledger(path), {"a:1": {"name": "a"}})

    def test_ledger_key_uses_name_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "TX01_MIC001_20260629_104056.wav"
            f.write_bytes(b"12345")
            self.assertEqual(dw._ledger_key(f), f"{f.name}:5")

    def test_find_dji_recordings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            dji1 = root / "TX01_MIC001_20260629_104056_orig.wav"
            dji2 = root / "sub" / "TX01_MIC002_20260629_120000.wav"
            other = root / "notdji.wav"
            for p in (dji1, dji2, other):
                p.write_bytes(b"x")
            found = {p.name for p in dw.find_dji_recordings(root)}
            self.assertEqual(found, {dji1.name, dji2.name})

    def test_copy_new_recordings_skips_ledgered(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "src"
            dest_dir = Path(tmp) / "dest"
            src_dir.mkdir()
            dest_dir.mkdir()
            src = src_dir / "TX01_MIC001_20260629_104056.wav"
            src.write_bytes(b"abcde")

            ledger: dict = {}
            copied = dw.copy_new_recordings([src], dest_dir, ledger)
            self.assertEqual(len(copied), 1)
            self.assertTrue((dest_dir / src.name).exists())
            self.assertIn(dw._ledger_key(src), ledger)

            # 第二次：账本里已有，跳过
            copied_again = dw.copy_new_recordings([src], dest_dir, ledger)
            self.assertEqual(copied_again, [])

    def test_run_once_no_volumes(self):
        # 没有外部卷时 run_once 返回 0 且不报错
        orig = dw.list_external_volumes
        dw.list_external_volumes = lambda: []
        try:
            self.assertEqual(dw.run_once(), 0)
        finally:
            dw.list_external_volumes = orig


if __name__ == "__main__":
    unittest.main()
