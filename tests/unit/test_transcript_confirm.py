#!/usr/bin/env python3
"""Tests for transcript.confirm.pending / transcript.confirm.submit (U6)."""
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _make_scene(
    scene_id: str,
    text: str,
    summary: str = "有内容",
    time_start: str = "10:00",
    usable: bool = True,
) -> dict:
    """Build a minimal scene dict for testing."""
    scene = {
        "scene_id": scene_id,
        "text": text,
        "summary": summary,
        "time_start": time_start,
    }
    if not usable:
        # scene_quality marks unusable scenes by low_quality flags
        scene["text"] = "[无法识别]" * 20  # triggers garbled ratio
    return scene


def _make_args(**overrides) -> argparse.Namespace:
    base = {
        "action": "transcript.confirm.pending",
        "date": None,
        "payload_json": None,
        "payload_file": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


class PendingFilteringTest(unittest.TestCase):
    """pending handler: only returns items from usable+summarized scenes."""

    def test_filters_unusable_and_unsummarized_scenes(self):
        """8 uncertain items across scenes, only usable+summarized ones return, cap 5."""
        from openmy.skill_handlers.transcript_confirm import handle_confirm_pending
        from openmy.skill_handlers.common import build_success_payload

        scenes = {
            "scenes": [
                # Scene 0: usable + summary — has 3 uncertain items
                {
                    "scene_id": "s00",
                    "text": "我：去[?宿州]看[?GL8]的车\n人：[?张韧]也想去",
                    "summary": "看车",
                    "time_start": "09:00",
                },
                # Scene 1: usable but NO summary — should be excluded
                {
                    "scene_id": "s01",
                    "text": "我：[?额外]的内容",
                    "summary": "",
                    "time_start": "09:30",
                },
                # Scene 2: unusable (garbled) — should be excluded
                {
                    "scene_id": "s02",
                    "text": "[无法识别]" * 20 + "[?不应出现]",
                    "summary": "垃圾",
                    "time_start": "09:45",
                },
                # Scene 3: usable + summary — has 3 uncertain items
                {
                    "scene_id": "s03",
                    "text": "外：[?播客]讲了[?人工智能]的内容\n我：[?记住了]这段",
                    "summary": "听播客",
                    "time_start": "10:00",
                },
                # Scene 4: usable + summary — has 2 uncertain items
                {
                    "scene_id": "s04",
                    "text": "我：[?小刘]说[?周六]见面",
                    "summary": "约见面",
                    "time_start": "11:00",
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            scenes_path.write_text(json.dumps(scenes, ensure_ascii=False), encoding="utf-8")

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
            )

            payload, exit_code = handle_confirm_pending(
                _make_args(date="2026-06-10"),
                cli_getter=lambda: fake_cli,
                require_date_fn=lambda action, d: d,
                build_success_payload=build_success_payload,
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        items = payload["data"]["items"]
        # s00 has 3, s03 has 3, s04 has 2 = 8 total eligible, cap at 5
        self.assertEqual(len(items), 5)
        # All items should have the required fields
        for item in items:
            self.assertIn("item_id", item)
            self.assertIn("uncertain_text", item)
            self.assertIn("context_line", item)
            self.assertIn("scene_time", item)
        # human_summary present
        self.assertIn("human_summary", payload)
        self.assertIn("5", payload["human_summary"])

    def test_ordering_by_scene_time(self):
        """Items sorted by scene time, first 5 returned."""
        from openmy.skill_handlers.transcript_confirm import handle_confirm_pending
        from openmy.skill_handlers.common import build_success_payload

        scenes = {
            "scenes": [
                {
                    "scene_id": "s_late",
                    "text": "我：[?晚场A]\n我：[?晚场B]\n我：[?晚场C]",
                    "summary": "有",
                    "time_start": "22:00",
                },
                {
                    "scene_id": "s_early",
                    "text": "我：[?早场A]\n我：[?早场B]\n我：[?早场C]",
                    "summary": "有",
                    "time_start": "08:00",
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            scenes_path.write_text(json.dumps(scenes, ensure_ascii=False), encoding="utf-8")

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
            )

            payload, _ = handle_confirm_pending(
                _make_args(date="2026-06-10"),
                cli_getter=lambda: fake_cli,
                require_date_fn=lambda action, d: d,
                build_success_payload=build_success_payload,
            )

        items = payload["data"]["items"]
        self.assertEqual(len(items), 5)
        # First 3 should be early, next 2 from late (sorted by time)
        self.assertTrue(all(it["scene_time"] == "08:00" for it in items[:3]))
        self.assertTrue(all(it["scene_time"] == "22:00" for it in items[3:5]))

    def test_all_scenes_unusable_returns_empty(self):
        """All scenes unusable -> empty list, success envelope intact."""
        from openmy.skill_handlers.transcript_confirm import handle_confirm_pending
        from openmy.skill_handlers.common import build_success_payload

        scenes = {
            "scenes": [
                {
                    "scene_id": "s00",
                    "text": "[无法识别]" * 20 + "[?不应出现]",
                    "summary": "垃圾",
                    "time_start": "10:00",
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            scenes_path.write_text(json.dumps(scenes, ensure_ascii=False), encoding="utf-8")

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
            )

            payload, exit_code = handle_confirm_pending(
                _make_args(date="2026-06-10"),
                cli_getter=lambda: fake_cli,
                require_date_fn=lambda action, d: d,
                build_success_payload=build_success_payload,
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["items"], [])
        self.assertIn("human_summary", payload)


class SubmitCorrectedTest(unittest.TestCase):
    """submit handler: corrected resolution writes dictionaries and cleans markers."""

    def test_corrected_writes_all_targets(self):
        from openmy.skill_handlers.transcript_confirm import handle_confirm_submit
        from openmy.skill_handlers.common import build_success_payload

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            transcript_path = Path(tmp) / "transcript.md"
            corrections_path = Path(tmp) / "corrections.json"
            vocab_path = Path(tmp) / "vocab.txt"

            scenes_data = {
                "scenes": [
                    {
                        "scene_id": "s00",
                        "text": "我：去[?宿州]看车",
                        "summary": "看车",
                        "time_start": "10:00",
                    }
                ]
            }
            scenes_path.write_text(json.dumps(scenes_data, ensure_ascii=False), encoding="utf-8")
            transcript_path.write_text("## 10:00\n\n我：去[?宿州]看车", encoding="utf-8")
            corrections_path.write_text('{"corrections": []}', encoding="utf-8")
            vocab_path.write_text("# vocab\n", encoding="utf-8")

            payload_file = Path(tmp) / "payload.json"
            payload_data = {
                "date": "2026-06-10",
                "items": [
                    {
                        "item_id": "s0_l0_abc",
                        "wrong": "宿州",
                        "right": "苏州",
                        "resolution": "corrected",
                    }
                ],
            }
            payload_file.write_text(json.dumps(payload_data, ensure_ascii=False), encoding="utf-8")

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path, "transcript": transcript_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
            )

            with (
                patch("openmy.commands.correct._upsert_word_correction") as mock_upsert,
                patch("openmy.services.cleaning.cleaner.sync_correction_to_vocab") as mock_vocab,
                patch("openmy.utils.io.safe_write_json", side_effect=lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")),
            ):
                mock_upsert.side_effect = lambda w, r: None
                mock_vocab.side_effect = lambda w, r: None

                payload, exit_code = handle_confirm_submit(
                    _make_args(date="2026-06-10", payload_file=str(payload_file)),
                    cli_getter=lambda: fake_cli,
                    require_date_fn=lambda action, d: d,
                    build_success_payload=build_success_payload,
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["stats"]["corrected"], 1)
            mock_upsert.assert_called_once_with("宿州", "苏州")
            mock_vocab.assert_called_once_with("宿州", "苏州")

            # Transcript: marker removed, word replaced
            transcript_text = transcript_path.read_text(encoding="utf-8")
            self.assertIn("苏州", transcript_text)
            self.assertNotIn("[?宿州]", transcript_text)
            self.assertNotIn("[?苏州]", transcript_text)

            # Scenes.json: same replacement
            scenes_updated = json.loads(scenes_path.read_text(encoding="utf-8"))
            self.assertIn("苏州", scenes_updated["scenes"][0]["text"])
            self.assertNotIn("[?宿州]", scenes_updated["scenes"][0]["text"])

    def test_corrected_item_excluded_from_re_pending(self):
        """After corrected submit, re-running pending does not return the item."""
        from openmy.skill_handlers.transcript_confirm import handle_confirm_pending, handle_confirm_submit
        from openmy.skill_handlers.common import build_success_payload

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            transcript_path = Path(tmp) / "transcript.md"

            scenes_data = {
                "scenes": [
                    {
                        "scene_id": "s00",
                        "text": "我：去[?宿州]看车",
                        "summary": "看车",
                        "time_start": "10:00",
                    }
                ]
            }
            scenes_path.write_text(json.dumps(scenes_data, ensure_ascii=False), encoding="utf-8")
            transcript_path.write_text("我：去[?宿州]看车", encoding="utf-8")

            payload_file = Path(tmp) / "payload.json"
            payload_file.write_text(
                json.dumps({
                    "date": "2026-06-10",
                    "items": [{"item_id": "x", "wrong": "宿州", "right": "苏州", "resolution": "corrected"}],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path, "transcript": transcript_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
            )

            with (
                patch("openmy.commands.correct._upsert_word_correction"),
                patch("openmy.services.cleaning.cleaner.sync_correction_to_vocab"),
                patch("openmy.utils.io.safe_write_json", side_effect=lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")),
            ):
                handle_confirm_submit(
                    _make_args(date="2026-06-10", payload_file=str(payload_file)),
                    cli_getter=lambda: fake_cli,
                    require_date_fn=lambda action, d: d,
                    build_success_payload=build_success_payload,
                )

            # Re-run pending
            pending_payload, _ = handle_confirm_pending(
                _make_args(date="2026-06-10"),
                cli_getter=lambda: fake_cli,
                require_date_fn=lambda action, d: d,
                build_success_payload=build_success_payload,
            )
            self.assertEqual(pending_payload["data"]["items"], [])


class SubmitConfirmedCorrectTest(unittest.TestCase):
    """confirmed_correct: unwrap mark, keep word, no dictionary writes."""

    def test_confirmed_correct_unwraps_only(self):
        from openmy.skill_handlers.transcript_confirm import handle_confirm_submit
        from openmy.skill_handlers.common import build_success_payload

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            transcript_path = Path(tmp) / "transcript.md"

            scenes_data = {
                "scenes": [
                    {
                        "scene_id": "s00",
                        "text": "我：去[?宿州]看车",
                        "summary": "看车",
                        "time_start": "10:00",
                    }
                ]
            }
            scenes_path.write_text(json.dumps(scenes_data, ensure_ascii=False), encoding="utf-8")
            transcript_path.write_text("我：去[?宿州]看车", encoding="utf-8")

            payload_file = Path(tmp) / "payload.json"
            payload_file.write_text(
                json.dumps({
                    "date": "2026-06-10",
                    "items": [{"item_id": "x", "wrong": "宿州", "resolution": "confirmed_correct"}],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path, "transcript": transcript_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
            )

            with (
                patch("openmy.commands.correct._upsert_word_correction") as mock_upsert,
                patch("openmy.services.cleaning.cleaner.sync_correction_to_vocab") as mock_vocab,
                patch("openmy.utils.io.safe_write_json", side_effect=lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")),
            ):
                payload, exit_code = handle_confirm_submit(
                    _make_args(date="2026-06-10", payload_file=str(payload_file)),
                    cli_getter=lambda: fake_cli,
                    require_date_fn=lambda action, d: d,
                    build_success_payload=build_success_payload,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["data"]["stats"]["confirmed_correct"], 1)

            # Dictionary NOT touched
            mock_upsert.assert_not_called()
            mock_vocab.assert_not_called()

            # Transcript: word kept, mark removed
            transcript_text = transcript_path.read_text(encoding="utf-8")
            self.assertIn("宿州", transcript_text)
            self.assertNotIn("[?", transcript_text)


class SubmitUnknownTest(unittest.TestCase):
    """unknown: 词替换为 [无法识别]（宁漏勿假），词典不写。"""

    def test_unknown_replaces_with_unrecognized_no_dictionary(self):
        from openmy.skill_handlers.transcript_confirm import handle_confirm_submit
        from openmy.skill_handlers.common import build_success_payload

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            transcript_path = Path(tmp) / "transcript.md"

            scenes_data = {
                "scenes": [
                    {
                        "scene_id": "s00",
                        "text": "我：去[?宿州]看车",
                        "summary": "看车",
                        "time_start": "10:00",
                    }
                ]
            }
            scenes_path.write_text(json.dumps(scenes_data, ensure_ascii=False), encoding="utf-8")
            transcript_path.write_text("我：去[?宿州]看车", encoding="utf-8")

            payload_file = Path(tmp) / "payload.json"
            payload_file.write_text(
                json.dumps({
                    "date": "2026-06-10",
                    "items": [{"item_id": "x", "wrong": "宿州", "resolution": "unknown"}],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path, "transcript": transcript_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
            )

            with (
                patch("openmy.commands.correct._upsert_word_correction") as mock_upsert,
                patch("openmy.services.cleaning.cleaner.sync_correction_to_vocab") as mock_vocab,
                patch("openmy.utils.io.safe_write_json", side_effect=lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")),
            ):
                payload, exit_code = handle_confirm_submit(
                    _make_args(date="2026-06-10", payload_file=str(payload_file)),
                    cli_getter=lambda: fake_cli,
                    require_date_fn=lambda action, d: d,
                    build_success_payload=build_success_payload,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["data"]["stats"]["unknown"], 1)
            mock_upsert.assert_not_called()
            mock_vocab.assert_not_called()

            # 宁漏勿假：没人敲定的词不能以确定身份留在转写里 → 替换为 [无法识别]
            transcript_text = transcript_path.read_text(encoding="utf-8")
            self.assertNotIn("宿州", transcript_text)
            self.assertIn("[无法识别]", transcript_text)
            self.assertNotIn("[?", transcript_text)


class IdempotencyTest(unittest.TestCase):
    """Same item submitted twice: no duplicate dictionary entry, no error."""

    def test_double_submit_no_error(self):
        from openmy.skill_handlers.transcript_confirm import handle_confirm_submit
        from openmy.skill_handlers.common import build_success_payload

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            transcript_path = Path(tmp) / "transcript.md"

            scenes_data = {
                "scenes": [
                    {
                        "scene_id": "s00",
                        "text": "我：去[?宿州]看车",
                        "summary": "看车",
                        "time_start": "10:00",
                    }
                ]
            }
            scenes_path.write_text(json.dumps(scenes_data, ensure_ascii=False), encoding="utf-8")
            transcript_path.write_text("我：去[?宿州]看车", encoding="utf-8")

            payload_file = Path(tmp) / "payload.json"
            payload_file.write_text(
                json.dumps({
                    "date": "2026-06-10",
                    "items": [{"item_id": "x", "wrong": "宿州", "right": "苏州", "resolution": "corrected"}],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path, "transcript": transcript_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
            )

            upsert_calls = []
            vocab_calls = []

            def track_upsert(w, r):
                upsert_calls.append((w, r))

            def track_vocab(w, r):
                vocab_calls.append((w, r))

            with (
                patch("openmy.commands.correct._upsert_word_correction", side_effect=track_upsert),
                patch("openmy.services.cleaning.cleaner.sync_correction_to_vocab", side_effect=track_vocab),
                patch("openmy.utils.io.safe_write_json", side_effect=lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")),
            ):
                # First submit
                handle_confirm_submit(
                    _make_args(date="2026-06-10", payload_file=str(payload_file)),
                    cli_getter=lambda: fake_cli,
                    require_date_fn=lambda action, d: d,
                    build_success_payload=build_success_payload,
                )

            # After first submit, markers are gone. Re-write the payload for second submit.
            # The second submit should still succeed (marker already replaced = no-op replace).
            payload_file2 = Path(tmp) / "payload2.json"
            payload_file2.write_text(
                json.dumps({
                    "date": "2026-06-10",
                    "items": [{"item_id": "x", "wrong": "宿州", "right": "苏州", "resolution": "corrected"}],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            with (
                patch("openmy.commands.correct._upsert_word_correction", side_effect=track_upsert),
                patch("openmy.services.cleaning.cleaner.sync_correction_to_vocab", side_effect=track_vocab),
                patch("openmy.utils.io.safe_write_json", side_effect=lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")),
            ):
                payload, exit_code = handle_confirm_submit(
                    _make_args(date="2026-06-10", payload_file=str(payload_file2)),
                    cli_getter=lambda: fake_cli,
                    require_date_fn=lambda action, d: d,
                    build_success_payload=build_success_payload,
                )

            # Both submits succeeded
            self.assertEqual(exit_code, 0)
            # _upsert_word_correction has upsert semantics — calling twice is safe
            self.assertEqual(len(upsert_calls), 2)
            # The actual dictionary deduplication is in _upsert_word_correction itself

            # Transcript should be clean (second replace is a no-op)
            transcript_text = transcript_path.read_text(encoding="utf-8")
            self.assertIn("苏州", transcript_text)
            self.assertNotIn("[?", transcript_text)
            # Should NOT have double-replaced to produce artifacts
            self.assertEqual(transcript_text.count("苏州"), 1)


class DispatchRegistrationTest(unittest.TestCase):
    """Both actions registered and reachable through the dispatch table."""

    def test_actions_registered(self):
        from openmy.skill_dispatch import ACTION_HANDLERS

        self.assertIn("transcript.confirm.pending", ACTION_HANDLERS)
        self.assertIn("transcript.confirm.submit", ACTION_HANDLERS)

    def test_pending_reachable_via_dispatch(self):
        from openmy.skill_dispatch import dispatch_skill_action

        with tempfile.TemporaryDirectory() as tmp:
            scenes_path = Path(tmp) / "scenes.json"
            scenes_path.write_text('{"scenes": []}', encoding="utf-8")

            fake_cli = SimpleNamespace(
                resolve_day_paths=lambda d: {"scenes": scenes_path},
                read_json=lambda p, default: json.loads(p.read_text(encoding="utf-8")) if p.exists() else default,
                DATE_RE=__import__("re").compile(r"^\d{4}-\d{2}-\d{2}$"),
            )

            with patch("openmy.skill_dispatch._cli", return_value=fake_cli):
                payload, exit_code = dispatch_skill_action(
                    "transcript.confirm.pending",
                    _make_args(date="2026-06-10"),
                )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "transcript.confirm.pending")


if __name__ == "__main__":
    unittest.main()
