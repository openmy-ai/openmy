from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any

from app.http_responses import send_json


CHUNK_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _server():
    import app.server as server_module

    return server_module


def _load_transcription_payload(day_dir: Path) -> dict[str, Any]:
    server = _server()
    return server.load_json(day_dir / "transcript.transcription.json") or {}


def _resolve_chunk_path(day_dir: Path, raw_path: str) -> Path | None:
    candidate = Path(str(raw_path or "").strip()).expanduser()
    if not str(candidate):
        return None

    try:
        resolved = candidate.resolve() if candidate.is_absolute() else (day_dir / candidate).resolve()
    except OSError:
        return None

    chunk_root = (day_dir / "stt_chunks").resolve()
    if resolved != chunk_root and chunk_root not in resolved.parents:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved


def resolve_chunk_audio(date_str: str, chunk_id: str) -> tuple[Path, str] | None:
    if not CHUNK_ID_RE.match(str(chunk_id or "").strip()):
        return None

    server = _server()
    day_dir = server.DATA_ROOT / date_str
    payload = _load_transcription_payload(day_dir)
    chunks = payload.get("chunks", []) if isinstance(payload.get("chunks", []), list) else []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        if str(chunk.get("chunk_id", "") or "").strip() != chunk_id:
            continue
        chunk_path = _resolve_chunk_path(day_dir, str(chunk.get("chunk_path", "") or ""))
        if not chunk_path:
            return None
        content_type, _ = mimetypes.guess_type(str(chunk_path))
        return chunk_path, content_type or "application/octet-stream"
    return None


def _parse_range_header(range_header: str, total_size: int) -> tuple[int, int] | None:
    if not range_header or not range_header.startswith("bytes="):
        return None

    spec = range_header[6:].strip()
    if not spec or "," in spec or "-" not in spec:
        raise ValueError("invalid range")

    start_text, end_text = spec.split("-", 1)
    if not start_text and not end_text:
        raise ValueError("invalid range")

    if start_text:
        start = int(start_text)
        if start < 0 or start >= total_size:
            raise ValueError("unsatisfied range")
        end = total_size - 1 if not end_text else int(end_text)
    else:
        suffix_size = int(end_text)
        if suffix_size <= 0:
            raise ValueError("invalid range")
        if suffix_size >= total_size:
            return 0, total_size - 1
        start = total_size - suffix_size
        end = total_size - 1

    if end < start:
        raise ValueError("invalid range")
    return start, min(end, total_size - 1)


def _send_file_slice(handler, file_path: Path, start: int, end: int) -> None:
    if handler.command == "HEAD":
        return

    remaining = end - start + 1
    with file_path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(64 * 1024, remaining))
            if not chunk:
                break
            handler.wfile.write(chunk)
            remaining -= len(chunk)


def serve_chunk_audio(handler, date_str: str, chunk_id: str) -> None:
    resolved = resolve_chunk_audio(date_str, chunk_id)
    if not resolved:
        send_json(handler, {"error": "audio not found", "date": date_str, "chunk_id": chunk_id}, status=404)
        return

    file_path, content_type = resolved
    total_size = file_path.stat().st_size
    range_header = str(handler.headers.get("Range", "") or "").strip()

    try:
        parsed_range = _parse_range_header(range_header, total_size) if range_header else None
    except ValueError:
        handler.send_response(416)
        handler.send_header("Content-Range", f"bytes */{total_size}")
        handler.send_header("Accept-Ranges", "bytes")
        handler.end_headers()
        return

    if parsed_range is None:
        start = 0
        end = total_size - 1
        status = 200
    else:
        start, end = parsed_range
        status = 206

    content_length = end - start + 1
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Content-Length", str(content_length))
    if status == 206:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
    handler.end_headers()
    _send_file_slice(handler, file_path, start, end)
