#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from daytape.services.context.active_context import (
    ActiveContext,
    ChangeItem,
    CommunicationContract,
    ConstraintItem,
    EntityRegistryCard,
    EntityRollup,
    Identity,
    IngestionHealth,
    OpenLoop,
    PreferenceItem,
    ProjectCard,
    QualityMetrics,
    RealtimeContext,
    RollingContext,
    SceneRefDigest,
    StableProfile,
    TodayState,
)


class TestActiveContextModel(unittest.TestCase):
    def make_context(self) -> ActiveContext:
        return ActiveContext(
            generated_at="2026-04-08T23:58:10+08:00",
            context_seq=42,
            materialized_from_event_seq=42,
            status_line="最近主要推进 OpenMy 第四层，总共有 2 个待办没闭环。",
            stable_profile=StableProfile(
                identity=Identity(
                    canonical_name="周瑟夫",
                    preferred_name="周瑟夫",
                    roles=["solo_founder", "builder"],
                ),
                communication_contract=CommunicationContract(
                    avoid=["long_bullet_lists"],
                    prefer=["short_paragraphs"],
                ),
                enduring_preferences=[
                    PreferenceItem(
                        id="pref_output_compact",
                        key="output_compactness",
                        value="high",
                        domain="communication",
                        confidence=0.98,
                        source_rank="human_confirmed",
                    )
                ],
                durable_constraints=[
                    ConstraintItem(
                        id="constraint_local_first",
                        key="privacy_architecture",
                        value="local_first",
                        domain="product",
                        hard=True,
                        confidence=0.92,
                        source_rank="declared",
                    )
                ],
                key_people_registry=[
                    EntityRegistryCard(
                        id="entity_partner",
                        entity_id="ent_partner",
                        display_name="伴侣",
                        relation_type="partner",
                        aliases=["老婆", "宝贝"],
                        confidence=0.97,
                        source_rank="human_confirmed",
                    )
                ],
            ),
            rolling_context=RollingContext(
                recent_changes=[
                    ChangeItem(
                        change_id="chg_001",
                        changed_at="2026-04-08T22:10:00+08:00",
                        change_type="new_decision",
                        summary="决定先做 CLI 再做前端。",
                        affected_ids=["decision_001"],
                        salience=0.88,
                    )
                ],
                active_projects=[
                    ProjectCard(
                        id="proj_daytape",
                        project_id="proj_daytape",
                        title="OpenMy",
                        current_goal="做出第一版 active context",
                        next_actions=["补 consolidation", "接 CLI"],
                        confidence=0.95,
                        source_rank="aggregate",
                    )
                ],
                open_loops=[
                    OpenLoop(
                        id="loop_readme",
                        loop_id="loop_readme",
                        title="README 重写",
                        loop_type="deliverable",
                        close_condition="README 提交到仓库",
                        confidence=0.89,
                        source_rank="declared",
                    )
                ],
                entity_rollups=[
                    EntityRollup(
                        entity_id="ent_partner",
                        interaction_7d_count=5,
                        interaction_30d_count=12,
                        last_interaction_at="2026-04-08T19:40:00+08:00",
                        recent_topics=["晚饭", "项目近况"],
                    )
                ],
            ),
            realtime_context=RealtimeContext(
                today_focus=["active_context 设计", "CLI 路线定稿"],
                today_state=TodayState(
                    primary_mode="design",
                    dominant_topics=["Agent memory", "开源定位"],
                    suggested_agent_posture="先给结论，再展开。",
                    confidence=0.76,
                ),
                latest_scene_refs=[
                    SceneRefDigest(
                        scene_id="scene_081",
                        time_range="22:48-23:12",
                        summary="讨论 active_context 和 correction。",
                    )
                ],
                pending_followups_today=["定稿 schema"],
                ingestion_health=IngestionHealth(
                    last_processed_date="2026-04-08",
                    unresolved_scene_ratio_1d=0.11,
                    last_human_review_at="2026-04-08T23:40:00+08:00",
                ),
            ),
            quality=QualityMetrics(
                coverage_days_30d=21,
                scene_count_7d=84,
                human_confirmed_items_30d=12,
                uncertain_ratio_7d=0.18,
                stale_fields=["stable_profile.routine_signals[0]"],
                last_human_review_at="2026-04-08T23:40:00+08:00",
            ),
        )

    def test_to_json_and_from_dict_round_trip(self):
        context = self.make_context()

        restored = ActiveContext.from_dict(context.to_dict())

        self.assertEqual(restored.to_dict(), context.to_dict())

    def test_save_and_load_round_trip(self):
        context = self.make_context()

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "active_context.json"
            context.save(path)

            restored = ActiveContext.load(path)

        self.assertEqual(restored.to_dict(), context.to_dict())

    def test_from_dict_ignores_unknown_fields(self):
        context = self.make_context().to_dict()
        context["unknown_top_level"] = "ignored"
        context["stable_profile"]["identity"]["unknown_nested"] = "ignored"

        restored = ActiveContext.from_dict(context)

        self.assertEqual(restored.stable_profile.identity.canonical_name, "周瑟夫")
        self.assertFalse(hasattr(restored, "unknown_top_level"))


if __name__ == "__main__":
    unittest.main()
