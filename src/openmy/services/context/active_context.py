"""Active Context 数据模型 — 三层快照 schema.

schema_version: active_context.v1

三层架构：
  - stable_profile：身份、沟通契约、持久偏好、关键人物
  - rolling_context：近期变化、活跃项目、open loops、决策、观点转向
  - realtime_context：今日焦点、当日状态、最新场景引用
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "active_context.v1"

# ---------------------------------------------------------------------------
# source_rank 优先级（数字越大越权威）
# ---------------------------------------------------------------------------
SOURCE_RANKS = {
    "aggregate": 100,
    "model_inferred": 200,
    "rule_inferred": 300,
    "declared": 400,
    "imported_trusted": 500,
    "human_confirmed": 600,
}


def _load_dataclass(dataclass_type, payload: dict[str, Any] | None):
    """只读取 dataclass 已知字段，忽略多余键。"""
    if not isinstance(payload, dict):
        payload = {}
    allowed = {item.name for item in fields(dataclass_type)}
    filtered = {key: value for key, value in payload.items() if key in allowed}
    return dataclass_type(**filtered)


# ---------------------------------------------------------------------------
# 公共基类字段（所有可晋升条目共享）
# ---------------------------------------------------------------------------
@dataclass
class ItemBase:
    """所有可晋升条目的公共基类."""

    id: str = ""
    confidence: float = 0.0
    source_rank: str = "model_inferred"
    first_seen_at: str = ""
    last_seen_at: str = ""
    last_confirmed_at: str = ""
    reinforcement_count: int = 0
    stale: bool = False
    provenance_refs: list[dict[str, str]] = field(default_factory=list)
    valid_from: str = ""
    valid_until: str = ""
    current_state: str = ""
    state_reason: str = ""


# ---------------------------------------------------------------------------
# 稳定层：stable_profile
# ---------------------------------------------------------------------------
@dataclass
class Identity:
    canonical_name: str = ""
    preferred_name: str = ""
    primary_language: str = "zh-CN"
    timezone: str = "Asia/Shanghai"
    roles: list[str] = field(default_factory=list)


@dataclass
class CommunicationContract:
    answer_language: str = "zh-CN"
    answer_style: str = "direct_compact"
    tone: str = "plain"
    avoid: list[str] = field(default_factory=list)
    prefer: list[str] = field(default_factory=list)


@dataclass
class PreferenceItem(ItemBase):
    key: str = ""
    value: str = ""
    domain: str = ""
    volatility: str = "stable"


@dataclass
class ConstraintItem(ItemBase):
    key: str = ""
    value: str = ""
    domain: str = ""
    hard: bool = False


@dataclass
class RoutineItem(ItemBase):
    pattern: str = ""
    window: str = ""
    days_observed: int = 0
    weekday_bias: list[str] = field(default_factory=list)


@dataclass
class EntityRegistryCard(ItemBase):
    entity_id: str = ""
    display_name: str = ""
    canonical_name: str = ""
    relation_type: str = ""
    aliases: list[str] = field(default_factory=list)
    default_address_style: str = ""


@dataclass
class StableProfile:
    identity: Identity = field(default_factory=Identity)
    communication_contract: CommunicationContract = field(
        default_factory=CommunicationContract
    )
    enduring_preferences: list[PreferenceItem] = field(default_factory=list)
    durable_constraints: list[ConstraintItem] = field(default_factory=list)
    routine_signals: list[RoutineItem] = field(default_factory=list)
    key_people_registry: list[EntityRegistryCard] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 核心层：core_memory
# ---------------------------------------------------------------------------
@dataclass
class CoreMemory:
    focus_projects: list["ProjectCard"] = field(default_factory=list)
    open_loops: list["OpenLoop"] = field(default_factory=list)
    active_decisions: list["DecisionItem"] = field(default_factory=list)
    key_people: list[EntityRegistryCard] = field(default_factory=list)
    current_focus: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 滚动层：rolling_context
# ---------------------------------------------------------------------------
@dataclass
class ChangeItem:
    change_id: str = ""
    changed_at: str = ""
    change_type: str = ""
    summary: str = ""
    affected_ids: list[str] = field(default_factory=list)
    salience: float = 0.0


@dataclass
class ProjectCard(ItemBase):
    project_id: str = ""
    title: str = ""
    status: str = "active"
    priority: str = "medium"
    current_goal: str = ""
    next_actions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    momentum: str = "steady"
    last_touched_at: str = ""


@dataclass
class OpenLoop(ItemBase):
    loop_id: str = ""
    title: str = ""
    loop_type: str = ""
    status: str = "open"
    owner: str = "self"
    due_hint: str = ""
    priority: str = "medium"
    waiting_on: str = ""
    close_condition: str = ""


@dataclass
class DecisionItem(ItemBase):
    decision_id: str = ""
    topic: str = ""
    decision: str = ""
    scope: str = "project"
    effective_from: str = ""
    supersedes: list[str] = field(default_factory=list)


@dataclass
class BeliefShift(ItemBase):
    shift_id: str = ""
    topic: str = ""
    old_value: str = ""
    new_value: str = ""
    shift_reason: str = ""
    effective_from: str = ""


@dataclass
class EntityRollup:
    entity_id: str = ""
    interaction_7d_count: int = 0
    interaction_30d_count: int = 0
    last_interaction_at: str = ""
    recent_topics: list[str] = field(default_factory=list)


@dataclass
class TopicRollup:
    topic: str = ""
    mentions_7d: int = 0
    mentions_30d: int = 0
    last_seen_at: str = ""


@dataclass
class EventItem(ItemBase):
    event_id: str = ""
    project: str = ""
    summary: str = ""
    happened_at: str = ""
    time_label: str = ""


@dataclass
class ConflictItem(ItemBase):
    conflict_id: str = ""
    canonical_key: str = ""
    title: str = ""
    conflict_type: str = ""
    variants: list[str] = field(default_factory=list)


@dataclass
class RollingContext:
    recent_changes: list[ChangeItem] = field(default_factory=list)
    active_projects: list[ProjectCard] = field(default_factory=list)
    open_loops: list[OpenLoop] = field(default_factory=list)
    recent_decisions: list[DecisionItem] = field(default_factory=list)
    recent_events: list[EventItem] = field(default_factory=list)
    recent_conflicts: list[ConflictItem] = field(default_factory=list)
    belief_shifts: list[BeliefShift] = field(default_factory=list)
    entity_rollups: list[EntityRollup] = field(default_factory=list)
    topic_rollups: list[TopicRollup] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 实时层：realtime_context
# ---------------------------------------------------------------------------
@dataclass
class TodayState:
    primary_mode: str = ""
    energy: str = "medium"
    time_pressure: str = "medium"
    interaction_load: str = "medium"
    dominant_topics: list[str] = field(default_factory=list)
    suggested_agent_posture: str = ""
    confidence: float = 0.0


@dataclass
class SceneRefDigest:
    scene_id: str = ""
    time_range: str = ""
    summary: str = ""


@dataclass
class IngestionHealth:
    last_processed_date: str = ""
    unresolved_scene_ratio_1d: float = 0.0
    last_human_review_at: str = ""


@dataclass
class CompletionCandidateDigest:
    scene_id: str = ""
    kind: str = ""
    label: str = ""
    confidence: float = 0.0
    evidence: str = ""


@dataclass
class RealtimeContext:
    today_focus: list[str] = field(default_factory=list)
    today_state: TodayState = field(default_factory=TodayState)
    latest_scene_refs: list[SceneRefDigest] = field(default_factory=list)
    pending_followups_today: list[str] = field(default_factory=list)
    screen_completion_candidates: list[CompletionCandidateDigest] = field(default_factory=list)
    ingestion_health: IngestionHealth = field(default_factory=IngestionHealth)


# ---------------------------------------------------------------------------
# 质量指标
# ---------------------------------------------------------------------------
@dataclass
class QualityMetrics:
    coverage_days_30d: int = 0
    scene_count_7d: int = 0
    human_confirmed_items_30d: int = 0
    uncertain_ratio_7d: float = 0.0
    stale_fields: list[str] = field(default_factory=list)
    last_human_review_at: str = ""


# ---------------------------------------------------------------------------
# 顶层：ActiveContext
# ---------------------------------------------------------------------------
@dataclass
class ActiveContext:
    """完整的 active_context 快照."""

    schema_version: str = SCHEMA_VERSION
    user_id: str = "user_zhousefu"
    generated_at: str = ""
    context_seq: int = 0
    materialized_from_event_seq: int = 0
    default_delta_window_days: int = 3
    status_line: str = ""

    stable_profile: StableProfile = field(default_factory=StableProfile)
    core_memory: CoreMemory = field(default_factory=CoreMemory)
    rolling_context: RollingContext = field(default_factory=RollingContext)
    realtime_context: RealtimeContext = field(default_factory=RealtimeContext)
    quality: QualityMetrics = field(default_factory=QualityMetrics)

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 保存的 dict."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: Path) -> None:
        """保存到文件."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ActiveContext":
        """从 JSON 文件加载."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActiveContext":
        """从 dict 反序列化。只解析已知字段，忽略未知。"""
        ctx = cls()
        ctx.schema_version = data.get("schema_version", SCHEMA_VERSION)
        ctx.user_id = data.get("user_id", "user_zhousefu")
        ctx.generated_at = data.get("generated_at", "")
        ctx.context_seq = data.get("context_seq", 0)
        ctx.materialized_from_event_seq = data.get(
            "materialized_from_event_seq", 0
        )
        ctx.default_delta_window_days = data.get(
            "default_delta_window_days", 3
        )
        ctx.status_line = data.get("status_line", "")

        # stable_profile
        sp = data.get("stable_profile", {})
        ctx.stable_profile = StableProfile(
            identity=_load_dataclass(Identity, sp.get("identity", {})),
            communication_contract=_load_dataclass(
                CommunicationContract, sp.get("communication_contract", {})
            ),
            enduring_preferences=[
                _load_dataclass(PreferenceItem, p)
                for p in sp.get("enduring_preferences", [])
            ],
            durable_constraints=[
                _load_dataclass(ConstraintItem, c)
                for c in sp.get("durable_constraints", [])
            ],
            routine_signals=[
                _load_dataclass(RoutineItem, r)
                for r in sp.get("routine_signals", [])
            ],
            key_people_registry=[
                _load_dataclass(EntityRegistryCard, e)
                for e in sp.get("key_people_registry", [])
            ],
        )

        cm = data.get("core_memory", {})
        ctx.core_memory = CoreMemory(
            focus_projects=[
                _load_dataclass(ProjectCard, p)
                for p in cm.get("focus_projects", [])
            ],
            open_loops=[
                _load_dataclass(OpenLoop, o)
                for o in cm.get("open_loops", [])
            ],
            active_decisions=[
                _load_dataclass(DecisionItem, d)
                for d in cm.get("active_decisions", [])
            ],
            key_people=[
                _load_dataclass(EntityRegistryCard, e)
                for e in cm.get("key_people", [])
            ],
            current_focus=cm.get("current_focus", []),
        )

        # rolling_context
        rc = data.get("rolling_context", {})
        ctx.rolling_context = RollingContext(
            recent_changes=[
                _load_dataclass(ChangeItem, c)
                for c in rc.get("recent_changes", [])
            ],
            active_projects=[
                _load_dataclass(ProjectCard, p)
                for p in rc.get("active_projects", [])
            ],
            open_loops=[
                _load_dataclass(OpenLoop, o)
                for o in rc.get("open_loops", [])
            ],
            recent_decisions=[
                _load_dataclass(DecisionItem, d)
                for d in rc.get("recent_decisions", [])
            ],
            recent_events=[
                _load_dataclass(EventItem, e)
                for e in rc.get("recent_events", [])
            ],
            recent_conflicts=[
                _load_dataclass(ConflictItem, c)
                for c in rc.get("recent_conflicts", [])
            ],
            belief_shifts=[
                _load_dataclass(BeliefShift, b)
                for b in rc.get("belief_shifts", [])
            ],
            entity_rollups=[
                _load_dataclass(EntityRollup, e)
                for e in rc.get("entity_rollups", [])
            ],
            topic_rollups=[
                _load_dataclass(TopicRollup, t)
                for t in rc.get("topic_rollups", [])
            ],
        )

        # realtime_context
        rt = data.get("realtime_context", {})
        ctx.realtime_context = RealtimeContext(
            today_focus=rt.get("today_focus", []),
            today_state=_load_dataclass(TodayState, rt.get("today_state", {})),
            latest_scene_refs=[
                _load_dataclass(SceneRefDigest, s)
                for s in rt.get("latest_scene_refs", [])
            ],
            pending_followups_today=rt.get("pending_followups_today", []),
            screen_completion_candidates=[
                _load_dataclass(CompletionCandidateDigest, item)
                for item in rt.get("screen_completion_candidates", [])
            ],
            ingestion_health=_load_dataclass(
                IngestionHealth, rt.get("ingestion_health", {})
            ),
        )

        # quality
        q = data.get("quality", {})
        ctx.quality = _load_dataclass(QualityMetrics, q)

        return ctx
