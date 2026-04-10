#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from openmy.services.ingest.transcription_enrichment import plan_transcription_enrichment


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
