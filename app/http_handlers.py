from __future__ import annotations

import json
import mimetypes
import re
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.audio_api import serve_chunk_audio
from app.context_api import (
    handle_close_loop,
    handle_merge_project,
    handle_reject_decision,
    handle_reject_loop,
    handle_reject_project,
)
from app.http_responses import send_json, send_options, serve_index
from app.payloads import (
    get_all_dates,
    get_briefing,
    get_context_decisions_payload,
    get_context_loops_payload,
    get_context_payload,
    get_context_projects_payload,
    get_context_query_payload,
    get_corrections,
    get_date_briefing_payload,
    get_date_detail,
    get_date_meta_payload,
    get_onboarding_payload,
    get_screen_context_settings_payload,
    get_stats,
    handle_correction,
    search_content,
    update_onboarding_provider_payload,
    update_screen_context_settings_payload,
)
from app.pipeline_api import (
    get_pipeline_job_payload,
    get_pipeline_jobs_payload,
    handle_create_pipeline_job,
    handle_job_action,
    handle_upload_request,
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_JSON_BODY_BYTES = 50 * 1024 * 1024


def _valid_date_or_400(handler: SimpleHTTPRequestHandler, date_str: str) -> bool:
    if DATE_RE.match(date_str):
        return True
    send_json(handler, {"error": "invalid date", "date": date_str}, status=400)
    return False


class BrainHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self._dispatch_request()

    def do_HEAD(self):
        self._dispatch_request()

    def _dispatch_request(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/health":
            send_json(self, {"status": "ok"})
        elif path == "/api/context":
            send_json(self, get_context_payload())
        elif path == "/api/onboarding":
            send_json(self, get_onboarding_payload())
        elif path == "/api/context/loops":
            send_json(self, get_context_loops_payload())
        elif path == "/api/context/projects":
            send_json(self, get_context_projects_payload())
        elif path == "/api/context/decisions":
            send_json(self, get_context_decisions_payload())
        elif path == "/api/context/query":
            kind = params.get("kind", [""])[0]
            query = params.get("q", [""])[0]
            limit_raw = params.get("limit", ["5"])[0]
            include_evidence = params.get("evidence", ["0"])[0].lower() in {"1", "true", "yes"}
            try:
                limit = int(limit_raw)
            except ValueError:
                limit = 5
            payload = get_context_query_payload(
                kind=kind,
                query=query,
                limit=limit,
                include_evidence=include_evidence,
            )
            send_json(self, payload, status=200 if not payload.get("error") else 400)
        elif path == "/api/dates":
            send_json(self, get_all_dates())
        elif path == "/api/search":
            query = params.get("q", [""])[0]
            send_json(self, [] if not query else search_content(query))
        elif path == "/api/stats":
            send_json(self, get_stats())
        elif path.startswith("/api/briefing/"):
            date = path.split("/api/briefing/")[-1]
            if not _valid_date_or_400(self, date):
                return
            briefing = get_briefing(date)
            if briefing:
                send_json(self, briefing)
            else:
                send_json(self, {"error": "no briefing", "date": date}, status=404)
        elif path.startswith("/api/audio/"):
            suffix = path.removeprefix("/api/audio/")
            date, _, chunk_id = suffix.partition("/")
            if not date or not chunk_id or "/" in chunk_id:
                send_json(self, {"error": "invalid audio route"}, status=400)
                return
            if not _valid_date_or_400(self, date):
                return
            serve_chunk_audio(self, date, chunk_id)
        elif path.startswith("/api/date/") and path.endswith("/meta"):
            date = path.removeprefix("/api/date/").removesuffix("/meta")
            if not _valid_date_or_400(self, date):
                return
            payload = get_date_meta_payload(date)
            if payload:
                send_json(self, payload)
            else:
                send_json(self, {"error": "no meta", "date": date}, status=404)
        elif path.startswith("/api/date/") and path.endswith("/briefing"):
            date = path.removeprefix("/api/date/").removesuffix("/briefing")
            if not _valid_date_or_400(self, date):
                return
            payload = get_date_briefing_payload(date)
            if payload:
                send_json(self, payload)
            else:
                send_json(self, {"error": "no briefing", "date": date}, status=404)
        elif path == "/api/pipeline/jobs":
            send_json(self, get_pipeline_jobs_payload())
        elif path.startswith("/api/pipeline/jobs/"):
            job_id = path.removeprefix("/api/pipeline/jobs/")
            payload = get_pipeline_job_payload(job_id)
            if payload:
                send_json(self, payload)
            else:
                send_json(self, {"error": "job not found", "job_id": job_id}, status=404)
        elif path.startswith("/api/date/"):
            date = path.split("/api/date/")[-1]
            if not _valid_date_or_400(self, date):
                return
            detail = get_date_detail(date)
            if detail:
                send_json(self, detail)
            else:
                self.send_error(404, "日期不存在")
        elif path == "/api/corrections":
            send_json(self, get_corrections())
        elif path == "/api/settings/screen-context":
            send_json(self, get_screen_context_settings_payload())
        elif path == "/favicon.ico":
            self.send_response(301)
            self.send_header("Location", "/static/icons/logo.svg")
            self.end_headers()
        elif path.startswith("/static/"):
            self._serve_static(path)
        elif path in {"/", "/index.html"}:
            serve_index(self)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/upload":
            payload = handle_upload_request(self)
            send_json(self, payload, status=200 if payload.get("file_path") else 400)
            return

        if self.headers.get("Content-Type", "").strip().lower() != "application/json":
            send_json(self, {"error": "unsupported media type", "expected": "application/json"}, status=415)
            return
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_JSON_BODY_BYTES:
            self.send_error(413, "Request Entity Too Large")
            return
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "无效的 JSON")
            return

        if path == "/api/correct":
            send_json(self, handle_correction(data))
        elif path == "/api/correct/typo":
            send_json(self, handle_correction(data))
        elif path == "/api/context/loops/close":
            payload = handle_close_loop(data)
            send_json(self, payload, status=200 if payload.get("success") else 400)
        elif path == "/api/context/loops/reject":
            payload = handle_reject_loop(data)
            send_json(self, payload, status=200 if payload.get("success") else 400)
        elif path == "/api/context/projects/merge":
            payload = handle_merge_project(data)
            send_json(self, payload, status=200 if payload.get("success") else 400)
        elif path == "/api/context/projects/reject":
            payload = handle_reject_project(data)
            send_json(self, payload, status=200 if payload.get("success") else 400)
        elif path == "/api/context/decisions/reject":
            payload = handle_reject_decision(data)
            send_json(self, payload, status=200 if payload.get("success") else 400)
        elif path == "/api/pipeline/jobs":
            payload = handle_create_pipeline_job(data)
            send_json(self, payload, status=200 if payload.get("job_id") else 400)
        elif path.startswith("/api/pipeline/jobs/"):
            suffix = path.removeprefix("/api/pipeline/jobs/")
            job_id, _, action = suffix.partition("/")
            payload, status = handle_job_action(job_id, action)
            send_json(self, payload, status=status)
        elif path == "/api/onboarding/select":
            payload = update_onboarding_provider_payload(data)
            send_json(self, payload, status=200 if payload.get('success') else 400)
        elif path == "/api/settings/screen-context":
            send_json(self, update_screen_context_settings_payload(data))
        else:
            self.send_error(404, "未知接口")

    def do_OPTIONS(self):
        send_options(self)

    def _serve_static(self, path: str) -> None:
        clean_path = path.lstrip("/")
        static_dir = Path(__file__).parent / "static"
        file_path = (static_dir / clean_path.removeprefix("static/")).resolve()
        static_root = static_dir.resolve()

        if not str(file_path).startswith(str(static_root)):
            self.send_error(403, "Forbidden")
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not Found")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        payload = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def log_message(self, format, *args):
        pass
