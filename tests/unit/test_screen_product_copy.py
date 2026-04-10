#!/usr/bin/env python3
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestScreenProductCopy(unittest.TestCase):
    def test_product_surfaces_do_not_expose_screenpipe_name(self):
        product_files = [
            PROJECT_ROOT / "app" / "index.html",
            PROJECT_ROOT / "app" / "server.py",
            PROJECT_ROOT / "src" / "openmy" / "services" / "briefing" / "cli.py",
            PROJECT_ROOT / "src" / "openmy" / "services" / "screen_recognition" / "__init__.py",
            PROJECT_ROOT / "src" / "openmy" / "domain" / "models.py",
            PROJECT_ROOT / "src" / "openmy" / "services" / "roles" / "resolver.py",
        ]

        for path in product_files:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("Screenpipe", content, path.as_posix())
            self.assertNotIn("screenpipe", content, path.as_posix())

    def test_frontend_uses_openmy_screen_context_terms(self):
        content = (PROJECT_ROOT / "app" / "index.html").read_text(encoding="utf-8")
        self.assertIn("屏幕上下文", content)


if __name__ == "__main__":
    unittest.main()
