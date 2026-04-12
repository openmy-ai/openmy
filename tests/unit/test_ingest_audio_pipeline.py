import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock


from openmy.services.ingest.audio_pipeline import (
    PreparedChunk,
    discover_audio_files_for_date,
    offset_time_label,
    prepare_audio_chunks,
    transcribe_audio_files,
)


class OffsetTimeLabelTest(unittest.TestCase):
    def test_offsets_minutes_from_base_time(self):
        self.assertEqual(offset_time_label("13:15", 0), "13:15")
        self.assertEqual(offset_time_label("13:15", 10), "13:25")
        self.assertEqual(offset_time_label("13:15", 70), "14:25")

    def test_returns_fallback_when_base_time_missing(self):
        self.assertEqual(offset_time_label("", 0), "00:00")
        self.assertEqual(offset_time_label("", 20), "00:20")


class PrepareAudioChunksTest(unittest.TestCase):
    def test_falls_back_to_original_audio_when_stripped_audio_too_short(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "TX01_MIC005_20260408_131552_orig.wav"
            audio_path.write_bytes(b"wav")

            with (
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.run_ffmpeg",
                    side_effect=[None, None],
                ) as ffmpeg_mock,
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.probe_duration_seconds",
                    side_effect=[2, 12],
                ),
            ):
                chunks = prepare_audio_chunks(audio_path, Path(tmp_dir), chunk_minutes=10)

            self.assertEqual(len(chunks), 1)
            self.assertEqual(chunks[0].time_label, "13:15")
            self.assertEqual(ffmpeg_mock.call_count, 2)

    def test_funasr_prefers_wav_chunks_instead_of_mp3(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "TX01_MIC005_20260408_131552_orig.wav"
            audio_path.write_bytes(b"wav")

            with (
                mock.patch("openmy.services.ingest.audio_pipeline.run_ffmpeg", side_effect=[None]) as ffmpeg_mock,
                mock.patch("openmy.services.ingest.audio_pipeline.probe_duration_seconds", side_effect=[12, 12]),
            ):
                chunks = prepare_audio_chunks(
                    audio_path,
                    Path(tmp_dir),
                    chunk_minutes=10,
                    provider_name="funasr",
                )

            self.assertEqual(len(chunks), 1)
            self.assertEqual(chunks[0].path.suffix, ".wav")
            self.assertEqual(ffmpeg_mock.call_count, 1)


class TranscribeAudioFilesTest(unittest.TestCase):
    def test_discover_audio_files_for_date_uses_modified_day_only(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            today_audio = root / "today.wav"
            other_audio = root / "other.wav"
            nested_audio = root / "nested" / "voice.m4a"
            nested_audio.parent.mkdir(parents=True, exist_ok=True)
            for path in [today_audio, other_audio, nested_audio]:
                path.write_bytes(b"audio")

            target_ts = datetime(2026, 4, 12, 9, 30).timestamp()
            old_ts = datetime(2026, 4, 11, 9, 30).timestamp()
            os.utime(today_audio, (target_ts, target_ts))
            os.utime(nested_audio, (target_ts + 10, target_ts + 10))
            os.utime(other_audio, (old_ts, old_ts))

            discovered = discover_audio_files_for_date(root, "2026-04-12")

            self.assertEqual(discovered, [str(today_audio.resolve()), str(nested_audio.resolve())])

    def test_uses_vocab_example_when_private_vocab_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "sample.wav"
            sidecar = tmp_path / "sample.transcript.txt"
            audio_one.write_bytes(b"wav")
            sidecar.write_text("伴侣，今天晚上吃火锅。", encoding="utf-8")
            vocab_example = tmp_path / "vocab.example.txt"
            vocab_example.write_text("Claude | Anthropic 的 AI 模型", encoding="utf-8")

            with (
                mock.patch.dict(
                    "os.environ",
                    {"OPENMY_STT_PROVIDER": "gemini"},
                    clear=True,
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.load_vocab_terms",
                    return_value="Claude | Anthropic 的 AI 模型",
                ) as load_vocab_mock,
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.VOCAB_FILE",
                    tmp_path / "vocab.txt",
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.VOCAB_EXAMPLE_FILE",
                    vocab_example,
                ),
            ):
                transcribe_audio_files(
                    date_str="2026-04-10",
                    audio_files=[str(audio_one)],
                    output_dir=tmp_path,
                )

            load_vocab_mock.assert_called_once_with(vocab_example)

    def test_uses_sidecar_transcript_when_api_key_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "sample.wav"
            sidecar = tmp_path / "sample.transcript.txt"
            audio_one.write_bytes(b"wav")
            sidecar.write_text("伴侣，今天晚上吃火锅。", encoding="utf-8")

            with (
                mock.patch.dict(
                    "os.environ",
                    {"OPENMY_STT_PROVIDER": "gemini"},
                    clear=True,
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.load_vocab_terms",
                    return_value="OpenMy",
                ),
            ):
                output_path = transcribe_audio_files(
                    date_str="2026-04-10",
                    audio_files=[str(audio_one)],
                    output_dir=tmp_path,
                )

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("## 00:00", content)
            self.assertIn("伴侣，今天晚上吃火锅。", content)

            structured_path = tmp_path / "transcript.transcription.json"
            self.assertTrue(structured_path.exists())
            payload = json.loads(structured_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider"], "gemini")
            self.assertEqual(payload["chunks"], [])

    def test_writes_structured_transcription_artifact_for_local_provider(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "TX01_MIC005_20260408_131552_orig.wav"
            audio_one.write_bytes(b"wav")

            chunk_one = tmp_path / "seg_1.mp3"
            chunk_one.write_bytes(b"mp3")

            fake_result = {
                "text": "第一段",
                "language": "zh",
                "duration_seconds": 12.3,
                "segments": [
                    {
                        "id": "seg_0001",
                        "text": "第一段",
                        "start": 0.0,
                        "end": 12.3,
                        "speaker": "",
                        "words": [],
                    }
                ],
                "provider_metadata": {"provider": "faster-whisper", "model": "small"},
            }

            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "OPENMY_STT_PROVIDER": "faster-whisper",
                        "OPENMY_STT_MODEL": "small",
                    },
                    clear=True,
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.prepare_audio_chunks",
                    return_value=[PreparedChunk(path=chunk_one, time_label="13:15")],
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.load_vocab_terms",
                    return_value="OpenMy",
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.transcribe_audio",
                    return_value=fake_result,
                ),
            ):
                output_path = transcribe_audio_files(
                    date_str="2026-04-08",
                    audio_files=[str(audio_one)],
                    output_dir=tmp_path,
                )

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("第一段", content)

            structured_path = tmp_path / "transcript.transcription.json"
            self.assertTrue(structured_path.exists())
            payload = json.loads(structured_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider"], "faster-whisper")
            self.assertEqual(payload["chunks"][0]["time_label"], "13:15")
            self.assertTrue(Path(payload["chunks"][0]["chunk_path"]).exists())

    def test_writes_structured_transcription_artifact_for_funasr_provider(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "TX01_MIC005_20260408_131552_orig.wav"
            audio_one.write_bytes(b"wav")

            chunk_one = tmp_path / "seg_1.mp3"
            chunk_one.write_bytes(b"mp3")

            fake_result = {
                "text": "你好世界",
                "language": "zh",
                "duration_seconds": 1.1,
                "segments": [
                    {
                        "id": "seg_0001",
                        "text": "你好",
                        "start": 0.0,
                        "end": 0.62,
                        "speaker": "",
                        "words": [],
                    },
                    {
                        "id": "seg_0002",
                        "text": "世界",
                        "start": 0.62,
                        "end": 1.1,
                        "speaker": "",
                        "words": [],
                    },
                ],
                "provider_metadata": {"provider": "funasr", "model": "paraformer-zh"},
            }

            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "OPENMY_STT_PROVIDER": "funasr",
                        "OPENMY_STT_MODEL": "paraformer-zh",
                    },
                    clear=True,
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.prepare_audio_chunks",
                    return_value=[PreparedChunk(path=chunk_one, time_label="13:15")],
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.load_vocab_terms",
                    return_value="OpenMy",
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.transcribe_audio",
                    return_value=fake_result,
                ),
            ):
                output_path = transcribe_audio_files(
                    date_str="2026-04-08",
                    audio_files=[str(audio_one)],
                    output_dir=tmp_path,
                )

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("你好世界", content)

            structured_path = tmp_path / "transcript.transcription.json"
            payload = json.loads(structured_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider"], "funasr")
            self.assertEqual(len(payload["chunks"][0]["segments"]), 2)

    def test_uses_prepared_chunks_instead_of_raw_audio(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "TX01_MIC005_20260408_131552_orig.wav"
            audio_two = tmp_path / "TX01_MIC006_20260408_134552_orig.wav"
            audio_one.write_bytes(b"wav")
            audio_two.write_bytes(b"wav")

            chunk_one = tmp_path / "seg_1.mp3"
            chunk_two = tmp_path / "sub_0001.mp3"
            chunk_three = tmp_path / "sub_0002.mp3"
            chunk_one.write_bytes(b"mp3")
            chunk_two.write_bytes(b"mp3")
            chunk_three.write_bytes(b"mp3")

            prepared = [
                [PreparedChunk(path=chunk_one, time_label="13:15")],
                [
                    PreparedChunk(path=chunk_two, time_label="13:45"),
                    PreparedChunk(path=chunk_three, time_label="13:55"),
                ],
            ]

            with (
                mock.patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key", "OPENMY_STT_PROVIDER": "gemini"}),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.prepare_audio_chunks",
                    side_effect=prepared,
                ) as prepare_mock,
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.load_vocab_terms",
                    return_value="OpenMy",
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.transcribe_audio",
                    side_effect=[
                        {"text": "第一段", "language": "zh", "duration_seconds": 1.0, "segments": [], "provider_metadata": {}},
                        {"text": "第二段-1", "language": "zh", "duration_seconds": 1.0, "segments": [], "provider_metadata": {}},
                        {"text": "第二段-2", "language": "zh", "duration_seconds": 1.0, "segments": [], "provider_metadata": {}},
                    ],
                ) as transcribe_mock,
            ):
                output_path = transcribe_audio_files(
                    date_str="2026-04-08",
                    audio_files=[str(audio_one), str(audio_two)],
                    output_dir=tmp_path,
                )

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("## 13:15", content)
            self.assertIn("## 13:45", content)
            self.assertIn("## 13:55", content)
            self.assertIn("第一段", content)
            self.assertIn("第二段-1", content)
            self.assertIn("第二段-2", content)

            prepare_calls = [call.kwargs["audio_path"] for call in prepare_mock.call_args_list]
            self.assertEqual(prepare_calls, [audio_one.resolve(), audio_two.resolve()])

            used_chunk_paths = [call.kwargs["audio_path"] for call in transcribe_mock.call_args_list]
            self.assertEqual(
                used_chunk_paths,
                [
                    tmp_path / "stt_chunks" / "audio_001_seg_1.mp3",
                    tmp_path / "stt_chunks" / "audio_002_sub_0001.mp3",
                    tmp_path / "stt_chunks" / "audio_002_sub_0002.mp3",
                ],
            )

    def test_retries_gemini_chunk_before_failing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "TX01_MIC005_20260408_131552_orig.wav"
            audio_one.write_bytes(b"wav")

            chunk_one = tmp_path / "seg_1.mp3"
            chunk_one.write_bytes(b"mp3")

            with (
                mock.patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key", "OPENMY_STT_PROVIDER": "gemini"}, clear=True),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.prepare_audio_chunks",
                    return_value=[PreparedChunk(path=chunk_one, time_label="13:15")],
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.load_vocab_terms",
                    return_value="OpenMy",
                ),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.transcribe_audio",
                    side_effect=[
                        RuntimeError("Premature close"),
                        RuntimeError("Premature close"),
                        {"text": "第三次成功", "language": "zh", "duration_seconds": 1.0, "segments": [], "provider_metadata": {}},
                    ],
                ) as transcribe_mock,
                mock.patch("openmy.services.ingest.audio_pipeline.time.sleep") as sleep_mock,
            ):
                output_path = transcribe_audio_files(
                    date_str="2026-04-08",
                    audio_files=[str(audio_one)],
                    output_dir=tmp_path,
                )

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("第三次成功", content)
            self.assertEqual(transcribe_mock.call_count, 3)
            self.assertEqual(sleep_mock.call_count, 2)

    def test_cloud_provider_uses_thread_pool_for_chunks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "TX01_MIC005_20260408_131552_orig.wav"
            audio_one.write_bytes(b"wav")

            chunk_one = tmp_path / "seg_1.mp3"
            chunk_two = tmp_path / "seg_2.mp3"
            chunk_one.write_bytes(b"mp3")
            chunk_two.write_bytes(b"mp3")

            class FakeExecutor:
                def __init__(self, *args, **kwargs):
                    self.max_workers = kwargs.get("max_workers")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def map(self, fn, jobs):
                    return [fn(job) for job in jobs]

            with (
                mock.patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key", "OPENMY_STT_PROVIDER": "gemini"}, clear=True),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.prepare_audio_chunks",
                    return_value=[
                        PreparedChunk(path=chunk_one, time_label="13:15"),
                        PreparedChunk(path=chunk_two, time_label="13:25"),
                    ],
                ),
                mock.patch("openmy.services.ingest.audio_pipeline.load_vocab_terms", return_value="OpenMy"),
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.transcribe_audio",
                    side_effect=[
                        {"text": "第一段", "language": "zh", "duration_seconds": 1.0, "segments": [], "provider_metadata": {}},
                        {"text": "第二段", "language": "zh", "duration_seconds": 1.0, "segments": [], "provider_metadata": {}},
                    ],
                ),
                mock.patch("openmy.services.ingest.audio_pipeline.ThreadPoolExecutor", side_effect=lambda *a, **k: FakeExecutor(*a, **k)) as executor_mock,
            ):
                output_path = transcribe_audio_files(
                    date_str="2026-04-08",
                    audio_files=[str(audio_one)],
                    output_dir=tmp_path,
                )

            self.assertTrue(output_path.exists())
            executor_mock.assert_called_once_with(max_workers=5)


if __name__ == "__main__":
    unittest.main()
