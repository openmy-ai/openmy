from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parents[1] / 'fixtures'


def load_fixture_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding='utf-8'))
