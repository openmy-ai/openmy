from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


DONE_STATUSES = {"done", "closed", "cancelled", "abandoned", "rejected"}


@dataclass
class ActorRef:
    kind: str = "unclear"
    label: str = ""
    entity_id: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ActorRef":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            kind=str(payload.get("kind", "unclear") or "unclear"),
            label=str(payload.get("label", "") or ""),
            entity_id=payload.get("entity_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DueDate:
    raw_text: str = ""
    iso_date: str = ""
    granularity: str = "none"

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "DueDate":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            raw_text=str(payload.get("raw_text", "") or ""),
            iso_date=str(payload.get("iso_date", "") or ""),
            granularity=str(payload.get("granularity", "none") or "none"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Intent:
    intent_id: str = ""
    kind: str = ""
    what: str = ""
    status: str = "open"
    who: ActorRef = field(default_factory=ActorRef)
    confidence_label: str = "medium"
    confidence_score: float = 0.0
    needs_review: bool = False
    evidence_quote: str = ""
    source_scene_id: str = ""
    topic: str = ""
    speech_act: str = ""
    due: DueDate = field(default_factory=DueDate)
    project_hint: str = ""
    source_recording_id: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "Intent":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            intent_id=str(payload.get("intent_id", "") or ""),
            kind=str(payload.get("kind", "") or ""),
            what=str(payload.get("what", "") or ""),
            status=str(payload.get("status", "open") or "open"),
            who=ActorRef.from_dict(payload.get("who")),
            confidence_label=str(payload.get("confidence_label", "medium") or "medium"),
            confidence_score=float(payload.get("confidence_score", 0.0) or 0.0),
            needs_review=bool(payload.get("needs_review", False)),
            evidence_quote=str(payload.get("evidence_quote", "") or ""),
            source_scene_id=str(payload.get("source_scene_id", "") or ""),
            topic=str(payload.get("topic", "") or ""),
            speech_act=str(payload.get("speech_act", "") or ""),
            due=DueDate.from_dict(payload.get("due")),
            project_hint=str(payload.get("project_hint", "") or ""),
            source_recording_id=str(payload.get("source_recording_id", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["who"] = self.who.to_dict()
        data["due"] = self.due.to_dict()
        return data


@dataclass
class Fact:
    fact_type: str = ""
    content: str = ""
    topic: str = ""
    confidence_label: str = "medium"
    confidence_score: float = 0.0
    source_scene_id: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "Fact":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            fact_type=str(payload.get("fact_type", "") or ""),
            content=str(payload.get("content", "") or ""),
            topic=str(payload.get("topic", "") or ""),
            confidence_label=str(payload.get("confidence_label", "medium") or "medium"),
            confidence_score=float(payload.get("confidence_score", 0.0) or 0.0),
            source_scene_id=str(payload.get("source_scene_id", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def should_generate_open_loop(intent: Intent) -> bool:
    """只有真正带未来约束力的 intent 才会长成 open loop。"""
    if not intent.what.strip():
        return False
    if intent.kind == "decision":
        return False
    if intent.status in DONE_STATUSES:
        return False
    if intent.confidence_label == "low":
        return False
    if intent.confidence_score and intent.confidence_score < 0.5:
        return False
    return intent.kind in {"action_item", "commitment", "open_question"}


def intent_to_loop_type(intent: Intent) -> str:
    """执行者是一个对象，loop_type 由 kind 和 who.kind 共同决定。"""
    if intent.kind == "commitment":
        return "promise"
    if intent.kind == "open_question":
        return "question"
    if intent.who.kind == "agent":
        return "delegated"
    if intent.who.kind == "other_person":
        return "waiting_on"
    if intent.who.kind == "shared":
        return "shared"
    return "actionable"
