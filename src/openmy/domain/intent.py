from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
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
    valid_from: str = ""
    valid_until: str = ""
    current_state: str = "active"
    provenance_refs: list[dict[str, Any]] = field(default_factory=list)
    temporal_state: str = ""
    temporal_basis: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "Intent":
        payload = payload if isinstance(payload, dict) else {}
        temporal_state = str(payload.get("temporal_state", "") or "").strip().lower()
        raw_current_state = str(payload.get("current_state", "") or "").strip().lower()
        if not raw_current_state and temporal_state:
            if temporal_state == "ongoing":
                raw_current_state = "active"
            elif temporal_state == "done":
                raw_current_state = "closed"
            elif temporal_state in {"past", "future", "active", "closed", "stale"}:
                raw_current_state = temporal_state
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
            valid_from=str(payload.get("valid_from", "") or ""),
            valid_until=str(payload.get("valid_until", "") or ""),
            current_state=raw_current_state or "active",
            provenance_refs=list(payload.get("provenance_refs", []) or []),
            temporal_state=temporal_state,
            temporal_basis=[
                str(item).strip()
                for item in payload.get("temporal_basis", [])
                if str(item).strip()
            ] if isinstance(payload.get("temporal_basis", []), list) else [],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["who"] = self.who.to_dict()
        data["due"] = self.due.to_dict()
        return data


@dataclass
class Fact:
    fact_id: str = ""
    fact_type: str = ""
    content: str = ""
    topic: str = ""
    confidence_label: str = "medium"
    confidence_score: float = 0.0
    source_scene_id: str = ""
    source_recording_id: str = ""
    evidence_quote: str = ""
    valid_from: str = ""
    valid_until: str = ""
    current_state: str = "active"
    provenance_refs: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "Fact":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            fact_id=str(payload.get("fact_id", "") or ""),
            fact_type=str(payload.get("fact_type", "") or ""),
            content=str(payload.get("content", "") or ""),
            topic=str(payload.get("topic", "") or ""),
            confidence_label=str(payload.get("confidence_label", "medium") or "medium"),
            confidence_score=float(payload.get("confidence_score", 0.0) or 0.0),
            source_scene_id=str(payload.get("source_scene_id", "") or ""),
            source_recording_id=str(payload.get("source_recording_id", "") or ""),
            evidence_quote=str(payload.get("evidence_quote", "") or ""),
            valid_from=str(payload.get("valid_from", "") or ""),
            valid_until=str(payload.get("valid_until", "") or ""),
            current_state=str(payload.get("current_state", "active") or "active"),
            provenance_refs=list(payload.get("provenance_refs", []) or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Event:
    event_id: str = ""
    time: str = ""
    project: str = ""
    summary: str = ""
    confidence_score: float = 0.0
    source_scene_id: str = ""
    source_recording_id: str = ""
    valid_from: str = ""
    valid_until: str = ""
    current_state: str = "past"
    provenance_refs: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "Event":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            event_id=str(payload.get("event_id", "") or ""),
            time=str(payload.get("time", "") or ""),
            project=str(payload.get("project", "") or ""),
            summary=str(payload.get("summary", "") or ""),
            confidence_score=float(payload.get("confidence_score", 0.0) or 0.0),
            source_scene_id=str(payload.get("source_scene_id", "") or ""),
            source_recording_id=str(payload.get("source_recording_id", "") or ""),
            valid_from=str(payload.get("valid_from", "") or ""),
            valid_until=str(payload.get("valid_until", "") or ""),
            current_state=str(payload.get("current_state", "past") or "past"),
            provenance_refs=list(payload.get("provenance_refs", []) or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def should_generate_open_loop(intent: Intent) -> bool:
    """只有真正带未来约束力的 intent 才会长成 open loop。"""
    temporal_state = str(intent.temporal_state or "").strip().lower()
    current_state = str(intent.current_state or "").strip().lower()
    if not intent.what.strip():
        return False
    if intent.kind == "decision":
        return False
    if intent.status in DONE_STATUSES:
        return False
    if temporal_state == "past" or current_state == "past":
        return False
    if current_state in {"closed", "done"}:
        return False
    if temporal_state == "unclear" and not intent.due.raw_text.strip():
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


def build_canonical_key(kind: str, text: str, topic: str = "") -> str:
    seed = f"{topic} {text}".strip()
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", seed.lower())
    return f"{kind}:{normalized}" if normalized else f"{kind}:unknown"


def adjudicate_temporal_state(
    *,
    status: str = "",
    current_state: str = "",
    valid_from: str = "",
    valid_until: str = "",
    due_iso_date: str = "",
    reference_date: str = "",
) -> dict[str, str]:
    normalized_status = str(status or "").strip().lower()
    normalized_state = str(current_state or "").strip().lower()
    if normalized_status in DONE_STATUSES or valid_until:
        return {"state": "closed", "reason": "status_or_valid_until"}
    if normalized_state in {"past", "future", "active", "closed", "stale", "done"}:
        return {"state": normalized_state, "reason": "explicit_current_state"}
    if due_iso_date and reference_date and due_iso_date > reference_date:
        return {"state": "future", "reason": "due_after_reference_date"}
    if valid_from and reference_date and valid_from[:10] > reference_date:
        return {"state": "future", "reason": "valid_from_after_reference_date"}
    return {"state": "active", "reason": "default_active"}
