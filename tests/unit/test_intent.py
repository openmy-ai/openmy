#!/usr/bin/env python3
import unittest

from openmy.domain.intent import (
    ActorRef,
    DueDate,
    Intent,
    intent_to_loop_type,
    should_generate_open_loop,
)


class TestIntentModel(unittest.TestCase):
    def make_intent(self, **overrides) -> Intent:
        payload = {
            "intent_id": "intent_001",
            "kind": "action_item",
            "what": "重写 README",
            "status": "open",
            "who": {"kind": "user", "label": "老板"},
            "confidence_label": "high",
            "confidence_score": 0.91,
            "needs_review": False,
            "evidence_quote": "今天把 README 重写一下。",
            "source_scene_id": "scene_001",
            "topic": "OpenMy",
            "speech_act": "self_instruction",
            "due": {"raw_text": "今天", "iso_date": "2026-04-08", "granularity": "day"},
            "project_hint": "OpenMy",
            "source_recording_id": "rec_001",
        }
        payload.update(overrides)
        return Intent.from_dict(payload)

    def test_intent_round_trip(self):
        intent = self.make_intent()

        restored = Intent.from_dict(intent.to_dict())

        self.assertEqual(restored.to_dict(), intent.to_dict())

    def test_should_generate_open_loop_false_for_low_confidence(self):
        intent = self.make_intent(confidence_label="low")

        self.assertFalse(should_generate_open_loop(intent))

    def test_should_generate_open_loop_false_for_decision(self):
        intent = self.make_intent(kind="decision")

        self.assertFalse(should_generate_open_loop(intent))

    def test_should_generate_open_loop_false_for_done_status(self):
        intent = self.make_intent(status="done")

        self.assertFalse(should_generate_open_loop(intent))

    def test_should_generate_open_loop_false_for_past_temporal_state(self):
        intent = self.make_intent(temporal_state="past")

        self.assertFalse(should_generate_open_loop(intent))

    def test_should_generate_open_loop_false_for_unclear_without_due(self):
        intent = self.make_intent(temporal_state="unclear", due={"raw_text": "", "iso_date": "", "granularity": "none"})

        self.assertFalse(should_generate_open_loop(intent))

    def test_should_generate_open_loop_true_for_future_action(self):
        intent = self.make_intent(temporal_state="future")

        self.assertTrue(should_generate_open_loop(intent))

    def test_intent_to_loop_type_all_branches(self):
        self.assertEqual(intent_to_loop_type(self.make_intent(kind="commitment")), "promise")
        self.assertEqual(intent_to_loop_type(self.make_intent(kind="open_question")), "question")
        self.assertEqual(
            intent_to_loop_type(self.make_intent(who={"kind": "agent", "label": "Claude"})),
            "delegated",
        )
        self.assertEqual(
            intent_to_loop_type(self.make_intent(who={"kind": "other_person", "label": "燕子"})),
            "waiting_on",
        )
        self.assertEqual(
            intent_to_loop_type(self.make_intent(who={"kind": "shared", "label": "我们"})),
            "shared",
        )
        self.assertEqual(intent_to_loop_type(self.make_intent(who={"kind": "user", "label": "老板"})), "actionable")


class TestIntentNestedModels(unittest.TestCase):
    def test_actor_ref_and_due_date_defaults(self):
        actor = ActorRef(kind="unclear")
        due = DueDate()

        self.assertEqual(actor.entity_id, None)
        self.assertEqual(due.granularity, "none")


if __name__ == "__main__":
    unittest.main()
