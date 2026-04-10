from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from openmy.domain.intent import DONE_STATUSES, Event, Fact, Intent, should_generate_open_loop
from openmy.services.context.active_context import ActiveContext

QUERY_KINDS = {"project", "person", "open", "closed", "evidence"}
QUERY_KINDS_REQUIRING_TEXT = {"project", "person", "evidence"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalize(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip().lower()


def _match_score(query: str, *candidates: Any) -> int:
    normalized_query = _normalize(query)
    if not normalized_query:
        return -1

    best = -1
    for candidate in candidates:
        normalized_candidate = _normalize(candidate)
        if not normalized_candidate:
            continue
        if normalized_query == normalized_candidate:
            return 1000 + len(normalized_candidate)
        if normalized_query in normalized_candidate:
            best = max(best, 500 - abs(len(normalized_candidate) - len(normalized_query)))
        elif normalized_candidate in normalized_query:
            best = max(best, 100 - abs(len(normalized_query) - len(normalized_candidate)))
    return best


def _matches(query: str, *candidates: Any) -> bool:
    return _match_score(query, *candidates) >= 0


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _list_dates(project_root: Path, data_root: Path) -> list[str]:
    dates: set[str] = set()
    if data_root.exists():
        for child in data_root.iterdir():
            if child.is_dir() and DATE_RE.match(child.name):
                dates.add(child.name)
    for path in project_root.glob("*.meta.json"):
        stem = path.name.removesuffix(".meta.json")
        if DATE_RE.match(stem):
            dates.add(stem)
    return sorted(dates, reverse=True)


def _resolve_paths(project_root: Path, data_root: Path, date_str: str) -> dict[str, Path]:
    day_dir = data_root / date_str
    dated_meta = day_dir / f"{date_str}.meta.json"
    legacy_meta = day_dir / "meta.json"
    if day_dir.exists():
        return {
            "meta": dated_meta if dated_meta.exists() or not legacy_meta.exists() else legacy_meta,
            "scenes": day_dir / "scenes.json",
            "briefing": day_dir / "daily_briefing.json",
        }
    return {
        "meta": project_root / f"{date_str}.meta.json",
        "scenes": project_root / f"{date_str}.scenes.json",
        "briefing": data_root / date_str / "daily_briefing.json",
    }


def _load_context(data_root: Path) -> ActiveContext:
    path = data_root / "active_context.json"
    if path.exists():
        return ActiveContext.load(path)

    from openmy.services.context.consolidation import consolidate

    return consolidate(data_root)


def _build_day_records(data_root: Path) -> list[dict[str, Any]]:
    project_root = data_root.parent
    records: list[dict[str, Any]] = []
    for date_str in _list_dates(project_root, data_root):
        paths = _resolve_paths(project_root, data_root, date_str)
        meta = _load_json(paths["meta"])
        scenes = _load_json(paths["scenes"])
        briefing = _load_json(paths["briefing"])
        if meta or scenes or briefing:
            records.append({"date": date_str, "meta": meta, "scenes": scenes, "briefing": briefing})
    return records


def _scene_time_range(scene: dict[str, Any]) -> str:
    start = str(scene.get("time_start", "") or "")
    end = str(scene.get("time_end", "") or "")
    return f"{start}-{end}".strip("-")


def _scene_index(day_records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for record in day_records:
        for scene in record.get("scenes", {}).get("scenes", []):
            if not isinstance(scene, dict):
                continue
            scene_id = str(scene.get("scene_id", "") or "")
            if scene_id:
                index[(record["date"], scene_id)] = scene
    return index


def _make_hit(
    *,
    hit_type: str,
    title: str,
    summary: str = "",
    hit_id: str = "",
    date: str = "",
    time: str = "",
    status: str = "",
    current_state: str = "",
    project: str = "",
    provenance_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "type": hit_type,
        "id": hit_id or title,
        "title": title,
        "summary": summary,
        "date": date,
        "time": time,
        "status": status,
        "current_state": current_state,
        "project": project,
        "provenance_refs": provenance_refs or [],
    }


def _dedupe_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = (str(item.get("type", "")), str(item.get("id", "")), str(item.get("date", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _resolve_evidence(
    refs: list[dict[str, Any]],
    scene_lookup: dict[tuple[str, str], dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for ref in refs:
        date = str(ref.get("date", "") or "")
        scene_id = str(ref.get("scene_id", "") or "")
        scene = scene_lookup.get((date, scene_id), {})
        item = {
            "date": date,
            "kind": str(ref.get("kind", "") or ""),
            "scene_id": scene_id,
            "recording_id": str(ref.get("recording_id", "") or ""),
            "quote": str(ref.get("quote", "") or ""),
            "source_path": str(ref.get("source_path", "") or ""),
            "scene_summary": str(scene.get("summary", "") or str(scene.get("preview", "") or "")),
            "time_range": _scene_time_range(scene),
        }
        key = (item["date"], item["kind"], item["scene_id"], item["quote"] or item["scene_summary"])
        if key in seen:
            continue
        seen.add(key)
        evidence.append(item)
        if len(evidence) >= limit:
            break
    return evidence


def _extend_evidence(
    target: list[dict[str, Any]],
    refs: list[dict[str, Any]],
    scene_lookup: dict[tuple[str, str], dict[str, Any]],
    limit: int,
) -> None:
    if len(target) >= limit:
        return
    remaining = limit - len(target)
    target.extend(_resolve_evidence(refs, scene_lookup, remaining))


def _refs_from_payload(
    *,
    date_str: str,
    kind: str,
    source_path: str,
    scene_id: str = "",
    recording_id: str = "",
    quote: str = "",
    refs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if refs:
        return refs
    return [
        {
            "date": date_str,
            "kind": kind,
            "scene_id": scene_id,
            "recording_id": recording_id,
            "quote": quote,
            "source_path": source_path,
        }
    ]


def _loop_is_open(loop: Any) -> bool:
    status = str(getattr(loop, "status", "") or "").lower()
    state = str(getattr(loop, "current_state", "") or "").lower()
    return status not in DONE_STATUSES and state not in {"closed", "done"}


def _loop_is_closed(loop: Any) -> bool:
    status = str(getattr(loop, "status", "") or "").lower()
    state = str(getattr(loop, "current_state", "") or "").lower()
    return status in DONE_STATUSES or state in {"closed", "done"}


def _project_query(
    ctx: ActiveContext,
    day_records: list[dict[str, Any]],
    scene_lookup: dict[tuple[str, str], dict[str, Any]],
    query: str,
    limit: int,
) -> dict[str, Any]:
    project_cards = list(ctx.core_memory.focus_projects) + list(ctx.rolling_context.active_projects)
    matched_project = None
    best_score = -1
    for item in project_cards:
        score = _match_score(query, item.title, item.project_id, item.current_goal, *item.next_actions)
        if score > best_score:
            best_score = score
            matched_project = item
    canonical = matched_project.title if matched_project is not None else query.strip()

    current_hits: list[dict[str, Any]] = []
    history_hits: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for item in project_cards:
        if not _matches(canonical, item.title, item.project_id):
            continue
        hit = _make_hit(
            hit_type="project",
            hit_id=item.project_id or item.id,
            title=item.title,
            summary=item.current_goal,
            status=item.status,
            current_state=item.current_state,
            project=item.title,
            provenance_refs=item.provenance_refs,
        )
        current_hits.append(hit)
        _extend_evidence(evidence, hit["provenance_refs"], scene_lookup, limit)

    for item in ctx.rolling_context.recent_decisions:
        if not _matches(canonical, item.topic, item.decision):
            continue
        hit = _make_hit(
            hit_type="decision",
            hit_id=item.decision_id or item.id,
            title=item.decision,
            summary=item.topic,
            date=item.effective_from[:10],
            time=item.effective_from[11:16] if item.effective_from else "",
            current_state=item.current_state,
            project=item.topic,
            provenance_refs=item.provenance_refs,
        )
        current_hits.append(hit)
        _extend_evidence(evidence, hit["provenance_refs"], scene_lookup, limit)

    for item in ctx.rolling_context.recent_events:
        if not _matches(canonical, item.project, item.summary):
            continue
        hit = _make_hit(
            hit_type="event",
            hit_id=item.event_id or item.id,
            title=item.summary,
            summary=item.project,
            date=item.happened_at[:10],
            time=item.time_label,
            current_state=item.current_state,
            project=item.project,
            provenance_refs=item.provenance_refs,
        )
        history_hits.append(hit)
        _extend_evidence(evidence, hit["provenance_refs"], scene_lookup, limit)

    for record in day_records:
        date_str = record["date"]
        for raw in record.get("meta", {}).get("facts", []):
            fact = Fact.from_dict(raw)
            if not _matches(canonical, fact.topic, fact.content):
                continue
            refs = _refs_from_payload(
                date_str=date_str,
                kind="fact",
                source_path=f"{date_str}.meta.json",
                scene_id=fact.source_scene_id,
                recording_id=fact.source_recording_id,
                quote=fact.evidence_quote,
                refs=fact.provenance_refs,
            )
            hit = _make_hit(
                hit_type="fact",
                hit_id=fact.fact_id,
                title=fact.content,
                summary=fact.topic,
                date=date_str,
                current_state=fact.current_state,
                project=fact.topic,
                provenance_refs=refs,
            )
            history_hits.append(hit)
            _extend_evidence(evidence, refs, scene_lookup, limit)

        for raw in record.get("meta", {}).get("intents", []):
            intent = Intent.from_dict(raw)
            project_hint = intent.project_hint.strip() or intent.topic.strip()
            if not _matches(canonical, project_hint, intent.what):
                continue
            refs = _refs_from_payload(
                date_str=date_str,
                kind="intent",
                source_path=f"{date_str}.meta.json",
                scene_id=intent.source_scene_id,
                recording_id=intent.source_recording_id,
                quote=intent.evidence_quote,
                refs=intent.provenance_refs,
            )
            if intent.kind == "decision":
                hit = _make_hit(
                    hit_type="decision",
                    hit_id=intent.intent_id,
                    title=intent.what,
                    summary=project_hint,
                    date=date_str,
                    status=intent.status,
                    current_state=intent.current_state,
                    project=project_hint,
                    provenance_refs=refs,
                )
                current_hits.append(hit)
            elif should_generate_open_loop(intent) and intent.status not in DONE_STATUSES:
                hit = _make_hit(
                    hit_type="loop",
                    hit_id=intent.intent_id,
                    title=intent.what,
                    summary=project_hint,
                    date=date_str,
                    status=intent.status,
                    current_state=intent.current_state or "active",
                    project=project_hint,
                    provenance_refs=refs,
                )
                current_hits.append(hit)
            else:
                continue
            _extend_evidence(evidence, refs, scene_lookup, limit)

    current_hits = _dedupe_items(current_hits, limit)
    history_hits = _dedupe_items(history_hits, limit)
    evidence = _dedupe_items(evidence, limit)
    return {
        "kind": "project",
        "query": query,
        "summary": f"{canonical} 最近有 {len(current_hits)} 条当前上下文，近期待回看 {len(history_hits)} 条历史记录。",
        "current_hits": current_hits,
        "history_hits": history_hits,
        "evidence": evidence,
    }


def _person_query(
    ctx: ActiveContext,
    day_records: list[dict[str, Any]],
    scene_lookup: dict[tuple[str, str], dict[str, Any]],
    query: str,
    limit: int,
) -> dict[str, Any]:
    current_hits: list[dict[str, Any]] = []
    history_hits: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for person in list(ctx.core_memory.key_people) + list(ctx.stable_profile.key_people_registry):
        aliases = getattr(person, "aliases", []) or []
        if _matches(query, person.display_name, person.entity_id, *aliases):
            current_hits.append(
                _make_hit(
                    hit_type="person",
                    hit_id=person.entity_id or person.id,
                    title=person.display_name,
                    summary=person.relation_type,
                )
            )

    for loop in list(ctx.core_memory.open_loops) + list(ctx.rolling_context.open_loops):
        if not _matches(query, loop.title, loop.waiting_on):
            continue
        hit = _make_hit(
            hit_type="loop",
            hit_id=loop.loop_id or loop.id,
            title=loop.title,
            status=loop.status,
            current_state=loop.current_state,
            provenance_refs=loop.provenance_refs,
        )
        (history_hits if _loop_is_closed(loop) else current_hits).append(hit)
        _extend_evidence(evidence, hit["provenance_refs"], scene_lookup, limit)

    for record in day_records:
        date_str = record["date"]
        for raw in record.get("scenes", {}).get("scenes", []):
            scene = raw if isinstance(raw, dict) else {}
            role = scene.get("role", {}) if isinstance(scene.get("role", {}), dict) else {}
            if not _matches(query, role.get("addressed_to", ""), scene.get("summary", ""), scene.get("preview", "")):
                continue
            refs = [
                {
                    "date": date_str,
                    "kind": "scene",
                    "scene_id": str(scene.get("scene_id", "") or ""),
                    "quote": str(scene.get("preview", "") or ""),
                    "source_path": "scenes.json",
                }
            ]
            hit = _make_hit(
                hit_type="scene",
                hit_id=str(scene.get("scene_id", "") or ""),
                title=str(scene.get("summary", "") or str(scene.get("preview", "") or "")),
                summary=str(role.get("addressed_to", "") or ""),
                date=date_str,
                time=_scene_time_range(scene),
                provenance_refs=refs,
            )
            history_hits.append(hit)
            _extend_evidence(evidence, refs, scene_lookup, limit)

        for raw in record.get("meta", {}).get("facts", []):
            fact = Fact.from_dict(raw)
            if not _matches(query, fact.content, fact.topic, fact.evidence_quote):
                continue
            refs = _refs_from_payload(
                date_str=date_str,
                kind="fact",
                source_path=f"{date_str}.meta.json",
                scene_id=fact.source_scene_id,
                recording_id=fact.source_recording_id,
                quote=fact.evidence_quote,
                refs=fact.provenance_refs,
            )
            hit = _make_hit(
                hit_type="fact",
                hit_id=fact.fact_id,
                title=fact.content,
                summary=fact.topic,
                date=date_str,
                current_state=fact.current_state,
                provenance_refs=refs,
            )
            history_hits.append(hit)
            _extend_evidence(evidence, refs, scene_lookup, limit)

    current_hits = _dedupe_items(current_hits, limit)
    history_hits = _dedupe_items(history_hits, limit)
    evidence = _dedupe_items(evidence, limit)
    return {
        "kind": "person",
        "query": query,
        "summary": f"最近和 {query} 相关的结构化上下文有 {len(current_hits) + len(history_hits)} 条。",
        "current_hits": current_hits,
        "history_hits": history_hits,
        "evidence": evidence,
    }


def _open_query(
    ctx: ActiveContext,
    scene_lookup: dict[tuple[str, str], dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    current_hits: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for loop in ctx.rolling_context.open_loops:
        if not _loop_is_open(loop):
            continue
        hit = _make_hit(
            hit_type="loop",
            hit_id=loop.loop_id or loop.id,
            title=loop.title,
            status=loop.status,
            current_state=loop.current_state,
            provenance_refs=loop.provenance_refs,
        )
        current_hits.append(hit)
        _extend_evidence(evidence, hit["provenance_refs"], scene_lookup, limit)

    current_hits = _dedupe_items(current_hits, limit)
    evidence = _dedupe_items(evidence, limit)
    return {
        "kind": "open",
        "query": "",
        "summary": f"现在还有 {len(current_hits)} 个待办处于未关闭状态。",
        "current_hits": current_hits,
        "history_hits": [],
        "evidence": evidence,
    }


def _closed_query(
    ctx: ActiveContext,
    day_records: list[dict[str, Any]],
    scene_lookup: dict[tuple[str, str], dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    history_hits: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for loop in ctx.rolling_context.open_loops:
        if not _loop_is_closed(loop):
            continue
        hit = _make_hit(
            hit_type="closed_item",
            hit_id=loop.loop_id or loop.id,
            title=loop.title,
            status=loop.status,
            current_state=loop.current_state or "closed",
            date=(loop.valid_until or loop.last_seen_at)[:10],
            provenance_refs=loop.provenance_refs,
        )
        history_hits.append(hit)
        _extend_evidence(evidence, hit["provenance_refs"], scene_lookup, limit)

    for record in day_records:
        date_str = record["date"]
        for raw in record.get("meta", {}).get("intents", []):
            intent = Intent.from_dict(raw)
            if intent.status not in DONE_STATUSES:
                continue
            refs = _refs_from_payload(
                date_str=date_str,
                kind="intent",
                source_path=f"{date_str}.meta.json",
                scene_id=intent.source_scene_id,
                recording_id=intent.source_recording_id,
                quote=intent.evidence_quote,
                refs=intent.provenance_refs,
            )
            hit = _make_hit(
                hit_type="closed_item",
                hit_id=intent.intent_id,
                title=intent.what,
                status=intent.status,
                current_state=intent.current_state or "closed",
                date=(intent.valid_until or intent.valid_from)[:10] if (intent.valid_until or intent.valid_from) else date_str,
                provenance_refs=refs,
            )
            history_hits.append(hit)
            _extend_evidence(evidence, refs, scene_lookup, limit)

    history_hits = _dedupe_items(history_hits, limit)
    evidence = _dedupe_items(evidence, limit)
    return {
        "kind": "closed",
        "query": "",
        "summary": f"最近找到 {len(history_hits)} 个已完成或已关闭的事项。",
        "current_hits": [],
        "history_hits": history_hits,
        "evidence": evidence,
    }


def _evidence_query(
    ctx: ActiveContext,
    day_records: list[dict[str, Any]],
    scene_lookup: dict[tuple[str, str], dict[str, Any]],
    query: str,
    limit: int,
) -> dict[str, Any]:
    current_hits: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for loop in ctx.rolling_context.open_loops:
        if not _matches(query, loop.title, loop.loop_id, loop.id):
            continue
        hit = _make_hit(
            hit_type="loop",
            hit_id=loop.loop_id or loop.id,
            title=loop.title,
            status=loop.status,
            current_state=loop.current_state,
            provenance_refs=loop.provenance_refs,
        )
        current_hits.append(hit)
        _extend_evidence(evidence, hit["provenance_refs"], scene_lookup, limit)

    for item in ctx.rolling_context.recent_decisions:
        if not _matches(query, item.decision, item.decision_id, item.topic):
            continue
        hit = _make_hit(
            hit_type="decision",
            hit_id=item.decision_id or item.id,
            title=item.decision,
            summary=item.topic,
            current_state=item.current_state,
            provenance_refs=item.provenance_refs,
        )
        current_hits.append(hit)
        _extend_evidence(evidence, hit["provenance_refs"], scene_lookup, limit)

    for record in day_records:
        date_str = record["date"]
        for raw in record.get("meta", {}).get("facts", []):
            fact = Fact.from_dict(raw)
            if not _matches(query, fact.fact_id, fact.content, fact.topic):
                continue
            refs = _refs_from_payload(
                date_str=date_str,
                kind="fact",
                source_path=f"{date_str}.meta.json",
                scene_id=fact.source_scene_id,
                recording_id=fact.source_recording_id,
                quote=fact.evidence_quote,
                refs=fact.provenance_refs,
            )
            hit = _make_hit(
                hit_type="fact",
                hit_id=fact.fact_id,
                title=fact.content,
                summary=fact.topic,
                current_state=fact.current_state,
                provenance_refs=refs,
            )
            current_hits.append(hit)
            _extend_evidence(evidence, refs, scene_lookup, limit)

        for raw in record.get("meta", {}).get("intents", []):
            intent = Intent.from_dict(raw)
            if not _matches(query, intent.intent_id, intent.what, intent.evidence_quote):
                continue
            refs = _refs_from_payload(
                date_str=date_str,
                kind="intent",
                source_path=f"{date_str}.meta.json",
                scene_id=intent.source_scene_id,
                recording_id=intent.source_recording_id,
                quote=intent.evidence_quote,
                refs=intent.provenance_refs,
            )
            hit = _make_hit(
                hit_type="intent",
                hit_id=intent.intent_id,
                title=intent.what,
                summary=intent.topic,
                status=intent.status,
                current_state=intent.current_state,
                provenance_refs=refs,
            )
            current_hits.append(hit)
            _extend_evidence(evidence, refs, scene_lookup, limit)

        for raw in record.get("meta", {}).get("events", []):
            event = Event.from_dict(raw)
            if not _matches(query, event.event_id, event.summary, event.project):
                continue
            refs = _refs_from_payload(
                date_str=date_str,
                kind="event",
                source_path=f"{date_str}.meta.json",
                scene_id=event.source_scene_id,
                recording_id=event.source_recording_id,
                refs=event.provenance_refs,
            )
            hit = _make_hit(
                hit_type="event",
                hit_id=event.event_id,
                title=event.summary,
                summary=event.project,
                current_state=event.current_state,
                provenance_refs=refs,
            )
            current_hits.append(hit)
            _extend_evidence(evidence, refs, scene_lookup, limit)

    current_hits = _dedupe_items(current_hits, limit)
    evidence = _dedupe_items(evidence, limit)
    return {
        "kind": "evidence",
        "query": query,
        "summary": f"找到 {len(evidence)} 条和“{query}”相关的结构化证据。",
        "current_hits": current_hits,
        "history_hits": [],
        "evidence": evidence,
    }


def query_context(
    data_root: Path,
    *,
    kind: str,
    query: str = "",
    limit: int = 5,
    include_evidence: bool = True,
) -> dict[str, Any]:
    final_kind = str(kind or "").strip().lower()
    final_query = str(query or "").strip()
    final_limit = max(1, min(int(limit or 5), 20))

    if final_kind not in QUERY_KINDS:
        return {"error": f"不支持的查询类型：{kind}"}
    if final_kind in QUERY_KINDS_REQUIRING_TEXT and not final_query:
        return {"error": f"{final_kind} 查询需要提供 query"}

    ctx = _load_context(data_root)
    day_records = _build_day_records(data_root)
    scene_lookup = _scene_index(day_records)

    if final_kind == "project":
        result = _project_query(ctx, day_records, scene_lookup, final_query, final_limit)
    elif final_kind == "person":
        result = _person_query(ctx, day_records, scene_lookup, final_query, final_limit)
    elif final_kind == "open":
        result = _open_query(ctx, scene_lookup, final_limit)
    elif final_kind == "closed":
        result = _closed_query(ctx, day_records, scene_lookup, final_limit)
    else:
        result = _evidence_query(ctx, day_records, scene_lookup, final_query, final_limit)

    if not include_evidence and final_kind != "evidence":
        result["evidence"] = []
    return result


def render_query_result(result: dict[str, Any]) -> str:
    lines = [str(result.get("summary", "") or "").strip() or "没有命中结果。"]

    current_hits = result.get("current_hits", []) or []
    history_hits = result.get("history_hits", []) or []
    evidence = result.get("evidence", []) or []

    if current_hits:
        lines.append("")
        lines.append("当前命中：")
        for item in current_hits[:5]:
            title = item.get("title") or item.get("summary") or item.get("id")
            state = item.get("current_state") or item.get("status") or ""
            suffix = f" [{state}]" if state else ""
            lines.append(f"- {title}{suffix}")

    if history_hits:
        lines.append("")
        lines.append("历史命中：")
        for item in history_hits[:5]:
            title = item.get("title") or item.get("summary") or item.get("id")
            date = item.get("date") or ""
            prefix = f"{date} " if date else ""
            lines.append(f"- {prefix}{title}")

    if evidence:
        lines.append("")
        lines.append("证据来源：")
        for item in evidence[:5]:
            date = item.get("date") or ""
            scene = item.get("scene_id") or "unknown"
            summary = item.get("quote") or item.get("scene_summary") or item.get("source_path") or ""
            prefix = f"{date} / {scene}" if date else scene
            lines.append(f"- {prefix}: {summary}")

    return "\n".join(lines).strip()
