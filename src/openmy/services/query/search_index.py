from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openmy.utils.io import safe_write_json

INDEX_SCHEMA_VERSION = "openmy.search_index.v1"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalize(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip().lower()


def _matches(query: str, *candidates: Any) -> bool:
    normalized_query = _normalize(query)
    if not normalized_query:
        return False
    for candidate in candidates:
        normalized_candidate = _normalize(candidate)
        if not normalized_candidate:
            continue
        if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
            return True
    return False


def index_path(data_root: Path) -> Path:
    return data_root / "search_index.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _terms_from_meta(meta: dict[str, Any]) -> dict[str, list[str]]:
    project_terms: list[str] = []
    person_terms: list[str] = []
    evidence_terms: list[str] = []
    closed_terms: list[str] = []

    for event in meta.get("events", []):
        if not isinstance(event, dict):
            continue
        project_terms.extend([event.get("project", ""), event.get("summary", "")])
        evidence_terms.extend([event.get("event_id", ""), event.get("project", ""), event.get("summary", "")])

    for fact in meta.get("facts", []):
        if not isinstance(fact, dict):
            continue
        project_terms.extend([fact.get("topic", ""), fact.get("content", "")])
        person_terms.extend([fact.get("topic", ""), fact.get("content", ""), fact.get("evidence_quote", "")])
        evidence_terms.extend([fact.get("fact_id", ""), fact.get("topic", ""), fact.get("content", ""), fact.get("evidence_quote", "")])

    for intent in meta.get("intents", []):
        if not isinstance(intent, dict):
            continue
        who = intent.get("who", {}) if isinstance(intent.get("who", {}), dict) else {}
        project_terms.extend([intent.get("project_hint", ""), intent.get("topic", ""), intent.get("what", "")])
        person_terms.extend([who.get("label", ""), intent.get("what", ""), intent.get("evidence_quote", "")])
        evidence_terms.extend([intent.get("intent_id", ""), intent.get("what", ""), intent.get("evidence_quote", "")])
        status = str(intent.get("status", "") or "").lower()
        if status in {"done", "closed", "cancelled", "abandoned", "rejected"}:
            closed_terms.extend([intent.get("what", ""), intent.get("evidence_quote", "")])

    return {
        "project": [item for item in project_terms if item],
        "person": [item for item in person_terms if item],
        "evidence": [item for item in evidence_terms if item],
        "closed": [item for item in closed_terms if item],
    }


def _terms_from_scenes(scenes: dict[str, Any]) -> dict[str, list[str]]:
    project_terms: list[str] = []
    person_terms: list[str] = []
    evidence_terms: list[str] = []

    for scene in scenes.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        role = scene.get("role", {}) if isinstance(scene.get("role", {}), dict) else {}
        summary = str(scene.get("summary", "") or "")
        preview = str(scene.get("preview", "") or scene.get("text", "") or "")
        addressed_to = str(role.get("addressed_to", "") or "")
        project_terms.extend([summary, preview])
        person_terms.extend([addressed_to, summary, preview])
        evidence_terms.extend([scene.get("scene_id", ""), summary, preview])

    return {
        "project": [item for item in project_terms if item],
        "person": [item for item in person_terms if item],
        "evidence": [item for item in evidence_terms if item],
    }


def _read_word_count(day_dir: Path) -> int:
    transcript_path = day_dir / "transcript.md"
    if not transcript_path.exists():
        return 0
    try:
        content = transcript_path.read_text(encoding="utf-8")
    except Exception:
        return 0
    return len(re.sub(r"\s+", "", content))


def build_day_entry(
    date_str: str,
    *,
    day_dir: Path,
    meta: dict[str, Any],
    scenes: dict[str, Any],
    briefing: dict[str, Any],
) -> dict[str, Any]:
    meta_terms = _terms_from_meta(meta)
    scene_terms = _terms_from_scenes(scenes)
    project_terms = meta_terms["project"] + scene_terms["project"] + [meta.get("daily_summary", ""), briefing.get("summary", "")]
    person_terms = meta_terms["person"] + scene_terms["person"]
    evidence_terms = meta_terms["evidence"] + scene_terms["evidence"] + [meta.get("daily_summary", ""), briefing.get("summary", "")]

    return {
        "date": date_str,
        "daily_summary": str(meta.get("daily_summary", "") or briefing.get("summary", "") or ""),
        "has_meta": bool(meta),
        "has_scenes": bool(scenes.get("scenes", [])),
        "has_briefing": bool(briefing),
        "word_count": _read_word_count(day_dir),
        "scene_count": len(scenes.get("scenes", [])) if isinstance(scenes.get("scenes", []), list) else 0,
        "terms": {
            "project": [item for item in project_terms if item],
            "person": [item for item in person_terms if item],
            "evidence": [item for item in evidence_terms if item],
            "closed": meta_terms["closed"],
        },
    }


def update_search_index_for_day(
    *,
    day_dir: Path,
    date_str: str,
    meta: dict[str, Any],
    scenes: dict[str, Any] | None = None,
    briefing: dict[str, Any] | None = None,
) -> None:
    data_root = day_dir.parent
    path = index_path(data_root)
    payload = _read_json(path)
    days = payload.get("days", []) if isinstance(payload.get("days", []), list) else []

    if scenes is None:
        scenes = _read_json(day_dir / "scenes.json")
    if briefing is None:
        briefing = _read_json(day_dir / "daily_briefing.json")

    new_entry = build_day_entry(
        date_str,
        day_dir=day_dir,
        meta=meta,
        scenes=scenes,
        briefing=briefing,
    )
    filtered = [item for item in days if isinstance(item, dict) and str(item.get("date", "") or "") != date_str]
    filtered.append(new_entry)
    filtered.sort(key=lambda item: str(item.get("date", "")), reverse=True)
    safe_write_json(
        path,
        {"schema_version": INDEX_SCHEMA_VERSION, "days": filtered},
    )


def load_search_index(data_root: Path) -> list[dict[str, Any]]:
    payload = _read_json(index_path(data_root))
    days = payload.get("days", [])
    if not isinstance(days, list):
        return []
    return [item for item in days if isinstance(item, dict) and DATE_RE.match(str(item.get("date", "") or ""))]


def list_index_dates(data_root: Path) -> list[str]:
    return [str(item.get("date", "")) for item in load_search_index(data_root)]


def get_day_status_from_index(data_root: Path, date_str: str) -> dict[str, Any] | None:
    for item in load_search_index(data_root):
        if str(item.get("date", "") or "") != date_str:
            continue
        return {
            "date": date_str,
            "has_transcript": bool(item.get("word_count", 0)),
            "has_raw": False,
            "has_scenes": bool(item.get("has_scenes", False)),
            "has_briefing": bool(item.get("has_briefing", False)),
            "word_count": int(item.get("word_count", 0) or 0),
            "scene_count": int(item.get("scene_count", 0) or 0),
            "role_distribution": {},
        }
    return None


def candidate_dates_for_query(data_root: Path, *, kind: str, query: str = "") -> list[str]:
    days = load_search_index(data_root)
    if kind == "open":
        return []
    if kind == "closed" and not query:
        return [str(item.get("date", "")) for item in days if item.get("terms", {}).get("closed")]
    if not query:
        return [str(item.get("date", "")) for item in days]

    matched: list[str] = []
    for item in days:
        terms = item.get("terms", {}) if isinstance(item.get("terms", {}), dict) else {}
        candidate_terms = list(terms.get(kind, [])) + [item.get("daily_summary", "")]
        if _matches(query, *candidate_terms):
            matched.append(str(item.get("date", "")))
    return matched
