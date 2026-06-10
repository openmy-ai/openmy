#!/usr/bin/env python3
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestScreenProductCopy(unittest.TestCase):
    def test_product_surfaces_do_not_expose_legacy_screen_brand(self):
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
            legacy_brand = "Screen" + "pipe"
            self.assertNotIn(legacy_brand, content, path.as_posix())
            self.assertNotIn(legacy_brand.lower(), content, path.as_posix())

    def test_frontend_uses_openmy_screen_context_terms(self):
        # The frontend was refactored into ES modules; UI copy that used to live
        # in app.js now lives across app/static/modules/*.js.
        static_dir = PROJECT_ROOT / "app" / "static"
        parts = [
            (PROJECT_ROOT / "app" / "index.html").read_text(encoding="utf-8"),
            (static_dir / "app.js").read_text(encoding="utf-8"),
        ]
        for module_file in sorted((static_dir / "modules").glob("*.js")):
            parts.append(module_file.read_text(encoding="utf-8"))
        content = "\n".join(parts)
        self.assertIn("屏幕上下文", content)


if __name__ == "__main__":
    unittest.main()
