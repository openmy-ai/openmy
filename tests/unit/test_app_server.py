#!/usr/bin/env python3
import json
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path
from unittest.mock import patch

import app.server as app_server
from app.job_runner import JobRunner


class TestAppServer(unittest.TestCase):
    def test_bootstrap_root_resolves_from_server_file(self):
        expected_root = Path(__file__).resolve().parents[2]
        self.assertEqual(app_server.BOOTSTRAP_ROOT, expected_root)
        self.assertEqual(app_server.SRC_DIR, expected_root / "src")

    def wait_for_job_status(self, runner: JobRunner, job_id: str, expected_status: str, timeout: float = 1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = runner.get_job(job_id)
            if job and job["status"] == expected_status:
                return job
            time.sleep(0.01)
        self.fail(f"job {job_id} did not reach status {expected_status}")

    def make_context_snapshot(self) -> dict:
        return {
            "schema_version": "active_context.v1",
            "generated_at": "2026-04-09T10:00:00+08:00",
            "status_line": "最近主要推进 OpenMy；当前有 2 个待办未闭环；高频互动对象是 伴侣。",
            "rolling_context": {
                "active_projects": [
                    {
                        "project_id": "project_openmy",
                        "id": "project_openmy",
                        "title": "OpenMy",
                        "next_actions": ["补前端"],
                    },
                    {
                        "project_id": "project_frontend",
                        "id": "project_frontend",
                        "title": "前端工作台",
                        "next_actions": ["接上 corrections"],
                    }
                ],
                "open_loops": [
                    {
                        "loop_id": "loop_frontend",
                        "id": "loop_frontend",
                        "title": "补前端工作台",
                    },
                    {
                        "loop_id": "loop_cleanup",
                        "id": "loop_cleanup",
                        "title": "清理未来测试日期",
                    }
                ],
                "recent_decisions": [
                    {
                        "decision_id": "decision_001",
                        "id": "decision_001",
                        "decision": "先补前端，再做 polish。",
                    },
                    {
                        "decision_id": "decision_002",
                        "id": "decision_002",
                        "decision": "移动端放在补齐后一起验。",
                    }
                ],
            },
            "realtime_context": {
                "today_focus": ["前端补齐", "active_context"],
                "today_state": {"energy": "focused"},
                "ingestion_health": {"last_processed_date": "2026-04-08"},
            },
        }

    def test_resolve_day_paths_prefers_dated_meta_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            day_dir = data_root / "2026-04-08"
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / "transcript.md").write_text("## 12:00\n\nhello", encoding="utf-8")
            (day_dir / "meta.json").write_text("{}", encoding="utf-8")
            (day_dir / "2026-04-08.meta.json").write_text("{}", encoding="utf-8")

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                paths = app_server.resolve_day_paths("2026-04-08")

            self.assertEqual(paths["meta"], day_dir / "2026-04-08.meta.json")

    def test_default_date_prefers_non_future_dates(self):
        ordered_dates = app_server.sort_dates_for_display(
            ["2099-04-08", "2026-04-08", "2026-04-07"],
            today="2026-04-09",
        )

        self.assertEqual(ordered_dates, ["2026-04-08", "2026-04-07", "2099-04-08"])
        self.assertEqual(app_server.choose_default_date(ordered_dates, today="2026-04-09"), "2026-04-08")

    def test_server_defaults_to_loopback_host(self):
        server = app_server.build_server(port=0)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
        finally:
            server.server_close()

    def test_json_response_does_not_return_wildcard_cors(self):
        server = app_server.build_server(port=0)
        try:
            with patch.object(app_server, "JOB_RUNNER", JobRunner()):
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                import threading

                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                with urlopen(f"{base_url}/api/stats", timeout=2) as response:
                    self.assertNotEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        finally:
            server.shutdown()
            server.server_close()

    def test_context_endpoint_returns_status_and_today_focus(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            (data_root / "active_context.json").write_text(
                json.dumps(self.make_context_snapshot(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root):
                payload = app_server.get_context_payload()

            self.assertEqual(payload["status_line"], self.make_context_snapshot()["status_line"])
            self.assertEqual(payload["today_focus"], ["前端补齐", "active_context"])

    def test_context_loops_endpoint_returns_open_loops(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            snapshot = self.make_context_snapshot()
            (data_root / "active_context.json").write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root):
                payload = app_server.get_context_loops_payload()

            self.assertEqual(payload, snapshot["rolling_context"]["open_loops"])

    def test_context_projects_endpoint_returns_active_projects(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            snapshot = self.make_context_snapshot()
            (data_root / "active_context.json").write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root):
                payload = app_server.get_context_projects_payload()

            self.assertEqual(payload, snapshot["rolling_context"]["active_projects"])

    def test_context_query_endpoint_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)

            with patch.object(app_server, "DATA_ROOT", data_root), patch(
                "app.http_handlers.get_context_query_payload",
                return_value={
                    "kind": "project",
                    "query": "OpenMy",
                    "summary": "OpenMy 最近主要在接查询接口。",
                    "current_hits": [{"type": "project", "title": "OpenMy"}],
                    "history_hits": [],
                    "daily_rollups": [{"date": "2026-04-10", "summary": "今天主要补查询接口。"}],
                    "temporal_buckets": {"current": [{"title": "OpenMy"}], "past": [], "future": [], "closed": []},
                    "conflicts": [],
                    "evidence": [],
                },
            ):
                server = app_server.build_server(port=0)
                try:
                    import threading

                    base_url = f"http://127.0.0.1:{server.server_address[1]}"
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    with urlopen(f"{base_url}/api/context/query?kind=project&q=OpenMy", timeout=2) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                finally:
                    server.shutdown()
                    server.server_close()

            self.assertEqual(payload["kind"], "project")
            self.assertEqual(payload["query"], "OpenMy")
            self.assertEqual(payload["current_hits"][0]["title"], "OpenMy")
            self.assertEqual(payload["daily_rollups"][0]["date"], "2026-04-10")

    def test_context_query_endpoint_error_lists_supported_types(self):
        server = app_server.build_server(port=0)
        try:
            import threading

            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"{base_url}/api/context/query?q=test", timeout=2)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertIn("支持的类型", payload["error"])
        self.assertIn("project", payload["error"])

    def seed_day_workspace(self, project_root: Path, date_str: str) -> Path:
        day_dir = project_root / "data" / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "transcript.md").write_text(
            "# sample\n\n---\n\n## 10:00\n\n今天先补前端。",
            encoding="utf-8",
        )
        (day_dir / f"{date_str}.meta.json").write_text(
            json.dumps(
                {
                    "daily_summary": "今天主要补前端工作台。",
                    "intents": [{"intent_id": "intent_001", "what": "补前端"}],
                    "facts": [{"fact_id": "fact_001", "content": "active_context 已接上"}],
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
        return day_dir

    def seed_audio_workspace(self, project_root: Path, date_str: str) -> tuple[Path, bytes]:
        day_dir = self.seed_day_workspace(project_root, date_str)
        chunk_dir = day_dir / "stt_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        audio_path = chunk_dir / "audio_001_sub_0000.mp3"
        audio_bytes = b"0123456789abcdef"
        audio_path.write_bytes(audio_bytes)
        (day_dir / "transcript.transcription.json").write_text(
            json.dumps(
                {
                    "chunks": [
                        {
                            "chunk_id": "chunk_0001",
                            "chunk_path": str(audio_path),
                            "time_label": "10:00",
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return day_dir, audio_bytes

    def test_date_detail_includes_meta_payload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_day_workspace(project_root, "2026-04-08")

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                payload = app_server.get_date_detail("2026-04-08")

            self.assertEqual(payload["meta"]["intents"][0]["what"], "补前端")
            self.assertEqual(payload["meta"]["facts"][0]["content"], "active_context 已接上")

    def test_get_date_detail_preserves_audio_ref_in_scenes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            day_dir = self.seed_day_workspace(project_root, "2026-04-08")
            (day_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "scenes": [
                            {
                                "scene_id": "scene_001",
                                "time_start": "10:00",
                                "time_end": "10:05",
                                "text": "今天先补前端。",
                                "summary": "上午补前端。",
                                "role": {"scene_type_label": "自言自语"},
                                "audio_ref": {
                                    "chunk_id": "chunk_0001",
                                    "offset_start": 1.2,
                                    "offset_end": 3.6,
                                    "segment_ids": ["seg_0001"],
                                },
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                payload = app_server.get_date_detail("2026-04-08")

            self.assertEqual(payload["scenes"]["scenes"][0]["audio_ref"]["chunk_id"], "chunk_0001")
            self.assertEqual(payload["segments"][0]["summary"], "上午补前端。")

    def test_get_date_detail_allows_missing_audio_ref(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            day_dir = self.seed_day_workspace(project_root, "2026-04-08")
            (day_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "scenes": [
                            {
                                "scene_id": "scene_001",
                                "time_start": "10:00",
                                "time_end": "10:05",
                                "text": "今天先补前端。",
                                "summary": "上午补前端。",
                                "role": {"scene_type_label": "自言自语"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                payload = app_server.get_date_detail("2026-04-08")

            self.assertNotIn("audio_ref", payload["scenes"]["scenes"][0])
            self.assertEqual(payload["segments"][0]["summary"], "上午补前端。")

    def test_audio_endpoint_serves_chunk_for_date_and_chunk_id(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            _, audio_bytes = self.seed_audio_workspace(project_root, "2026-04-08")

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                server = app_server.build_server(port=0)
                try:
                    import threading

                    base_url = f"http://127.0.0.1:{server.server_address[1]}"
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    with urlopen(f"{base_url}/api/audio/2026-04-08/chunk_0001", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers.get("Accept-Ranges"), "bytes")
                        self.assertEqual(response.headers.get("Content-Type"), "audio/mpeg")
                        self.assertEqual(response.read(), audio_bytes)
                finally:
                    server.shutdown()
                    server.server_close()

    def test_audio_endpoint_supports_http_range_requests(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            _, audio_bytes = self.seed_audio_workspace(project_root, "2026-04-08")

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                server = app_server.build_server(port=0)
                try:
                    import threading

                    base_url = f"http://127.0.0.1:{server.server_address[1]}"
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    request = Request(
                        f"{base_url}/api/audio/2026-04-08/chunk_0001",
                        headers={"Range": "bytes=2-5"},
                    )
                    with urlopen(request, timeout=2) as response:
                        self.assertEqual(response.status, 206)
                        self.assertEqual(response.headers.get("Content-Range"), f"bytes 2-5/{len(audio_bytes)}")
                        self.assertEqual(response.read(), audio_bytes[2:6])
                finally:
                    server.shutdown()
                    server.server_close()

    def test_audio_endpoint_returns_404_for_stale_or_outside_chunk_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            day_dir = self.seed_day_workspace(project_root, "2026-04-08")
            bad_audio_path = project_root / "outside.mp3"
            bad_audio_path.write_bytes(b"outside")
            (day_dir / "transcript.transcription.json").write_text(
                json.dumps(
                    {
                        "chunks": [
                            {
                                "chunk_id": "chunk_0001",
                                "chunk_path": str(bad_audio_path),
                                "time_label": "10:00",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                server = app_server.build_server(port=0)
                try:
                    import threading

                    base_url = f"http://127.0.0.1:{server.server_address[1]}"
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    with self.assertRaises(HTTPError) as ctx:
                        urlopen(f"{base_url}/api/audio/2026-04-08/chunk_0001", timeout=2)
                    self.assertEqual(ctx.exception.code, 404)
                finally:
                    server.shutdown()
                    server.server_close()

    def test_audio_endpoint_returns_416_for_invalid_range(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            _, audio_bytes = self.seed_audio_workspace(project_root, "2026-04-08")

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                server = app_server.build_server(port=0)
                try:
                    import threading

                    base_url = f"http://127.0.0.1:{server.server_address[1]}"
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    request = Request(
                        f"{base_url}/api/audio/2026-04-08/chunk_0001",
                        headers={"Range": f"bytes={len(audio_bytes)}-"},
                    )
                    with self.assertRaises(HTTPError) as ctx:
                        urlopen(request, timeout=2)
                    self.assertEqual(ctx.exception.code, 416)
                    self.assertEqual(ctx.exception.headers.get("Content-Range"), f"bytes */{len(audio_bytes)}")
                finally:
                    server.shutdown()
                    server.server_close()

    def test_date_meta_endpoint_returns_intents_and_facts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_day_workspace(project_root, "2026-04-08")

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                payload = app_server.get_date_meta_payload("2026-04-08")

            self.assertEqual(payload["intents"][0]["what"], "补前端")
            self.assertEqual(payload["facts"][0]["content"], "active_context 已接上")

    def test_date_briefing_endpoint_returns_daily_briefing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_day_workspace(project_root, "2026-04-08")

            with patch.object(app_server, "DATA_ROOT", data_root), patch.object(app_server, "LEGACY_ROOT", project_root):
                payload = app_server.get_date_briefing_payload("2026-04-08")

            self.assertEqual(payload["summary"], "今天主要推进前端补齐。")
            self.assertEqual(payload["key_events"], ["接上 active_context"])

    def test_handle_correction_syncs_transcript_scenes_and_briefing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            date_str = "2026-04-08"
            day_dir = data_root / date_str
            day_dir.mkdir(parents=True, exist_ok=True)

            (day_dir / "transcript.md").write_text(
                "# sample\n\n---\n\n## 10:00\n\n示例错名今天把 OpenMy 写完了。",
                encoding="utf-8",
            )
            (day_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "scenes": [
                            {
                                "scene_id": "scene_001",
                                "time_start": "10:00",
                                "time_end": "10:05",
                                "text": "示例错名今天把 OpenMy 写完了。",
                                "summary": "示例错名正在收尾。",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (day_dir / "daily_briefing.json").write_text(
                json.dumps(
                    {
                        "summary": "示例错名今天把 OpenMy 写完了。",
                        "key_events": ["示例错名完成第一版。"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            corrections_file = project_root / "src" / "openmy" / "resources" / "corrections.json"
            corrections_file.parent.mkdir(parents=True, exist_ok=True)

            with (
                patch.object(app_server, "DATA_ROOT", data_root),
                patch.object(app_server, "LEGACY_ROOT", project_root),
                patch.object(app_server, "CORRECTIONS_FILE", corrections_file),
                patch.object(app_server, "sync_correction_to_vocab"),
            ):
                payload = app_server.handle_correction(
                    {
                        "wrong": "示例错名",
                        "right": "示例正名",
                        "date": date_str,
                        "context": "示例昵称",
                        "sync_vocab": True,
                    }
                )

            transcript = (day_dir / "transcript.md").read_text(encoding="utf-8")
            scenes = json.loads((day_dir / "scenes.json").read_text(encoding="utf-8"))
            briefing = json.loads((day_dir / "daily_briefing.json").read_text(encoding="utf-8"))

            self.assertTrue(payload["success"])
            self.assertEqual(payload["replaced_in_file"], 1)
            self.assertIn("示例正名", transcript)
            self.assertNotIn("示例错名", transcript)
            self.assertIn("示例正名", scenes["scenes"][0]["text"])
            self.assertIn("示例正名", scenes["scenes"][0]["summary"])
            self.assertIn("示例正名", briefing["summary"])
            self.assertIn("示例正名", briefing["key_events"][0])

    def test_handle_correction_preserves_audio_ref(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            date_str = "2026-04-08"
            day_dir = data_root / date_str
            day_dir.mkdir(parents=True, exist_ok=True)

            (day_dir / "transcript.md").write_text(
                "# sample\n\n---\n\n## 10:00\n\n示例错名今天把 OpenMy 写完了。",
                encoding="utf-8",
            )
            (day_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "scenes": [
                            {
                                "scene_id": "scene_001",
                                "time_start": "10:00",
                                "time_end": "10:05",
                                "text": "示例错名今天把 OpenMy 写完了。",
                                "summary": "示例错名正在收尾。",
                                "audio_ref": {
                                    "chunk_id": "chunk_0001",
                                    "offset_start": 1.0,
                                    "offset_end": 3.0,
                                    "segment_ids": ["seg_0001"],
                                },
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            corrections_file = project_root / "src" / "openmy" / "resources" / "corrections.json"
            corrections_file.parent.mkdir(parents=True, exist_ok=True)

            with (
                patch.object(app_server, "DATA_ROOT", data_root),
                patch.object(app_server, "LEGACY_ROOT", project_root),
                patch.object(app_server, "CORRECTIONS_FILE", corrections_file),
                patch.object(app_server, "sync_correction_to_vocab"),
            ):
                payload = app_server.handle_correction(
                    {
                        "wrong": "示例错名",
                        "right": "示例正名",
                        "date": date_str,
                        "context": "示例昵称",
                        "sync_vocab": True,
                    }
                )

            scenes = json.loads((day_dir / "scenes.json").read_text(encoding="utf-8"))

            self.assertTrue(payload["success"])
            self.assertIn("示例正名", scenes["scenes"][0]["text"])
            self.assertIn("示例正名", scenes["scenes"][0]["summary"])
            self.assertEqual(scenes["scenes"][0]["audio_ref"]["chunk_id"], "chunk_0001")
            self.assertEqual(scenes["scenes"][0]["audio_ref"]["segment_ids"], ["seg_0001"])

    def test_freeze_scene_roles_preserves_audio_ref(self):
        from openmy.commands.show import freeze_scene_roles

        payload = {
            "scenes": [
                {
                    "scene_id": "scene_001",
                    "time_start": "10:00",
                    "time_end": "10:05",
                    "text": "今天先补前端。",
                    "role": {"scene_type_label": "自言自语", "needs_review": False},
                    "audio_ref": {
                        "chunk_id": "chunk_0001",
                        "offset_start": 1.2,
                        "offset_end": 3.6,
                        "segment_ids": ["seg_0001"],
                    },
                }
            ],
            "stats": {},
        }

        frozen = freeze_scene_roles(payload)

        self.assertEqual(frozen["scenes"][0]["audio_ref"]["chunk_id"], "chunk_0001")
        self.assertEqual(frozen["scenes"][0]["audio_ref"]["segment_ids"], ["seg_0001"])
        self.assertEqual(frozen["scenes"][0]["role"]["source"], "frozen")

    def test_close_loop_endpoint_appends_correction_and_refreshes_context(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            (data_root / "active_context.json").write_text(
                json.dumps(self.make_context_snapshot(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root):
                payload = app_server.handle_close_loop({"query": "补前端工作台", "status": "done"})

            updated = json.loads((data_root / "active_context.json").read_text(encoding="utf-8"))
            loop = next(item for item in updated["rolling_context"]["open_loops"] if item["title"] == "补前端工作台")
            corrections_log = (data_root / "corrections.jsonl").read_text(encoding="utf-8")

            self.assertTrue(payload["success"])
            self.assertEqual(loop["status"], "done")
            self.assertEqual(loop["current_state"], "closed")
            self.assertIn("close_loop", corrections_log)
            self.assertIn("loop_frontend", corrections_log)

    def test_reject_loop_endpoint_appends_correction_and_refreshes_context(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            (data_root / "active_context.json").write_text(
                json.dumps(self.make_context_snapshot(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root):
                payload = app_server.handle_reject_loop({"query": "清理未来测试日期"})

            updated = json.loads((data_root / "active_context.json").read_text(encoding="utf-8"))
            loop_titles = [item["title"] for item in updated["rolling_context"]["open_loops"]]
            corrections_log = (data_root / "corrections.jsonl").read_text(encoding="utf-8")

            self.assertTrue(payload["success"])
            self.assertNotIn("清理未来测试日期", loop_titles)
            self.assertIn("reject_loop", corrections_log)
            self.assertIn("loop_cleanup", corrections_log)

    def test_merge_project_endpoint_appends_correction_and_refreshes_context(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            (data_root / "active_context.json").write_text(
                json.dumps(self.make_context_snapshot(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root):
                payload = app_server.handle_merge_project({"source": "前端工作台", "target": "OpenMy"})

            updated = json.loads((data_root / "active_context.json").read_text(encoding="utf-8"))
            project_titles = [item["title"] for item in updated["rolling_context"]["active_projects"]]
            corrections_log = (data_root / "corrections.jsonl").read_text(encoding="utf-8")

            self.assertTrue(payload["success"])
            self.assertNotIn("前端工作台", project_titles)
            self.assertIn("OpenMy", project_titles)
            self.assertIn("merge_project", corrections_log)
            self.assertIn("project_frontend", corrections_log)

    def test_reject_decision_endpoint_appends_correction_and_refreshes_context(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            (data_root / "active_context.json").write_text(
                json.dumps(self.make_context_snapshot(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with patch.object(app_server, "DATA_ROOT", data_root):
                payload = app_server.handle_reject_decision({"query": "移动端放在补齐后一起验。"})

            updated = json.loads((data_root / "active_context.json").read_text(encoding="utf-8"))
            decisions = [item["decision"] for item in updated["rolling_context"]["recent_decisions"]]
            corrections_log = (data_root / "corrections.jsonl").read_text(encoding="utf-8")

            self.assertTrue(payload["success"])
            self.assertNotIn("移动端放在补齐后一起验。", decisions)
            self.assertIn("reject_decision", corrections_log)
            self.assertIn("decision_002", corrections_log)

    def test_create_pipeline_job_endpoint_accepts_context_kind(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = JobRunner(job_dir=Path(tmp_dir))

            def fake_run(kind, target_date, handle):
                handle.step(f"{kind} running")
                handle.log(f"{kind} started")

            with patch.object(app_server, "JOB_RUNNER", runner), patch.object(app_server, "run_pipeline_job_command", side_effect=fake_run):
                payload = app_server.handle_create_pipeline_job({"kind": "context"})
                self.wait_for_job_status(runner, payload["job_id"], "succeeded")

        self.assertEqual(payload["kind"], "context")
        self.assertIsNone(payload["target_date"])
        self.assertEqual(payload["status"], "queued")

    def test_create_pipeline_job_endpoint_accepts_run_kind(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = JobRunner(job_dir=Path(tmp_dir))

            def fake_run(kind, target_date, handle):
                handle.step(f"{kind} running")
                handle.log(f"{target_date} started")

            with patch.object(app_server, "JOB_RUNNER", runner), patch.object(app_server, "run_pipeline_job_command", side_effect=fake_run):
                payload = app_server.handle_create_pipeline_job({"kind": "run", "target_date": "2026-04-08"})
                self.wait_for_job_status(runner, payload["job_id"], "succeeded")

        self.assertEqual(payload["kind"], "run")
        self.assertEqual(payload["target_date"], "2026-04-08")
        self.assertEqual(payload["status"], "queued")

    def test_create_pipeline_job_endpoint_accepts_audio_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = JobRunner(job_dir=Path(tmp_dir))

            def fake_run(kind, target_date, handle):
                handle.step({"name": "transcribe", "label": "转写", "status": "running"})
                handle.log("audio pipeline started")

            audio_path = str(Path(tmp_dir) / "sample.wav")
            Path(audio_path).write_bytes(b"RIFFdemo")

            with patch.object(app_server, "JOB_RUNNER", runner), patch.object(app_server, "run_pipeline_job_command", side_effect=fake_run):
                payload = app_server.handle_create_pipeline_job(
                    {
                        "kind": "run",
                        "audio_files": [audio_path],
                        "source_file": "sample.wav",
                        "source_size_bytes": 8,
                    }
                )
                self.wait_for_job_status(runner, payload["job_id"], "succeeded")

        self.assertEqual(payload["source_file"], "sample.wav")
        self.assertEqual(payload["source_size_bytes"], 8)
        self.assertEqual(len(payload["steps"]), 4)

    def test_jobs_list_endpoint_returns_recent_jobs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = JobRunner(job_dir=Path(tmp_dir))

            def fake_run(kind, target_date, handle):
                handle.step(f"{kind} running")
                handle.log(f"{kind}:{target_date or 'none'}")

            with patch.object(app_server, "JOB_RUNNER", runner), patch.object(app_server, "run_pipeline_job_command", side_effect=fake_run):
                first = app_server.handle_create_pipeline_job({"kind": "context"})
                second = app_server.handle_create_pipeline_job({"kind": "run", "target_date": "2026-04-08"})

                self.wait_for_job_status(runner, first["job_id"], "succeeded")
                self.wait_for_job_status(runner, second["job_id"], "succeeded")
                payload = app_server.get_pipeline_jobs_payload()

        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["job_id"], second["job_id"])
        self.assertEqual(payload[1]["job_id"], first["job_id"])

    def test_job_detail_endpoint_returns_status_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = JobRunner(job_dir=Path(tmp_dir))

            def fake_run(kind, target_date, handle):
                handle.step("render briefing")
                handle.log("briefing started")

            with patch.object(app_server, "JOB_RUNNER", runner), patch.object(app_server, "run_pipeline_job_command", side_effect=fake_run):
                created = app_server.handle_create_pipeline_job({"kind": "context"})
                self.wait_for_job_status(runner, created["job_id"], "succeeded")
                payload = app_server.get_pipeline_job_payload(created["job_id"])

        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["current_step"], "render briefing")
        self.assertIn("briefing started", payload["log_lines"])


if __name__ == "__main__":
    unittest.main()
