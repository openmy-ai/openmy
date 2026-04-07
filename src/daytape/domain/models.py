from __future__ import annotations

from dataclasses import dataclass, field
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
    screen_sessions: list["ScreenSession"] = field(default_factory=list)


@dataclass
class ScreenSession:
    """Screenpipe 屏幕会话摘要"""

    app_name: str = ""
    window_name: str = ""
    url_domain: str = ""
    start_time: str = ""
    end_time: str = ""
    frame_ids: list[int] = field(default_factory=list)
    role_hint: str = ""


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
