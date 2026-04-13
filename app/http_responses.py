from __future__ import annotations

import json
from pathlib import Path
from http.server import SimpleHTTPRequestHandler


def send_json(handler: SimpleHTTPRequestHandler, payload: dict | list, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)


def send_options(handler: SimpleHTTPRequestHandler) -> None:
    handler.send_response(204)
    handler.send_header('Allow', 'GET,HEAD,POST,OPTIONS')
    handler.end_headers()


def serve_index(handler: SimpleHTTPRequestHandler) -> None:
    root = Path(__file__).parent
    body = (root / 'index.html').read_bytes()
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/html; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)
