#!/usr/bin/env python3
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestPaths(unittest.TestCase):
    def test_resolve_data_root_prefers_env(self):
        from openmy.utils import paths

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"OPENMY_DATA_DIR": temp_dir}, clear=False):
            resolved = paths.resolve_data_root()

        self.assertEqual(resolved, Path(temp_dir).resolve())

    def test_find_project_root_walks_up_to_pyproject(self):
        from openmy.utils import paths

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='openmy'\n", encoding="utf-8")
            nested = root / "src" / "openmy" / "utils" / "paths.py"
            nested.parent.mkdir(parents=True, exist_ok=True)
            nested.write_text("", encoding="utf-8")

            found = paths.find_project_root(nested)

        self.assertEqual(found, root.resolve())

    def test_resolve_data_root_falls_back_to_home_cache(self):
        from openmy.utils import paths

        with (
            tempfile.TemporaryDirectory() as temp_home,
            patch.dict(os.environ, {}, clear=True),
            patch("pathlib.Path.home", return_value=Path(temp_home)),
            patch("pathlib.Path.cwd", return_value=Path(temp_home) / "no-project"),
        ):
            resolved = paths.resolve_data_root(start_path=Path(temp_home) / "no-project" / "file.py")

        self.assertEqual(resolved, (Path(temp_home) / ".openmy" / "data").resolve())


if __name__ == "__main__":
    unittest.main()
