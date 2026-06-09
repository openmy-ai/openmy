from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def upsert_env_value(env_path: Path, key: str, value: str) -> Path:
    """Read a .env file, find/replace a key=value line, write it back.

    If the key already exists its line is updated in-place; otherwise
    a new ``key=value`` line is appended.  Returns *env_path* for
    convenience.
    """
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    replaced = False
    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        existing_key = stripped.split("=", 1)[0].strip()
        if existing_key != key:
            continue
        lines[index] = f"{key}={value}"
        replaced = True
        break

    if not replaced:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{key}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return env_path


def load_vocab_terms(vocab_file: Path) -> str:
    """Load vocabulary terms from a ``vocab.txt`` file.

    Each non-blank, non-comment line should have the term as the first
    pipe-delimited field.  Returns a Chinese-comma-separated string of
    terms.
    """
    if not vocab_file.exists():
        return ""
    terms: list[str] = []
    for raw_line in vocab_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line.split("|", 1)[0].strip())
    return "、".join(t for t in terms if t)


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
