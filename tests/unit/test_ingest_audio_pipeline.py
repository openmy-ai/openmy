import tempfile
import unittest
from pathlib import Path
from unittest import mock


from openmy.services.ingest.audio_pipeline import (
    PreparedChunk,
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
    def test_returns_empty_when_stripped_audio_too_short(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "TX01_MIC005_20260408_131552_orig.wav"
            audio_path.write_bytes(b"wav")

            with (
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.run_ffmpeg",
                    side_effect=[None],
                ) as ffmpeg_mock,
                mock.patch(
                    "openmy.services.ingest.audio_pipeline.probe_duration_seconds",
                    return_value=2,
                ),
            ):
                chunks = prepare_audio_chunks(audio_path, Path(tmp_dir), chunk_minutes=10)

            self.assertEqual(chunks, [])
            self.assertEqual(ffmpeg_mock.call_count, 1)


class TranscribeAudioFilesTest(unittest.TestCase):
    def test_uses_sidecar_transcript_when_api_key_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "sample.wav"
            sidecar = tmp_path / "sample.transcript.txt"
            audio_one.write_bytes(b"wav")
            sidecar.write_text("老婆，今天晚上吃火锅。", encoding="utf-8")

            with (
                mock.patch.dict("os.environ", {}, clear=True),
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
            self.assertIn("老婆，今天晚上吃火锅。", content)

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
                mock.patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}),
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
                    side_effect=["第一段", "第二段-1", "第二段-2"],
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
            self.assertEqual(used_chunk_paths, [chunk_one, chunk_two, chunk_three])

    def test_retries_gemini_chunk_before_failing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_one = tmp_path / "TX01_MIC005_20260408_131552_orig.wav"
            audio_one.write_bytes(b"wav")

            chunk_one = tmp_path / "seg_1.mp3"
            chunk_one.write_bytes(b"mp3")

            with (
                mock.patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}),
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
                    side_effect=[RuntimeError("Premature close"), RuntimeError("Premature close"), "第三次成功"],
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


if __name__ == "__main__":
    unittest.main()
