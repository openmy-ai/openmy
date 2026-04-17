#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openmy.services.ingest.transcription_enrichment import (
    apply_transcription_enrichment_to_scenes,
    plan_transcription_enrichment,
)


class TestTranscriptionEnrichmentPlanning(unittest.TestCase):
    def test_recommended_mode_enables_whisperx_for_local_provider(self):
        with patch("openmy.services.ingest.transcription_enrichment.whisperx", object()):
            plan = plan_transcription_enrichment(
                provider_name="faster-whisper",
                enrich_mode="recommended",
                diarize_requested=False,
            )

        self.assertTrue(plan["enabled"])
        self.assertTrue(plan["align"])
        self.assertEqual(plan["status"], "recommended")

    def test_recommended_mode_degrades_diarization_when_token_missing(self):
        with patch("openmy.services.ingest.transcription_enrichment.whisperx", object()):
            plan = plan_transcription_enrichment(
                provider_name="funasr",
                enrich_mode="recommended",
                diarize_requested=True,
                diarization_token="",
            )

        self.assertTrue(plan["enabled"])
        self.assertFalse(plan["diarize"])
        self.assertEqual(plan["diarization_status"], "degraded_missing_token")

    def test_force_mode_surfaces_missing_dependency_as_failure(self):
        with patch("openmy.services.ingest.transcription_enrichment.whisperx", None):
            plan = plan_transcription_enrichment(
                provider_name="faster-whisper",
                enrich_mode="force",
                diarize_requested=True,
            )

        self.assertFalse(plan["enabled"])
        self.assertEqual(plan["status"], "failed")
        self.assertIn("whisperx", plan["message"].lower())


class TestApplyTranscriptionEnrichmentToScenes(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_scene(self, day_dir: Path) -> dict:
        payload = json.loads((day_dir / "scenes.json").read_text(encoding="utf-8"))
        return payload["scenes"][0]

    def read_scenes(self, day_dir: Path) -> list[dict]:
        payload = json.loads((day_dir / "scenes.json").read_text(encoding="utf-8"))
        return payload["scenes"]

    def test_apply_transcription_enrichment_to_scenes_adds_audio_ref_from_single_chunk_evidence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            day_dir = Path(tmp_dir)
            self.write_json(
                day_dir / "scenes.json",
                {
                    "scenes": [
                        {
                            "scene_id": "scene_001",
                            "time_start": "10:00",
                            "time_end": "10:05",
                            "text": "alpha",
                        }
                    ]
                },
            )
            self.write_json(
                day_dir / "transcript.transcription.json",
                {
                    "chunks": [
                        {
                            "chunk_id": "chunk_0001",
                            "time_label": "10:00",
                            "aligned_segments": [
                                {"id": "seg_0001", "start": 1.2, "end": 2.4, "text": "alpha"},
                                {"id": "seg_0002", "start": 4.0, "end": 5.5, "text": "beta"},
                            ],
                        }
                    ]
                },
            )

            apply_transcription_enrichment_to_scenes(day_dir)
            scene = self.read_scene(day_dir)

            self.assertEqual(scene["transcription_evidence"][0]["chunk_id"], "chunk_0001")
            self.assertEqual(scene["audio_ref"]["chunk_id"], "chunk_0001")
            self.assertEqual(scene["audio_ref"]["offset_start"], 1.2)
            self.assertEqual(scene["audio_ref"]["offset_end"], 5.5)
            self.assertEqual(scene["audio_ref"]["segment_ids"], ["seg_0001", "seg_0002"])
            self.assertNotIn("chunk_path", scene["audio_ref"])

    def test_apply_transcription_enrichment_to_scenes_skips_audio_ref_when_evidence_spans_multiple_chunks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            day_dir = Path(tmp_dir)
            self.write_json(
                day_dir / "scenes.json",
                {
                    "scenes": [
                        {
                            "scene_id": "scene_001",
                            "time_start": "10:00",
                            "time_end": "10:05",
                            "text": "alpha",
                            "audio_ref": {"chunk_id": "stale"},
                        }
                    ]
                },
            )
            self.write_json(
                day_dir / "transcript.transcription.json",
                {
                    "chunks": [
                        {
                            "chunk_id": "chunk_0001",
                            "time_label": "10:00",
                            "aligned_segments": [
                                {"id": "seg_0001", "chunk_id": "chunk_0001", "start": 0.2, "end": 1.0, "text": "alpha"},
                                {"id": "seg_0002", "chunk_id": "chunk_0002", "start": 1.5, "end": 2.0, "text": "beta"},
                            ],
                        }
                    ]
                },
            )

            apply_transcription_enrichment_to_scenes(day_dir)
            scene = self.read_scene(day_dir)

            self.assertEqual(
                {item["chunk_id"] for item in scene["transcription_evidence"]},
                {"chunk_0001", "chunk_0002"},
            )
            self.assertNotIn("audio_ref", scene)

    def test_apply_transcription_enrichment_to_scenes_skips_audio_ref_when_evidence_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            day_dir = Path(tmp_dir)
            self.write_json(
                day_dir / "scenes.json",
                {
                    "scenes": [
                        {
                            "scene_id": "scene_001",
                            "time_start": "10:00",
                            "time_end": "10:05",
                            "text": "alpha",
                        }
                    ]
                },
            )
            self.write_json(
                day_dir / "transcript.transcription.json",
                {
                    "chunks": [
                        {
                            "chunk_id": "chunk_0001",
                            "time_label": "10:00",
                            "aligned_segments": [],
                            "segments": [],
                        }
                    ]
                },
            )

            apply_transcription_enrichment_to_scenes(day_dir)
            scene = self.read_scene(day_dir)

            self.assertEqual(scene["transcription_evidence"], [])
            self.assertNotIn("audio_ref", scene)

    def test_apply_transcription_enrichment_to_scenes_maps_repeated_text_by_time_not_text(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            day_dir = Path(tmp_dir)
            self.write_json(
                day_dir / "scenes.json",
                {
                    "scenes": [
                        {
                            "scene_id": "scene_001",
                            "time_start": "10:00",
                            "time_end": "10:05",
                            "text": "重复文本",
                        },
                        {
                            "scene_id": "scene_002",
                            "time_start": "10:10",
                            "time_end": "10:15",
                            "text": "重复文本",
                        },
                    ]
                },
            )
            self.write_json(
                day_dir / "transcript.transcription.json",
                {
                    "chunks": [
                        {
                            "chunk_id": "chunk_0001",
                            "time_label": "10:00",
                            "aligned_segments": [
                                {"id": "seg_0001", "start": 0.1, "end": 1.5, "text": "重复文本"},
                            ],
                        },
                        {
                            "chunk_id": "chunk_0002",
                            "time_label": "10:10",
                            "aligned_segments": [
                                {"id": "seg_0002", "start": 0.2, "end": 1.8, "text": "重复文本"},
                            ],
                        },
                    ]
                },
            )

            apply_transcription_enrichment_to_scenes(day_dir)
            scenes = self.read_scenes(day_dir)

            self.assertEqual(scenes[0]["text"], scenes[1]["text"])
            self.assertEqual(scenes[0]["audio_ref"]["chunk_id"], "chunk_0001")
            self.assertEqual(scenes[1]["audio_ref"]["chunk_id"], "chunk_0002")
            self.assertEqual(scenes[0]["audio_ref"]["segment_ids"], ["seg_0001"])
            self.assertEqual(scenes[1]["audio_ref"]["segment_ids"], ["seg_0002"])
