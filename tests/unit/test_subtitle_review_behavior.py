#!/usr/bin/env python3
import json
import math
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import app.server as app_server
from app.job_runner import JobRunner


class TestSubtitleReviewBehavior(unittest.TestCase):
    def start_server(self, data_root: Path, legacy_root: Path, runner: JobRunner):
        patches = [
            patch.object(app_server, "DATA_ROOT", data_root),
            patch.object(app_server, "LEGACY_ROOT", legacy_root),
            patch.object(app_server, "ROOT_DIR", legacy_root),
            patch.object(app_server, "JOB_RUNNER", runner),
            patch("app.payloads.get_stt_provider_name", return_value=""),
            patch("app.payloads.get_stt_api_key", return_value=""),
        ]
        for item in patches:
            item.start()

        server = app_server.build_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        return server, patches, base_url

    def stop_server(self, server, patches):
        server.shutdown()
        server.server_close()
        for item in reversed(patches):
          item.stop()

    def write_test_wav(self, path: Path, duration_seconds: float = 2.4, sample_rate: int = 16000) -> None:
        frame_count = int(duration_seconds * sample_rate)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            frames = bytearray()
            for index in range(frame_count):
                value = int(8000 * math.sin(2 * math.pi * 220 * (index / sample_rate)))
                frames.extend(struct.pack("<h", value))
            wav_file.writeframes(bytes(frames))

    def seed_day_workspace(self, project_root: Path, date_str: str) -> None:
        day_dir = project_root / "data" / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "transcript.md").write_text(
            "# sample\n\n---\n\n## 14:27\n\n要，稍稍看一下那个别人是怎么配的。",
            encoding="utf-8",
        )
        (day_dir / f"{date_str}.meta.json").write_text(
            json.dumps({"daily_summary": "今天主要在看技能配置。"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (day_dir / "daily_briefing.json").write_text(
            json.dumps({"summary": "今天主要在看技能配置。"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        chunk_dir = day_dir / "stt_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        audio_path = chunk_dir / "audio_001_sub_0000.wav"
        self.write_test_wav(audio_path)

        scene_text = (
            "要，稍稍看一下那个别人是怎么配的。"
            "我的意思是按照我刚才说的这个工作流。"
            "今天同时安装你这个 skill 中间有冲突吗？"
        )
        speech_segments = [
            {"start": 0.2, "end": 0.6},
            {"start": 0.85, "end": 1.4},
            {"start": 1.55, "end": 2.2},
        ]

        (day_dir / "transcript.transcription.json").write_text(
            json.dumps(
                {
                    "chunks": [
                        {
                            "chunk_id": "chunk_0001",
                            "chunk_path": str(audio_path),
                            "time_label": "14:27",
                            "text": scene_text,
                            "duration_seconds": 2.4,
                            "speech_segments": speech_segments,
                            "segments": [
                                {
                                    "id": "seg_0001",
                                    "text": scene_text,
                                    "start": 0.0,
                                    "end": 2.4,
                                    "words": [],
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        (day_dir / "scenes.json").write_text(
            json.dumps(
                {
                    "scenes": [
                        {
                            "scene_id": "s01",
                            "time_start": "14:27",
                            "time_end": "14:57",
                            "text": scene_text,
                            "summary": "我决定清理冗余技能并优化工作流。",
                            "audio_ref": {
                                "chunk_id": "chunk_0001",
                                "offset_start": 0.0,
                                "offset_end": 2.4,
                                "duration_seconds": 2.4,
                                "speech_segments": speech_segments,
                            },
                            "transcription_evidence": [
                                {
                                    "chunk_id": "chunk_0001",
                                    "segment_id": "seg_0001",
                                    "text": scene_text,
                                    "start": 0.0,
                                    "end": 2.4,
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def test_smart_audio_player_v2_behavior_in_real_browser(self):
        if shutil.which("node") is None:
            self.skipTest("node 不可用")

        try:
            subprocess.run(
                ["node", "-e", "require('playwright');console.log('ok')"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"playwright 不可用: {exc}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            data_root = project_root / "data"
            data_root.mkdir(parents=True, exist_ok=True)
            self.seed_day_workspace(project_root, "2026-04-18")

            runner = JobRunner()
            server, patches, base_url = self.start_server(data_root, project_root, runner)
            try:
                script = Path(__file__).resolve().parents[1] / "browser" / "smart_audio_player_v2_behavior.cjs"
                result = subprocess.run(
                    ["node", str(script), base_url],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
            finally:
                self.stop_server(server, patches)

            if result.returncode != 0:
                self.fail(
                    "浏览器行为测试失败\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)


if __name__ == "__main__":
    unittest.main()
