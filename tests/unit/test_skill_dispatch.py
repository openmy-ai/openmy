#!/usr/bin/env python3
import argparse
import unittest
from unittest.mock import patch


class TestSkillDispatch(unittest.TestCase):
    def make_args(self, **overrides):
        base = {
            "action": "status.get",
            "date": None,
            "audio": None,
            "skip_transcribe": False,
            "correct_args": None,
            "op": None,
            "arg": None,
            "status": "done",
            "level": 1,
            "compact": False,
            "json": True,
        }
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_registry_contains_exact_required_actions(self):
        from openmy import skill_dispatch

        self.assertEqual(
            set(skill_dispatch.ACTION_HANDLERS.keys()),
            {"context.get", "context.query", "day.get", "day.run", "correction.apply", "status.get"},
        )

    def test_dispatch_unknown_action_returns_contract_error(self):
        from openmy import skill_dispatch

        payload, exit_code = skill_dispatch.dispatch_skill_action("unknown.action", self.make_args(action="unknown.action"))
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["action"], "unknown.action")
        self.assertEqual(payload["error_code"], "unknown_action")
        self.assertEqual(payload["version"], "v1")

    def test_correction_apply_normalizes_op_and_arg_flags(self):
        from openmy import skill_dispatch

        self.assertEqual(
            skill_dispatch.build_correction_tokens(self.make_args(op="close-loop", arg=["README"], correct_args=None)),
            ["close-loop", "README"],
        )

    def test_dispatch_routes_through_handler_table(self):
        from openmy import skill_dispatch

        fake_payload = skill_dispatch.build_success_payload(
            action="status.get",
            data={"total_days": 1},
            human_summary="共有 1 天数据。",
        )
        with patch.dict(skill_dispatch.ACTION_HANDLERS, {"status.get": lambda _args: (fake_payload, 0)}, clear=False):
            payload, exit_code = skill_dispatch.dispatch_skill_action("status.get", self.make_args())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, fake_payload)

    def test_day_run_bridges_existing_run_command(self):
        from openmy import skill_dispatch

        fake_status = {"status": "completed", "current_step": "briefing"}
        with (
            patch("openmy.skill_dispatch._run_existing_command", return_value=0) as run_mock,
            patch("openmy.skill_dispatch._day_run_status_path") as status_path_mock,
            patch("openmy.skill_dispatch._read_json", return_value=fake_status),
            patch("openmy.services.ingest.audio_pipeline.load_sidecar_transcript", return_value="已有侧车转写"),
        ):
            status_path_mock.return_value.exists.return_value = True
            payload, exit_code = skill_dispatch.dispatch_skill_action(
                "day.run",
                self.make_args(action="day.run", date="2026-04-10", audio=["a.wav"]),
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "day.run")
        run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
