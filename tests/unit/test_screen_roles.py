#!/usr/bin/env python3
import unittest

from openmy.domain.models import RoleTag, SceneBlock, ScreenContext
from openmy.services.roles.resolver import apply_screen_context_role_adjustments


class TestScreenRoles(unittest.TestCase):
    def make_scene(self, text: str, *, role_type: str = "uncertain", confidence: float = 0.0):
        scene = SceneBlock(scene_id="scene_001", time_start="10:00", time_end="10:05", text=text)
        scene.role = RoleTag(
            category=role_type,
            scene_type=role_type,
            scene_type_label="不确定" if role_type == "uncertain" else role_type,
            confidence=confidence,
            evidence_chain=[],
            needs_review=role_type == "uncertain",
        )
        return scene

    def test_dev_tools_push_ambiguous_self_talk_toward_self_context(self):
        scene = self.make_scene("这个我待会儿弄")
        scene.screen_context = ScreenContext(
            enabled=True,
            aligned=True,
            primary_app="Cursor",
            primary_domain="github.com",
            tags=["development"],
            summary="当时正在 Cursor 修改 OpenMy 的 provider",
        )

        apply_screen_context_role_adjustments(scene)

        self.assertEqual(scene.role.scene_type, "self")
        self.assertIn("开发语境", " ".join(scene.role.evidence_chain))

    def test_wechat_context_pushes_ambiguous_chat_to_interpersonal(self):
        scene = self.make_scene("我刚聊完，回头再看")
        scene.screen_context = ScreenContext(
            enabled=True,
            aligned=True,
            primary_app="微信",
            tags=["communication"],
            summary="当时在微信和人对接需求",
        )

        apply_screen_context_role_adjustments(scene)

        self.assertEqual(scene.role.scene_type, "interpersonal")

    def test_merchant_context_marks_conflict_instead_of_hard_overwrite(self):
        scene = self.make_scene("我刚聊完", role_type="interpersonal", confidence=0.7)
        scene.screen_context = ScreenContext(
            enabled=True,
            aligned=True,
            primary_app="支付宝",
            tags=["payment", "merchant"],
            evidence_conflict=False,
            summary="当时在支付宝订单页处理付款",
        )

        apply_screen_context_role_adjustments(scene)

        self.assertTrue(scene.role.needs_review)
        self.assertTrue(scene.screen_context.evidence_conflict)


if __name__ == "__main__":
    unittest.main()
