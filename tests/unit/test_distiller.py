#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestDistillerCli(unittest.TestCase):
    def test_main_respects_custom_api_key_env(self):
        from openmy.services.distillation import distiller

        with tempfile.TemporaryDirectory() as tmpdir:
            scenes_path = Path(tmpdir) / "scenes.json"
            scenes_path.write_text('{"scenes": []}', encoding="utf-8")

            with (
                patch.dict("os.environ", {"CUSTOM_DISTILL_KEY": "custom-key"}, clear=True),
                patch.object(
                    sys,
                    "argv",
                    [
                        "distiller.py",
                        str(scenes_path),
                        "--api-key-env",
                        "CUSTOM_DISTILL_KEY",
                    ],
                ),
                patch("openmy.services.distillation.distiller.distill_scenes") as mock_distill,
            ):
                result = distiller.main()

        self.assertEqual(result, 0)
        mock_distill.assert_called_once_with(scenes_path, "custom-key", distiller.GEMINI_MODEL)


if __name__ == "__main__":
    unittest.main()
