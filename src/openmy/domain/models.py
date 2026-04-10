from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TranscriptSegment:
    time: str
    text: str
    duration: float = 0.0


@dataclass
class RoleDecision:
    category: str = "uncertain"
    entity_id: str = ""
    relation_label: str = ""
    confidence: float = 0.0
    evidence_chain: list[str] = field(default_factory=list)
    scene_type: str = "uncertain"
    scene_type_label: str = "不确定"
    addressed_to: str = ""
    about: str = ""
    source: str = "uncertain"
    source_label: str = "不确定"
    evidence: str = ""
    needs_review: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RoleDecision":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            category=str(payload.get("category", "uncertain") or "uncertain"),
            entity_id=str(payload.get("entity_id", "") or ""),
            relation_label=str(payload.get("relation_label", "") or ""),
            confidence=float(payload.get("confidence", 0.0) or 0.0),
            evidence_chain=[str(item) for item in payload.get("evidence_chain", []) if item is not None],
            scene_type=str(payload.get("scene_type", "uncertain") or "uncertain"),
            scene_type_label=str(payload.get("scene_type_label", "不确定") or "不确定"),
            addressed_to=str(payload.get("addressed_to", "") or ""),
            about=str(payload.get("about", "") or ""),
            source=str(payload.get("source", "uncertain") or "uncertain"),
            source_label=str(payload.get("source_label", "不确定") or "不确定"),
            evidence=str(payload.get("evidence", "") or ""),
            needs_review=bool(payload.get("needs_review", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScreenFrameRef:
    frame_id: int = 0
    timestamp: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ScreenFrameRef":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            frame_id=int(payload.get("frame_id", 0) or 0),
            timestamp=str(payload.get("timestamp", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScreenCompletionCandidate:
    kind: str = ""
    label: str = ""
    confidence: float = 0.0
    evidence: str = ""
    source_session_id: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ScreenCompletionCandidate":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            kind=str(payload.get("kind", "") or ""),
            label=str(payload.get("label", "") or ""),
            confidence=float(payload.get("confidence", 0.0) or 0.0),
            evidence=str(payload.get("evidence", "") or ""),
            source_session_id=str(payload.get("source_session_id", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScreenSession:
    """屏幕会话摘要。"""

    session_id: str = ""
    app_name: str = ""
    window_name: str = ""
    url_domain: str = ""
    start_time: str = ""
    end_time: str = ""
    frame_ids: list[int] = field(default_factory=list)
    frame_refs: list[ScreenFrameRef] = field(default_factory=list)
    text: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    sensitive: bool = False
    summary_only: bool = False
    excluded: bool = False
    privacy_reason: str = ""
    task_signal: str = ""
    completion_candidates: list[ScreenCompletionCandidate] = field(default_factory=list)
    role_hint: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ScreenSession":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            session_id=str(payload.get("session_id", "") or ""),
            app_name=str(payload.get("app_name", "") or ""),
            window_name=str(payload.get("window_name", "") or ""),
            url_domain=str(payload.get("url_domain", "") or ""),
            start_time=str(payload.get("start_time", "") or ""),
            end_time=str(payload.get("end_time", "") or ""),
            frame_ids=[int(item) for item in payload.get("frame_ids", []) if item is not None],
            frame_refs=[ScreenFrameRef.from_dict(item) for item in payload.get("frame_refs", []) if isinstance(item, dict)],
            text=str(payload.get("text", "") or ""),
            summary=str(payload.get("summary", "") or ""),
            tags=[str(item) for item in payload.get("tags", []) if item is not None],
            sensitive=bool(payload.get("sensitive", False)),
            summary_only=bool(payload.get("summary_only", False)),
            excluded=bool(payload.get("excluded", False)),
            privacy_reason=str(payload.get("privacy_reason", "") or ""),
            task_signal=str(payload.get("task_signal", "") or ""),
            completion_candidates=[
                ScreenCompletionCandidate.from_dict(item)
                for item in payload.get("completion_candidates", [])
                if isinstance(item, dict)
            ],
            role_hint=str(payload.get("role_hint", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["frame_refs"] = [item.to_dict() for item in self.frame_refs]
        data["completion_candidates"] = [item.to_dict() for item in self.completion_candidates]
        return data


@dataclass
class ScreenContext:
    enabled: bool = False
    participation_mode: str = "off"
    aligned: bool = False
    summary: str = ""
    primary_app: str = ""
    primary_window: str = ""
    primary_domain: str = ""
    tags: list[str] = field(default_factory=list)
    sensitive: bool = False
    summary_only: bool = False
    has_task_signal: bool = False
    evidence_conflict: bool = False
    completion_candidates: list[ScreenCompletionCandidate] = field(default_factory=list)
    evidences: list[ScreenSession] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ScreenContext":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            enabled=bool(payload.get("enabled", False)),
            participation_mode=str(payload.get("participation_mode", "off") or "off"),
            aligned=bool(payload.get("aligned", False)),
            summary=str(payload.get("summary", "") or ""),
            primary_app=str(payload.get("primary_app", "") or ""),
            primary_window=str(payload.get("primary_window", "") or ""),
            primary_domain=str(payload.get("primary_domain", "") or ""),
            tags=[str(item) for item in payload.get("tags", []) if item is not None],
            sensitive=bool(payload.get("sensitive", False)),
            summary_only=bool(payload.get("summary_only", False)),
            has_task_signal=bool(payload.get("has_task_signal", False)),
            evidence_conflict=bool(payload.get("evidence_conflict", False)),
            completion_candidates=[
                ScreenCompletionCandidate.from_dict(item)
                for item in payload.get("completion_candidates", [])
                if isinstance(item, dict)
            ],
            evidences=[ScreenSession.from_dict(item) for item in payload.get("evidences", []) if isinstance(item, dict)],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["completion_candidates"] = [item.to_dict() for item in self.completion_candidates]
        data["evidences"] = [item.to_dict() for item in self.evidences]
        return data


@dataclass
class Scene:
    scene_id: str = ""
    time_start: str = ""
    time_end: str = ""
    text: str = ""
    role: RoleDecision = field(default_factory=RoleDecision)
    keywords_matched: list[str] = field(default_factory=list)
    summary: str = ""
    preview: str = ""
    screen_sessions: list[ScreenSession] = field(default_factory=list)
    screen_context: ScreenContext = field(default_factory=ScreenContext)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "Scene":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            scene_id=str(payload.get("scene_id", "") or ""),
            time_start=str(payload.get("time_start", "") or ""),
            time_end=str(payload.get("time_end", "") or ""),
            text=str(payload.get("text", "") or ""),
            role=RoleDecision.from_dict(payload.get("role")),
            keywords_matched=[str(item) for item in payload.get("keywords_matched", []) if item is not None],
            summary=str(payload.get("summary", "") or ""),
            preview=str(payload.get("preview", "") or ""),
            screen_sessions=[ScreenSession.from_dict(item) for item in payload.get("screen_sessions", []) if isinstance(item, dict)],
            screen_context=ScreenContext.from_dict(payload.get("screen_context")),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.to_dict()
        data["screen_sessions"] = [item.to_dict() for item in self.screen_sessions]
        data["screen_context"] = self.screen_context.to_dict()
        return data


@dataclass
class FactBundle:
    events: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    todos: list[dict[str, Any]] = field(default_factory=list)
    insights: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ArtifactBundle:
    date: str
    transcript_doc: str = ""
    scenes: list[Scene] = field(default_factory=list)
    facts: FactBundle = field(default_factory=FactBundle)
    stats: dict[str, Any] = field(default_factory=dict)


RoleTag = RoleDecision
SceneBlock = Scene
