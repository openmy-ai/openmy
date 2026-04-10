from __future__ import annotations

import json
from pathlib import Path


def send_options(handler) -> None:
    handler.send_response(204)
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()


def send_json(handler, data, status: int = 200) -> None:
    response = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(response)))
    handler.end_headers()
    handler.wfile.write(response)


def serve_index(handler) -> None:
    index_path = Path(__file__).parent / "index.html"
    if not index_path.exists():
        handler.send_error(404, "index.html 不存在")
        return
    content = index_path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)
