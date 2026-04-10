#!/usr/bin/env python3
import json
import unittest
from unittest.mock import patch

from openmy.domain.models import RoleTag, SceneBlock, ScreenSession
from openmy.services.roles.resolver import resolve_roles
from openmy.services.screen_recognition.hints import (
    APP_ROLE_HINTS,
    apply_hints,
    enrich_with_hints,
    get_role_hint,
    sessionize,
)
from openmy.adapters.screen_recognition.client import ScreenEvent, ScreenRecognitionClient


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = payload or {}

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


class TestScreenRecognitionClient(unittest.TestCase):
    def test_is_available_returns_true_on_200(self):
        client = ScreenRecognitionClient(base_url="http://localhost:3030", timeout=1)
        with patch("urllib.request.urlopen", return_value=FakeResponse(status=200)) as mocked:
            self.assertTrue(client.is_available())
        self.assertIn("/health", mocked.call_args.args[0].full_url)

    def test_is_available_returns_false_on_error(self):
        client = ScreenRecognitionClient(base_url="http://localhost:3030", timeout=1)
        with patch("urllib.request.urlopen", side_effect=OSError("boom")):
            self.assertFalse(client.is_available())

    def test_search_ocr_maps_response_and_truncates_text(self):
        client = ScreenRecognitionClient(base_url="http://localhost:3030", timeout=1)
        payload = {
            "data": [
                {
                    "content": {
                        "app_name": "Claude",
                        "window_name": "Chat Window",
                        "timestamp": "2026-04-07T12:00:00+08:00",
                        "frame_id": 42,
                        "text": "x" * 250,
                        "browser_url": "https://claude.ai/chat",
                    }
                }
            ]
        }
        with patch("urllib.request.urlopen", return_value=FakeResponse(payload=payload)) as mocked:
            events = client.search_ocr(
                start_time="2026-04-07T12:00:00+08:00",
                end_time="2026-04-07T12:00:59+08:00",
                app_name="Claude",
            )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].app_name, "Claude")
        self.assertEqual(events[0].frame_id, 42)
        self.assertEqual(len(events[0].text), 200)
        self.assertIn("content_type=ocr", mocked.call_args.args[0].full_url)
        self.assertIn("app_name=Claude", mocked.call_args.args[0].full_url)

    def test_search_ocr_returns_empty_on_error(self):
        client = ScreenRecognitionClient(base_url="http://localhost:3030", timeout=1)
        with patch("urllib.request.urlopen", side_effect=OSError("boom")):
            self.assertEqual(
                client.search_ocr(
                    start_time="2026-04-07T12:00:00+08:00",
                    end_time="2026-04-07T12:00:59+08:00",
                ),
                [],
            )


class TestGetRoleHint(unittest.TestCase):
    def test_role_hints_cover_expected_buckets(self):
        self.assertIn("ai", APP_ROLE_HINTS)
        self.assertIn("interpersonal", APP_ROLE_HINTS)
        self.assertIn("merchant", APP_ROLE_HINTS)

    def test_claude_is_ai(self):
        role, boost = get_role_hint("Claude", "")
        self.assertEqual(role, "ai")
        self.assertGreater(boost, 0)

    def test_wechat_is_interpersonal(self):
        role, boost = get_role_hint("WeChat", "")
        self.assertEqual(role, "interpersonal")
        self.assertGreater(boost, 0)

    def test_taobao_is_merchant(self):
        role, boost = get_role_hint("淘宝", "")
        self.assertEqual(role, "merchant")
        self.assertGreater(boost, 0)

    def test_unknown_app_has_no_hint(self):
        role, boost = get_role_hint("Finder", "")
        self.assertEqual(role, "")
        self.assertEqual(boost, 0.0)


class TestSessionize(unittest.TestCase):
    def test_empty_events_returns_empty_sessions(self):
        self.assertEqual(sessionize([]), [])

    def test_groups_same_app_and_window(self):
        events = [
            ScreenEvent(
                app_name="Claude",
                window_name="Daily Context",
                timestamp="2026-04-07T12:00:00+08:00",
                frame_id=1,
            ),
            ScreenEvent(
                app_name="Claude",
                window_name="Daily Context",
                timestamp="2026-04-07T12:00:10+08:00",
                frame_id=2,
            ),
            ScreenEvent(
                app_name="WeChat",
                window_name="和老婆聊天",
                timestamp="2026-04-07T12:01:00+08:00",
                frame_id=3,
            ),
        ]

        sessions = sessionize(events)

        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].app_name, "Claude")
        self.assertEqual(sessions[0].frame_ids, [1, 2])
        self.assertEqual(sessions[0].role_hint, "ai")
        self.assertEqual(sessions[1].role_hint, "interpersonal")


class TestApplyHints(unittest.TestCase):
    def _make_scene(self, scene_type, confidence):
        scene = SceneBlock(time_start="12:00", time_end="12:01", text="test")
        scene.role = RoleTag(
            category=scene_type,
            scene_type=scene_type,
            scene_type_label=scene_type,
            confidence=confidence,
            evidence_chain=[],
        )
        return scene

    def test_high_confidence_scene_is_not_overridden(self):
        scene = self._make_scene("interpersonal", 0.95)
        sessions = [ScreenSession(app_name="Claude", role_hint="ai")]

        apply_hints(scene, sessions)

        self.assertEqual(scene.role.scene_type, "interpersonal")
        self.assertEqual(scene.screen_sessions, sessions)

    def test_matching_hint_boosts_confidence(self):
        scene = self._make_scene("ai", 0.6)
        sessions = [ScreenSession(app_name="Claude", role_hint="ai")]

        apply_hints(scene, sessions)

        self.assertAlmostEqual(scene.role.confidence, 0.7)
        self.assertIn("Claude", scene.role.evidence_chain[0])

    def test_uncertain_scene_uses_hint_as_fallback(self):
        scene = self._make_scene("uncertain", 0.0)
        sessions = [ScreenSession(app_name="WeChat", role_hint="interpersonal")]

        apply_hints(scene, sessions)

        self.assertEqual(scene.role.scene_type, "interpersonal")
        self.assertEqual(scene.role.source, "screen_hint")
        self.assertTrue(scene.role.needs_review)

    def test_conflicting_low_confidence_marks_review(self):
        scene = self._make_scene("ai", 0.5)
        sessions = [ScreenSession(app_name="WeChat", role_hint="interpersonal")]

        apply_hints(scene, sessions)

        self.assertTrue(scene.role.needs_review)


class StubScreenRecognitionClient:
    def __init__(self, available=True, events=None):
        self.available = available
        self.events = events or []
        self.calls = []

    def is_available(self):
        return self.available

    def search_ocr(self, start_time, end_time, app_name=None, limit=100):
        self.calls.append(
            {
                "start_time": start_time,
                "end_time": end_time,
                "app_name": app_name,
                "limit": limit,
            }
        )
        return list(self.events)


class TestEnrichWithHints(unittest.TestCase):
    def test_skips_when_client_unavailable(self):
        scene = SceneBlock(time_start="12:00", time_end="12:01", text="test")
        scene.role = RoleTag(scene_type="uncertain", scene_type_label="不确定")
        client = StubScreenRecognitionClient(available=False)

        result = enrich_with_hints([scene], client, "2026-04-07")

        self.assertIs(result[0], scene)
        self.assertEqual(client.calls, [])

    def test_enriches_scene_with_client_results(self):
        scene = SceneBlock(time_start="12:00", time_end="12:01", text="test")
        scene.role = RoleTag(scene_type="uncertain", scene_type_label="不确定", evidence_chain=[])
        client = StubScreenRecognitionClient(
            available=True,
            events=[
                ScreenEvent(
                    app_name="Claude",
                    window_name="Chat Window",
                    timestamp="2026-04-07T12:00:00+08:00",
                    frame_id=9,
                )
            ],
        )

        enrich_with_hints([scene], client, "2026-04-07")

        self.assertEqual(scene.role.scene_type, "ai")
        self.assertEqual(client.calls[0]["start_time"], "2026-04-07T12:00:00+08:00")
        self.assertEqual(client.calls[0]["end_time"], "2026-04-07T12:01:59+08:00")


class TestResolveRolesWithScreenpipe(unittest.TestCase):
    @unittest.mock.patch("openmy.services.roles.resolver.infer_role_with_model", return_value=None)
    def test_screenpipe_hint_can_fill_uncertain_role(self, _mock_infer):
        scenes = [SceneBlock(time_start="12:00", time_end="12:01", text="天气不错")]
        client = StubScreenRecognitionClient(
            available=True,
            events=[
                ScreenEvent(
                    app_name="WeChat",
                    window_name="和家人聊天",
                    timestamp="2026-04-07T12:00:05+08:00",
                    frame_id=7,
                )
            ],
        )

        result = resolve_roles(scenes, date_str="2026-04-07", screen_client=client)

        self.assertEqual(result[0].role.scene_type, "interpersonal")
        self.assertEqual(result[0].role.source, "screen_hint")


if __name__ == "__main__":
    unittest.main()
