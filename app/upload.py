from __future__ import annotations

import re
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any


UPLOAD_LIMIT_BYTES = 500 * 1024 * 1024
MULTIPART_BODY_LIMIT_BYTES = UPLOAD_LIMIT_BYTES + 256 * 1024
ALLOWED_UPLOAD_SUFFIXES = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".mp4",
    ".mov",
    ".flac",
    ".ogg",
    ".webm",
}


def _server():
    import app.server as server_module

    return server_module


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "upload")
    return cleaned.strip("._") or "upload.bin"


def _read_chunked_body(handler) -> bytes:
    total = 0
    chunks = bytearray()
    while True:
        raw_size = handler.rfile.readline()
        if not raw_size:
            break
        size_token = raw_size.split(b";", 1)[0].strip()
        if not size_token:
            continue
        try:
            size = int(size_token, 16)
        except ValueError:
            raise ValueError("invalid chunked upload body")
        if size == 0:
            while True:
                trailer = handler.rfile.readline()
                if trailer in {b"", b"\r\n", b"\n"}:
                    break
            break
        chunk = handler.rfile.read(size)
        if len(chunk) != size:
            raise ValueError("truncated chunked upload body")
        chunks.extend(chunk)
        total += size
        if total > MULTIPART_BODY_LIMIT_BYTES:
            raise ValueError("file too large")
        handler.rfile.read(2)
    return bytes(chunks)


def _read_request_body(handler) -> bytes:
    transfer_encoding = str(handler.headers.get("Transfer-Encoding", "") or "").lower()
    if "chunked" in transfer_encoding:
        return _read_chunked_body(handler)

    content_length = int(handler.headers.get("Content-Length", "0") or 0)
    if content_length <= 0:
        raise ValueError("missing upload body")
    if content_length > MULTIPART_BODY_LIMIT_BYTES:
        raise ValueError("file too large")
    body = handler.rfile.read(content_length)
    if not body:
        raise ValueError("empty upload body")
    return body


def _extract_upload_part(content_type: str, body: bytes) -> tuple[str, bytes]:
    parser = BytesParser(policy=policy.default)
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = parser.parsebytes(header + body)
    if not message.is_multipart():
        raise ValueError("invalid multipart payload")

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        field_name = str(part.get_param("name", header="content-disposition") or "")
        if field_name != "file":
            continue
        filename = Path(part.get_filename() or "").name
        if not filename:
            raise ValueError("missing filename")
        payload = part.get_payload(decode=True) or b""
        return filename, payload
    raise ValueError("missing upload file")


def handle_upload_request(handler) -> dict[str, Any]:
    content_type = str(handler.headers.get("Content-Type", "") or "")
    if not content_type.lower().startswith("multipart/form-data"):
        return {"error": "missing multipart boundary"}

    try:
        body = _read_request_body(handler)
    except ValueError as exc:
        message = str(exc)
        if message == "file too large":
            return {"error": "file too large", "limit_bytes": UPLOAD_LIMIT_BYTES}
        return {"error": message}

    try:
        filename, file_bytes = _extract_upload_part(content_type, body)
    except ValueError as exc:
        return {"error": str(exc)}

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return {"error": "unsupported file type", "allowed_suffixes": sorted(ALLOWED_UPLOAD_SUFFIXES)}
    if len(file_bytes) > UPLOAD_LIMIT_BYTES:
        return {"error": "file too large", "limit_bytes": UPLOAD_LIMIT_BYTES}

    inbox_dir = _server().DATA_ROOT / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    saved_name = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{_safe_filename(filename)}"
    saved_path = inbox_dir / saved_name
    saved_path.write_bytes(file_bytes)

    return {
        "file_path": str(saved_path),
        "filename": filename,
        "size_bytes": saved_path.stat().st_size,
    }
