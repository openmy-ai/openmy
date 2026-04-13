#!/usr/bin/env python3
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import app.server as app_server
from app.job_runner import JobRunner


class TestWebSmoke(unittest.TestCase):
    def fetch_json(self, base_url: str, path: str):
        with urlopen(f"{base_url}{path}", timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))

    def wait_for_job_status(self, runner: JobRunner, job_id: str, expected_status: str, timeout: float = 1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            payload = runner.get_job(job_id)
            if payload and payload["status"] == expected_status:
                return payload
            time.sleep(0.01)
        self.fail(f"job {job_id} did not reach status {expected_status}")

    def start_server(self, data_root: Path, legacy_root: Path, runner: JobRunner):
        patches = [
            patch.object(app_server, "DATA_ROOT", data_root),
            patch.object(app_server, "LEGACY_ROOT", legacy_root),
            patch.object(app_server, "ROOT_DIR", legacy_root),
            patch.object(app_server, "JOB_RUNNER", runner),
        ]
        for item in patches:
            item.start()

        server = ThreadingHTTPServer(("127.0.0.1", 0), app_server.BrainHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        return server, patches, base_url

    def stop_server(self, server: ThreadingHTTPServer, patches: list):
        server.shutdown()
        server.server_close()
        for item in reversed(patches):
            item.stop()

    def seed_onboarding(self, data_root: Path) -> None:
        (data_root / "onboarding_state.json").write_text(
            json.dumps(
                {
                    "completed": False,
                    "headline": "先别自己挑，先按推荐路线走：本地中文优先",
                    "recommended_reason": "中文录音优先，而且不用密钥。",
                    "primary_action": "先运行 openmy skill profile.set --stt-provider funasr --json，先把推荐路线定下来。",
                    "choices": {
                        "local": [{"label": "本地中文优先", "description": "中文录音优先，而且不用密钥。", "is_recommended": True}],
                        "cloud": [{"label": "云端省事优先", "description": "后面再看。", "is_recommended": False}],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def seed_context(self, data_root: Path) -> None:
        (data_root / "active_context.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-09T10:00:00+08:00",
                    "status_line": "最近主要推进 OpenMy；当前有 2 个待办未闭环；高频互动对象是 伴侣。",
                    "rolling_context": {
                        "active_projects": [{"title": "OpenMy", "project_id": "project_openmy"}],
                        "open_loops": [{"title": "补前端工作台", "loop_id": "loop_frontend"}],
                        "recent_decisions": [{"decision": "先补前端，再做 polish。", "decision_id": "decision_001"}],
                    },
                    "realtime_context": {
                        "today_focus": ["前端补齐", "pipeline"],
                        "today_state": {"energy": "focused"},
                        "ingestion_health": {"last_processed_date": "2026-04-08"},
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def seed_day(self, data_root: Path, date_str: str) -> None:
        day_dir = data_root / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "transcript.md").write_text(
            "# sample\n\n---\n\n## 10:00\n\n今天先补前端。",
            encoding="utf-8",
        )
        (day_dir / f"{date_str}.meta.json").write_text(
            json.dumps(
                {
                    "daily_summary": "今天主要补前端工作台。",
                    "intents": [{"what": "补前端"}],
                    "facts": [{"content": "active_context 已接上"}],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (day_dir / "daily_briefing.json").write_text(
            json.dumps(
                {
                    "summary": "今天主要推进前端补齐。",
                    "key_events": ["接上 active_context"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def test_server_serves_onboarding_payload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_onboarding(data_root)

            runner = JobRunner()
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                payload = self.fetch_json(base_url, "/api/onboarding")
            finally:
                self.stop_server(server, patches)

            self.assertEqual(payload["headline"], "先别自己挑，先按推荐路线走：本地中文优先")
            self.assertIn("profile.set", payload["primary_action"])
            self.assertNotIn("state_path", payload)

    def test_server_updates_onboarding_provider(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_onboarding(data_root)

            runner = JobRunner()
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                request = Request(
                    f"{base_url}/api/onboarding/select",
                    data=json.dumps({"provider": "funasr"}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request, timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                self.stop_server(server, patches)

            self.assertTrue(payload["success"])
            self.assertEqual(payload["provider"], "funasr")
            self.assertEqual(payload["onboarding"]["current_provider"], "funasr")
            self.assertNotIn("state_path", payload["onboarding"])

    def test_server_serves_health_payload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            runner = JobRunner()
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                payload = self.fetch_json(base_url, "/api/health")
            finally:
                self.stop_server(server, patches)

        self.assertEqual(payload, {"status": "ok"})

    def test_server_serves_favicon_redirect(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            runner = JobRunner()
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                request = Request(f"{base_url}/favicon.ico", method="GET")
                with urlopen(request, timeout=2) as response:
                    final_url = response.geturl()
            finally:
                self.stop_server(server, patches)

        self.assertTrue(final_url.endswith("/static/icons/logo.svg"))

    def test_server_head_on_onboarding_returns_200(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_onboarding(data_root)

            runner = JobRunner()
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                request = Request(f"{base_url}/api/onboarding", method="HEAD")
                with urlopen(request, timeout=2) as response:
                    status_code = response.status
                    content_length = response.headers.get("Content-Length")
            finally:
                self.stop_server(server, patches)

        self.assertEqual(status_code, 200)
        self.assertIsNotNone(content_length)

    def test_server_serves_context_and_pipeline_contract(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_context(data_root)

            runner = JobRunner()
            created = runner.create_job(
                kind="context",
                target_date=None,
                run_fn=lambda handle: handle.log("context started"),
            )
            self.wait_for_job_status(runner, created["job_id"], "succeeded")

            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                context_payload = self.fetch_json(base_url, "/api/context")
                jobs_payload = self.fetch_json(base_url, "/api/pipeline/jobs")
                detail_payload = self.fetch_json(base_url, f"/api/pipeline/jobs/{created['job_id']}")
            finally:
                self.stop_server(server, patches)

            self.assertEqual(context_payload["status_line"], "最近主要推进 OpenMy；当前有 2 个待办未闭环；高频互动对象是 伴侣。")
            self.assertEqual(context_payload["today_focus"], ["前端补齐", "pipeline"])
            self.assertEqual(jobs_payload[0]["job_id"], created["job_id"])
            self.assertEqual(detail_payload["status"], "succeeded")
            self.assertIn("context started", detail_payload["log_lines"])

    def test_server_serves_day_workspace_contract(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_day(data_root, "2026-04-08")

            runner = JobRunner()
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                detail_payload = self.fetch_json(base_url, "/api/date/2026-04-08")
                meta_payload = self.fetch_json(base_url, "/api/date/2026-04-08/meta")
                briefing_payload = self.fetch_json(base_url, "/api/date/2026-04-08/briefing")
            finally:
                self.stop_server(server, patches)

            self.assertEqual(detail_payload["meta"]["daily_summary"], "今天主要补前端工作台。")
            self.assertEqual(meta_payload["intents"][0]["what"], "补前端")
            self.assertEqual(briefing_payload["summary"], "今天主要推进前端补齐。")

    def test_server_dates_hide_demo_year_entries(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_day(data_root, "2026-04-08")
            self.seed_day(data_root, "2099-12-31")

            runner = JobRunner()
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                payload = self.fetch_json(base_url, "/api/dates")
            finally:
                self.stop_server(server, patches)

        self.assertEqual([item["date"] for item in payload], ["2026-04-08"])

    def test_server_does_not_expose_repo_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            runner = JobRunner(job_dir=project_root / "jobs")
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(f"{base_url}/README.md", timeout=2)
            finally:
                self.stop_server(server, patches)

            self.assertEqual(ctx.exception.code, 404)

    def test_server_serves_static_assets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            runner = JobRunner(job_dir=project_root / "jobs")
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                with urlopen(f"{base_url}/static/style.css", timeout=2) as style_response:
                    style_body = style_response.read().decode("utf-8")
                    style_type = style_response.headers.get_content_type()
                with urlopen(f"{base_url}/static/app.js", timeout=2) as script_response:
                    script_body = script_response.read().decode("utf-8")
                    script_type = script_response.headers.get_content_type()
            finally:
                self.stop_server(server, patches)

        self.assertEqual(style_type, "text/css")
        self.assertIn("--font-body", style_body)
        self.assertEqual(script_type, "text/javascript")
        self.assertIn("function init()", script_body)

    def test_server_serves_nested_static_vendor_asset(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            runner = JobRunner(job_dir=project_root / "jobs")
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                with urlopen(f"{base_url}/static/vendor/chart.umd.js", timeout=2) as response:
                    body = response.read().decode("utf-8")
                    content_type = response.headers.get_content_type()
            finally:
                self.stop_server(server, patches)

        self.assertEqual(content_type, "text/javascript")
        self.assertIn("Chart.js", body)

    def test_invalid_date_path_returns_400(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            runner = JobRunner(job_dir=project_root / "jobs")
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(f"{base_url}/api/date/../../etc", timeout=2)
            finally:
                self.stop_server(server, patches)

        self.assertEqual(ctx.exception.code, 400)

    def test_post_requires_application_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            runner = JobRunner(job_dir=project_root / "jobs")
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                request = Request(
                    f"{base_url}/api/correct",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "text/plain"},
                )
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(request, timeout=2)
            finally:
                self.stop_server(server, patches)

        self.assertEqual(ctx.exception.code, 415)


if __name__ == "__main__":
    unittest.main()
