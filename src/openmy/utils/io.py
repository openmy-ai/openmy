from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def safe_write_json(
    path: Path,
    data: Any,
    *,
    ensure_ascii: bool = False,
    indent: int = 2,
    trailing_newline: bool = False,
) -> None:
    """Atomically write JSON to disk via a sibling temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=ensure_ascii, indent=indent)
            if trailing_newline:
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)
