#!/usr/bin/env python3
"""Active Context 汇总器 — 把日级数据提升为全局状态快照。"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openmy.config import ROLE_RECOGNITION_ENABLED
from openmy.domain.intent import (
    DONE_STATUSES,
    Event,
    Fact,
    Intent,
    adjudicate_temporal_state,
    build_canonical_key,
    intent_to_loop_type,
    should_generate_open_loop,
)
from openmy.services.context.active_context import (
    ActiveContext,
    ChangeItem,
    CommunicationContract,
    ConflictItem,
    CoreMemory,
    DecisionItem,
    EntityRegistryCard,
    EntityRollup,
    EventItem,
    Identity,
    IngestionHealth,
    OpenLoop,
    ProjectCard,
    QualityMetrics,
    RealtimeContext,
    RollingContext,
    SceneRefDigest,
    StableProfile,
    TodayState,
)
from openmy.services.context.corrections import apply_corrections, load_corrections


DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ROOT_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.(?:md|meta\.json|scenes\.json)$")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _list_dates(project_root: Path, data_root: Path) -> list[str]:
    dates: set[str] = set()
    if data_root.exists():
        for child in data_root.iterdir():
            if child.is_dir() and DATE_DIR_RE.match(child.name):
                dates.add(child.name)

    for child in project_root.iterdir():
        match = ROOT_FILE_RE.match(child.name)
        if match:
            dates.add(match.group(1))

    return sorted(dates)


def _resolve_paths(project_root: Path, data_root: Path, date_str: str) -> dict[str, Path]:
    day_dir = data_root / date_str
    return {
        "scenes": day_dir / "scenes.json" if (day_dir / "scenes.json").exists() else project_root / f"{date_str}.scenes.json",
        "briefing": day_dir / "daily_briefing.json",
        "meta": day_dir / f"{date_str}.meta.json" if (day_dir / f"{date_str}.meta.json").exists() else project_root / f"{date_str}.meta.json",
    }


def _known_relation_type(name: str) -> str:
    if name in {"AI助手", "Claude", "ChatGPT", "GPT", "Gemini"}:
        return "ai"
    if name in {"老婆", "伴侣", "宝贝"}:
        return "partner"
    if name in {"宠物", "狗", "猫"}:
        return "pet"
    return "person"


def _slug(prefix: str, text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text).strip("_").lower()
    cleaned = cleaned[:40] if cleaned else "item"
    return f"{prefix}_{cleaned}"


def _iso_at(date_str: str, time_str: str = "00:00") -> str:
    cleaned_time = time_str.strip() or "00:00"
    if not re.match(r"^\d{2}:\d{2}$", cleaned_time):
        cleaned_time = "00:00"
    return f"{date_str}T{cleaned_time}:00+08:00"


def _build_provenance(
    *,
    date_str: str,
    kind: str,
    scene_id: str = "",
    recording_id: str = "",
    quote: str = "",
    source_path: str = "",
) -> list[dict[str, str]]:
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


def _extract_projects(briefing: dict[str, Any], meta: dict[str, Any]) -> dict[str, list[str]]:
    projects: dict[str, list[str]] = defaultdict(list)

    summary = str(briefing.get("summary", "")).strip()
    if "OpenMy" in summary:
        projects["OpenMy"].append(summary)

    raw_intents = meta.get("intents")
    if isinstance(raw_intents, list):
        for raw in raw_intents:
            if not isinstance(raw, dict):
                continue
            intent = Intent.from_dict(raw)
            project = (intent.project_hint or intent.topic).strip()
            snippet = intent.what.strip()
            if project:
                projects[project].append(snippet or project)

    for event in meta.get("events", []):
        if isinstance(event, dict):
            project = str(event.get("project", "")).strip()
            item_summary = str(event.get("summary", "")).strip()
            if project:
                projects[project].append(item_summary or project)

    for item in meta.get("decisions", []):
        if isinstance(item, dict):
            project = str(item.get("project", "")).strip()
            decision = str(item.get("what", "")).strip()
            if project:
                projects[project].append(decision or project)

    for item in meta.get("todos", []):
        if isinstance(item, dict):
            project = str(item.get("project", "")).strip()
            task = str(item.get("task", "")).strip()
            if project:
                projects[project].append(task or project)

    return projects


def _make_open_loops(briefing: dict[str, Any], meta: dict[str, Any], date_str: str) -> list[OpenLoop]:
    loops: dict[str, OpenLoop] = {}

    raw_intents = meta.get("intents")
    if isinstance(raw_intents, list):
        # Intent 只代表未来约束；低置信、已完成、纯决策都不应该长成 open loop。
        for raw in raw_intents:
            if not isinstance(raw, dict):
                continue
            intent = Intent.from_dict(raw)
            if not should_generate_open_loop(intent):
                continue

            title = intent.what.strip()
            if not title:
                continue

            # 执行者是一个对象，loop_type 由 who.kind 决定，而不是靠文本猜。
            loops.setdefault(
                title,
                OpenLoop(
                    id=_slug("loop", title),
                    loop_id=_slug("loop", title),
                    title=title,
                    loop_type=intent_to_loop_type(intent),
                    priority="high" if intent.confidence_label == "high" else "medium",
                    status="open",
                    owner=intent.who.kind or "self",
                    waiting_on=intent.who.label if intent.who.kind in {"agent", "other_person"} else "",
                    source_rank="declared",
                    confidence=intent.confidence_score or 0.8,
                    first_seen_at=_iso_at(date_str),
                    last_seen_at=f"{date_str}T23:59:59+08:00",
                    reinforcement_count=1,
                    due_hint=intent.due.iso_date or intent.due.raw_text,
                    valid_from=intent.valid_from or _iso_at(date_str),
                    valid_until=intent.valid_until or "",
                    current_state=adjudicate_temporal_state(
                        status=intent.status,
                        current_state=intent.current_state,
                        valid_from=intent.valid_from or _iso_at(date_str),
                        valid_until=intent.valid_until,
                        due_iso_date=intent.due.iso_date,
                        reference_date=date_str,
                    )["state"],
                    state_reason=adjudicate_temporal_state(
                        status=intent.status,
                        current_state=intent.current_state,
                        valid_from=intent.valid_from or _iso_at(date_str),
                        valid_until=intent.valid_until,
                        due_iso_date=intent.due.iso_date,
                        reference_date=date_str,
                    )["reason"],
                    provenance_refs=_build_provenance(
                        date_str=date_str,
                        kind="intent",
                        scene_id=intent.source_scene_id,
                        recording_id=intent.source_recording_id,
                        quote=intent.evidence_quote,
                        source_path=f"{date_str}.meta.json",
                    ),
                ),
            )
        return list(loops.values())

    for item in briefing.get("todos_open", []):
        title = str(item).strip()
        if not title:
            continue
        # 截断保护：超过 80 字的不是待办，是段落摘要，截断取第一句
        if len(title) > 80:
            first_sentence = re.split(r'[。！？!?]', title)[0]
            title = first_sentence[:80] if first_sentence else title[:80]
        loops.setdefault(
            title,
            OpenLoop(
                id=_slug("loop", title),
                loop_id=_slug("loop", title),
                title=title,
                loop_type="todo",
                priority="medium",
                status="open",
                source_rank="aggregate",
                confidence=0.8,
                first_seen_at=_iso_at(date_str),
                last_seen_at=f"{date_str}T23:59:59+08:00",
                reinforcement_count=1,
                valid_from=_iso_at(date_str),
                current_state="active",
                state_reason="briefing_open_loop",
                provenance_refs=_build_provenance(
                    date_str=date_str,
                    kind="briefing.todo",
                    source_path="daily_briefing.json",
                ),
            ),
        )

    for item in meta.get("todos", []):
        if isinstance(item, dict):
            title = str(item.get("task", "")).strip()
            priority = str(item.get("priority", "")).strip() or "medium"
        else:
            title = str(item).strip()
            priority = "medium"
        if not title:
            continue
        # 截断保护
        if len(title) > 80:
            first_sentence = re.split(r'[。！？!?]', title)[0]
            title = first_sentence[:80] if first_sentence else title[:80]
        loops.setdefault(
            title,
            OpenLoop(
                id=_slug("loop", title),
                loop_id=_slug("loop", title),
                title=title,
                loop_type="todo",
                priority=priority,
                status="open",
                source_rank="declared",
                confidence=0.9,
                first_seen_at=_iso_at(date_str),
                last_seen_at=f"{date_str}T23:59:59+08:00",
                reinforcement_count=1,
                valid_from=_iso_at(date_str),
                current_state="active",
                state_reason="meta_open_loop",
                provenance_refs=_build_provenance(
                    date_str=date_str,
                    kind="meta.todo",
                    source_path=f"{date_str}.meta.json",
                ),
            ),
        )

    return list(loops.values())


def _filter_stale_loops(loops: list[OpenLoop], stale_days: int = 3, expire_days: int = 7) -> list[OpenLoop]:
    """Fix B: 过期机制 — 3 天 stale，7 天踢出。"""
    today = date.today()
    result: list[OpenLoop] = []
    for loop in loops:
        last_seen = loop.last_seen_at or ""
        if last_seen:
            try:
                seen_date = date.fromisoformat(last_seen[:10])
                age = (today - seen_date).days
                if age >= expire_days:
                    continue  # 超过 7 天，踢出
                if age >= stale_days:
                    loop.status = "stale"
                    loop.current_state = "stale"
            except (ValueError, TypeError):
                pass
        result.append(loop)
    return result[:10]


def _auto_close_loops(
    loops: dict[str, OpenLoop],
    all_metas: list[tuple[str, dict]],
) -> None:
    """Fix I: 用新录音的 done intents 自动关闭匹配的 open_loops。"""
    done_whats: dict[str, str] = {}
    for date_str, meta in all_metas:
        for raw in meta.get("intents", []):
            if not isinstance(raw, dict):
                continue
            intent = Intent.from_dict(raw)
            if intent.status in DONE_STATUSES and intent.what.strip():
                done_whats[intent.what.strip().lower()] = intent.valid_until or _iso_at(date_str, "23:59")

    if not done_whats:
        return

    for title, loop in loops.items():
        if loop.status != "open":
            continue
        title_lower = title.lower()
        for done_what, done_at in done_whats.items():
            # 模糊匹配：done_what 包含在 loop title 里，或反过来
            if done_what in title_lower or title_lower in done_what:
                loop.status = "closed"
                loop.current_state = "closed"
                loop.valid_until = done_at
                loop.state_reason = "matched_done_intent"
                break


def _make_decisions(briefing: dict[str, Any], meta: dict[str, Any], date_str: str) -> list[DecisionItem]:
    items: dict[str, DecisionItem] = {}

    raw_intents = meta.get("intents")
    if isinstance(raw_intents, list):
        for raw in raw_intents:
            if not isinstance(raw, dict):
                continue
            intent = Intent.from_dict(raw)
            if intent.kind != "decision":
                continue
            decision = intent.what.strip()
            topic = (intent.project_hint or intent.topic or "intent").strip()
            if not decision:
                continue
            items.setdefault(
                decision,
                DecisionItem(
                    id=_slug("decision", decision),
                    decision_id=_slug("decision", decision),
                    topic=topic,
                    decision=decision,
                    scope="project",
                    effective_from=f"{date_str}T12:00:00+08:00",
                    source_rank="declared",
                    confidence=intent.confidence_score or 0.9,
                    valid_from=intent.valid_from or _iso_at(date_str),
                    valid_until=intent.valid_until or "",
                    current_state=intent.current_state or "active",
                    first_seen_at=intent.valid_from or _iso_at(date_str),
                    last_seen_at=f"{date_str}T23:59:59+08:00",
                    reinforcement_count=1,
                    state_reason="intent_decision",
                    provenance_refs=_build_provenance(
                        date_str=date_str,
                        kind="intent.decision",
                        scene_id=intent.source_scene_id,
                        recording_id=intent.source_recording_id,
                        quote=intent.evidence_quote,
                        source_path=f"{date_str}.meta.json",
                    ),
                ),
            )
        return list(items.values())

    for text in briefing.get("decisions", []):
        decision = str(text).strip()
        if not decision:
            continue
        items.setdefault(
            decision,
            DecisionItem(
                id=_slug("decision", decision),
                decision_id=_slug("decision", decision),
                topic="briefing",
                decision=decision,
                scope="project",
                effective_from=f"{date_str}T12:00:00+08:00",
                source_rank="aggregate",
                confidence=0.8,
                valid_from=_iso_at(date_str),
                current_state="active",
                first_seen_at=_iso_at(date_str),
                last_seen_at=f"{date_str}T23:59:59+08:00",
                reinforcement_count=1,
                state_reason="briefing_decision",
                provenance_refs=_build_provenance(
                    date_str=date_str,
                    kind="briefing.decision",
                    source_path="daily_briefing.json",
                ),
            ),
        )

    for raw in meta.get("decisions", []):
        if isinstance(raw, dict):
            decision = str(raw.get("what", "")).strip()
            topic = str(raw.get("project", "")).strip() or "meta"
        else:
            decision = str(raw).strip()
            topic = "meta"
        if not decision:
            continue
        items.setdefault(
            decision,
            DecisionItem(
                id=_slug("decision", decision),
                decision_id=_slug("decision", decision),
                topic=topic,
                decision=decision,
                scope="project",
                effective_from=f"{date_str}T12:00:00+08:00",
                source_rank="declared",
                confidence=0.9,
                valid_from=_iso_at(date_str),
                current_state="active",
                first_seen_at=_iso_at(date_str),
                last_seen_at=f"{date_str}T23:59:59+08:00",
                reinforcement_count=1,
                state_reason="meta_decision",
                provenance_refs=_build_provenance(
                    date_str=date_str,
                    kind="meta.decision",
                    source_path=f"{date_str}.meta.json",
                ),
            ),
        )

    return list(items.values())


def _make_recent_events(meta: dict[str, Any], date_str: str) -> list[EventItem]:
    events: list[EventItem] = []
    for raw in meta.get("events", []):
        if not isinstance(raw, dict):
            continue
        event = Event.from_dict(raw)
        summary = event.summary.strip() or str(raw.get("summary", "")).strip()
        if not summary:
            continue
        time_label = event.time.strip() or str(raw.get("time", "")).strip()
        happened_at = event.valid_from or _iso_at(date_str, time_label or "00:00")
        events.append(
            EventItem(
                id=event.event_id or _slug("event", f"{date_str}_{summary}"),
                event_id=event.event_id or _slug("event", f"{date_str}_{summary}"),
                project=event.project.strip() or str(raw.get("project", "")).strip(),
                summary=summary,
                happened_at=happened_at,
                time_label=time_label,
                confidence=event.confidence_score or 0.8,
                source_rank="declared",
                valid_from=happened_at,
                valid_until=event.valid_until or happened_at,
                current_state=event.current_state or "past",
                provenance_refs=event.provenance_refs
                or _build_provenance(
                    date_str=date_str,
                    kind="meta.event",
                    scene_id=event.source_scene_id,
                    recording_id=event.source_recording_id,
                    source_path=f"{date_str}.meta.json",
                ),
            )
        )
    return events


def _today_state_from_scenes(scenes: list[dict[str, Any]]) -> TodayState:
    if not scenes:
        return TodayState(primary_mode="idle", confidence=0.2)

    summaries = " ".join(str(scene.get("summary", "")) for scene in scenes)
    primary_mode = "design" if any(word in summaries for word in ["OpenMy", "CLI", "设计", "代码"]) else "conversation"
    energy = "high" if len(scenes) >= 6 else "medium"
    if ROLE_RECOGNITION_ENABLED:
        interaction_load = "high" if len({scene.get("role", {}).get("addressed_to", "") for scene in scenes if scene.get("role", {}).get("addressed_to", "")}) >= 2 else "medium"
    else:
        interaction_load = "medium"

    top_words = []
    for scene in scenes:
        summary = str(scene.get("summary", "")).strip()
        if summary:
            top_words.append(summary[:20])

    return TodayState(
        primary_mode=primary_mode,
        energy=energy,
        time_pressure="medium",
        interaction_load=interaction_load,
        dominant_topics=top_words[:3],
        suggested_agent_posture="先给结论，再展开；避免长篇枚举。",
        confidence=0.7,
    )


def _append_update_log(data_root: Path, ctx: ActiveContext) -> None:
    log_path = data_root / "active_context_updates.jsonl"
    payload = {
        "time": ctx.generated_at,
        "context_seq": ctx.context_seq,
        "status_line": ctx.status_line,
        "open_loop_count": len(ctx.rolling_context.open_loops),
        "top_entities": [item.entity_id for item in ctx.rolling_context.entity_rollups[:3]],
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _merge_refs(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    merged: list[dict[str, Any]] = []
    for ref in [*existing, *incoming]:
        if not isinstance(ref, dict):
            continue
        key = (
            str(ref.get("date", "") or ""),
            str(ref.get("kind", "") or ""),
            str(ref.get("scene_id", "") or ""),
            str(ref.get("quote", "") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(ref)
    return merged


def _merge_loop(existing: OpenLoop, incoming: OpenLoop) -> OpenLoop:
    existing.first_seen_at = min(filter(None, [existing.first_seen_at, incoming.first_seen_at]), default="")
    existing.last_seen_at = max(filter(None, [existing.last_seen_at, incoming.last_seen_at]), default="")
    existing.reinforcement_count = max(existing.reinforcement_count, 1) + max(incoming.reinforcement_count, 1)
    existing.confidence = max(existing.confidence, incoming.confidence)
    existing.provenance_refs = _merge_refs(existing.provenance_refs, incoming.provenance_refs)
    if incoming.due_hint and not existing.due_hint:
        existing.due_hint = incoming.due_hint
    if incoming.valid_from and (not existing.valid_from or incoming.valid_from < existing.valid_from):
        existing.valid_from = incoming.valid_from
    if incoming.valid_until and (not existing.valid_until or incoming.valid_until > existing.valid_until):
        existing.valid_until = incoming.valid_until
    if incoming.current_state == "closed":
        existing.status = incoming.status
        existing.current_state = "closed"
        existing.valid_until = incoming.valid_until or existing.valid_until
        existing.state_reason = incoming.state_reason or existing.state_reason
    elif existing.current_state != "closed":
        adjudicated = adjudicate_temporal_state(
            status=existing.status,
            current_state="future" if existing.due_hint and existing.due_hint[:10] > (existing.last_seen_at[:10] or "") else existing.current_state,
            valid_from=existing.valid_from,
            valid_until=existing.valid_until,
            due_iso_date=existing.due_hint[:10] if re.match(r"^\d{4}-\d{2}-\d{2}$", existing.due_hint[:10]) else "",
            reference_date=existing.last_seen_at[:10] or incoming.last_seen_at[:10],
        )
        existing.current_state = adjudicated["state"]
        existing.state_reason = adjudicated["reason"]
    return existing


def _group_fact_conflicts(meta_payload: dict[str, Any], date_str: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in meta_payload.get("facts", []):
        if not isinstance(raw, dict):
            continue
        fact = Fact.from_dict(raw)
        content_basis = re.split(r"(?:改成|改为|切到|切成|是)", fact.content, maxsplit=1)[0].strip()
        basis = fact.topic if fact.topic and "默认" in fact.topic else content_basis or fact.topic or fact.fact_type or "fact"
        canonical = build_canonical_key("fact", basis)
        grouped[canonical].append(
            {
                "title": fact.topic or fact.content,
                "variant": fact.content,
                "date": date_str,
                "refs": fact.provenance_refs
                or _build_provenance(
                    date_str=date_str,
                    kind="fact",
                    scene_id=fact.source_scene_id,
                    recording_id=fact.source_recording_id,
                    quote=fact.evidence_quote,
                    source_path=f"{date_str}.meta.json",
                ),
            }
        )
    return grouped


def consolidate(data_root: Path, existing_context: ActiveContext | None = None) -> ActiveContext:
    """扫描所有日期数据，生成新的 ActiveContext。"""
    project_root = data_root.parent
    dates = _list_dates(project_root, data_root)
    ctx = ActiveContext()

    if existing_context:
        ctx.context_seq = existing_context.context_seq + 1
    else:
        ctx.context_seq = 1
    ctx.materialized_from_event_seq = ctx.context_seq
    ctx.generated_at = datetime.now().isoformat()

    ctx.stable_profile = StableProfile(
        identity=Identity(
            canonical_name="周瑟夫",
            preferred_name="周瑟夫",
            primary_language="zh-CN",
            timezone="Asia/Shanghai",
            roles=["solo_founder", "builder"],
        ),
        communication_contract=CommunicationContract(
            answer_language="zh-CN",
            answer_style="direct_compact",
            tone="plain",
            avoid=["long_bullet_lists", "empty_empathy", "english_syntax_chinese"],
            prefer=["short_paragraphs", "specific_recommendations"],
        ),
    )

    if not dates:
        ctx.status_line = "当前还没有可汇总的日数据。"
        _append_update_log(data_root, ctx)
        return ctx

    latest_date = dates[-1]
    latest_day = _parse_date(latest_date)

    addressed_date_hits: dict[str, set[str]] = defaultdict(set)
    addressed_counts_7d: Counter[str] = Counter()
    addressed_counts_30d: Counter[str] = Counter()
    addressed_topics: dict[str, list[str]] = defaultdict(list)
    all_projects: dict[str, dict[str, Any]] = {}
    all_loops: dict[str, OpenLoop] = {}
    all_decisions: dict[str, DecisionItem] = {}
    all_events: list[EventItem] = []
    all_metas_for_close: list[tuple[str, dict[str, Any]]] = []
    conflict_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    recent_changes: list[ChangeItem] = []
    scene_count_7d = 0
    coverage_days_30d = 0
    uncertain_count_7d = 0

    latest_scenes: list[dict[str, Any]] = []
    latest_briefing: dict[str, Any] = {}
    latest_meta: dict[str, Any] = {}

    for date_str in dates:
        day_date = _parse_date(date_str)
        delta_days = (latest_day - day_date).days
        paths = _resolve_paths(project_root, data_root, date_str)
        scenes_payload = _load_json(paths["scenes"])
        briefing_payload = _load_json(paths["briefing"])
        meta_payload = _load_json(paths["meta"])
        all_metas_for_close.append((date_str, meta_payload))
        scenes = scenes_payload.get("scenes", [])

        if date_str == latest_date:
            latest_scenes = scenes
            latest_briefing = briefing_payload
            latest_meta = meta_payload

        if delta_days <= 29 and scenes:
            coverage_days_30d += 1
        if delta_days <= 6:
            scene_count_7d += len(scenes)

        if ROLE_RECOGNITION_ENABLED:
            for scene in scenes:
                role = scene.get("role", {}) if isinstance(scene.get("role", {}), dict) else {}
                addressed_to = str(role.get("addressed_to", "")).strip()
                if not addressed_to:
                    continue

                addressed_date_hits[addressed_to].add(date_str)
                if delta_days <= 6:
                    addressed_counts_7d[addressed_to] += 1
                if delta_days <= 29:
                    addressed_counts_30d[addressed_to] += 1

                summary = str(scene.get("summary", "")).strip()
                if summary and summary not in addressed_topics[addressed_to]:
                    addressed_topics[addressed_to].append(summary)

                if delta_days <= 6 and bool(role.get("needs_review")):
                    uncertain_count_7d += 1

        for loop in _make_open_loops(briefing_payload, meta_payload, date_str):
            canonical = build_canonical_key("loop", loop.title)
            existing_loop = all_loops.get(canonical)
            if existing_loop is None:
                all_loops[canonical] = loop
            else:
                all_loops[canonical] = _merge_loop(existing_loop, loop)

        for decision in _make_decisions(briefing_payload, meta_payload, date_str):
            canonical = build_canonical_key("decision", decision.decision, decision.topic)
            if canonical not in all_decisions:
                all_decisions[canonical] = decision
            else:
                existing_decision = all_decisions[canonical]
                existing_decision.provenance_refs = _merge_refs(existing_decision.provenance_refs, decision.provenance_refs)
                existing_decision.last_seen_at = max(filter(None, [existing_decision.last_seen_at, decision.last_seen_at]), default=decision.last_seen_at)
                existing_decision.reinforcement_count = max(existing_decision.reinforcement_count, 1) + 1

        all_events.extend(_make_recent_events(meta_payload, date_str))
        for canonical, claims in _group_fact_conflicts(meta_payload, date_str).items():
            conflict_candidates[canonical].extend(claims)

        for project_title, snippets in _extract_projects(briefing_payload, meta_payload).items():
            if not project_title:
                continue
            all_projects[project_title] = {
                "title": project_title,
                "snippets": snippets,
                "last_touched_at": f"{date_str}T23:59:59+08:00",
                "valid_from": _iso_at(date_str),
                "provenance_refs": _build_provenance(
                    date_str=date_str,
                    kind="project.aggregate",
                    source_path=f"{date_str}.meta.json",
                ),
            }

        if delta_days <= 2:
            for decision in _make_decisions(briefing_payload, meta_payload, date_str):
                recent_changes.append(
                    ChangeItem(
                        change_id=_slug("chg", f"{date_str}_{decision.decision}"),
                        changed_at=f"{date_str}T23:59:59+08:00",
                        change_type="new_decision",
                        summary=decision.decision,
                        affected_ids=[decision.decision_id],
                        salience=decision.confidence,
                    )
                )

    # Fix D: 门槛从 >=2天 降到 >=1天，首次出现 confidence 0.5
    ctx.stable_profile.key_people_registry = [
        EntityRegistryCard(
            id=_slug("entity", name),
            entity_id=name,
            display_name=name,
            relation_type=_known_relation_type(name),
            aliases=[name],
            confidence=0.9 if len(date_hits) >= 2 else 0.5,
            source_rank="aggregate",
            last_seen_at=max(date_hits) + "T23:59:59+08:00",
        )
        for name, date_hits in sorted(addressed_date_hits.items())
        if len(date_hits) >= 1
    ]

    # Fix I: 用 done intents 自动关闭匹配的 open_loops
    _auto_close_loops(all_loops, all_metas_for_close)

    recent_conflicts: list[ConflictItem] = []
    for canonical, claims in conflict_candidates.items():
        variants = sorted({item["variant"] for item in claims if item.get("variant")})
        if len(variants) < 2:
            continue
        title = next((item["title"] for item in claims if item.get("title")), canonical)
        refs: list[dict[str, Any]] = []
        for item in claims:
            refs = _merge_refs(refs, item.get("refs", []))
        recent_conflicts.append(
            ConflictItem(
                id=_slug("conflict", canonical),
                conflict_id=_slug("conflict", canonical),
                canonical_key=canonical,
                title=title,
                conflict_type="fact_conflict",
                variants=variants,
                confidence=0.9,
                source_rank="aggregate",
                first_seen_at=min((item["date"] for item in claims), default=""),
                last_seen_at=max((item["date"] for item in claims), default=""),
                reinforcement_count=len(claims),
                current_state="active",
                state_reason="multi_day_conflict",
                provenance_refs=refs,
            )
        )

    # 项目去重 — 合并相似名、过滤一次性提及（映射表在 config.py）
    from openmy.config import PROJECT_MERGE_MAP
    filtered_projects: dict[str, Any] = {}
    for title, snippets in all_projects.items():
        merged = PROJECT_MERGE_MAP.get(title, title)
        if merged is None:
            continue  # 过滤掉非项目
        if merged in filtered_projects:
            # 合并 snippets
            existing = filtered_projects[merged]
            existing["snippets"]["snippets"].extend(snippets["snippets"])
            if snippets["last_touched_at"] > existing["snippets"]["last_touched_at"]:
                existing["snippets"]["last_touched_at"] = snippets["last_touched_at"]
        else:
            filtered_projects[merged] = {"snippets": snippets}

    ctx.rolling_context = RollingContext(
        recent_changes=recent_changes[:10],
        active_projects=[
            ProjectCard(
                id=_slug("project", title),
                project_id=_slug("project", title),
                title=title,
                status="active",
                priority="high" if "OpenMy" in title else "medium",
                current_goal=info["snippets"]["snippets"][0] if info["snippets"]["snippets"] else title,
                next_actions=[
                    loop.title
                    for loop in all_loops.values()
                    if title in loop.title or title == "OpenMy"
                ][:3],
                blockers=[],
                momentum="steady",
                last_touched_at=info["snippets"]["last_touched_at"],
                confidence=0.85,
                source_rank="aggregate",
                valid_from=info["snippets"].get("valid_from", ""),
                current_state="active",
                provenance_refs=info["snippets"].get("provenance_refs", []),
            )
            for title, info in sorted(filtered_projects.items())
        ],
        open_loops=_filter_stale_loops(sorted(all_loops.values(), key=lambda item: item.title)),
        recent_decisions=sorted(
            all_decisions.values(),
            key=lambda item: item.effective_from,
            reverse=True,
        )[:10],
        recent_events=sorted(
            all_events,
            key=lambda item: item.happened_at,
            reverse=True,
        )[:15],
        recent_conflicts=sorted(
            recent_conflicts,
            key=lambda item: item.last_seen_at,
            reverse=True,
        )[:10],
        belief_shifts=[],
        entity_rollups=[
            EntityRollup(
                entity_id=name,
                interaction_7d_count=addressed_counts_7d[name],
                interaction_30d_count=addressed_counts_30d[name],
                last_interaction_at=max(addressed_date_hits[name]) + "T23:59:59+08:00",
                recent_topics=addressed_topics[name][:3],
            )
            for name, _count in addressed_counts_30d.most_common()
        ],
        topic_rollups=[],
    )

    latest_events = latest_briefing.get("key_events", [])
    if not latest_events:
        latest_events = [
            str(item.get("summary", "")).strip()
            for item in latest_meta.get("events", [])
            if isinstance(item, dict) and str(item.get("summary", "")).strip()
        ]

    latest_todos = list(latest_briefing.get("todos_open", []))
    if not latest_todos and isinstance(latest_meta.get("intents"), list):
        latest_todos = [
            Intent.from_dict(item).what.strip()
            for item in latest_meta.get("intents", [])
            if isinstance(item, dict) and should_generate_open_loop(Intent.from_dict(item))
        ]
    if not latest_todos:
        latest_todos = [
            str(item.get("task", "")).strip()
            for item in latest_meta.get("todos", [])
            if isinstance(item, dict) and str(item.get("task", "")).strip()
        ]

    ctx.core_memory = CoreMemory(
        focus_projects=[
            item
            for item in ctx.rolling_context.active_projects
            if item.confidence >= 0.8 and item.current_state == "active"
        ][:3],
        open_loops=[
            item
            for item in ctx.rolling_context.open_loops
            if item.confidence >= 0.75 and item.current_state in {"active", "future"}
        ][:5],
        active_decisions=[
            item
            for item in ctx.rolling_context.recent_decisions
            if item.current_state == "active"
        ][:5],
        key_people=[
            item
            for item in ctx.stable_profile.key_people_registry
            if item.confidence >= 0.8
        ][:5],
        current_focus=latest_events[:3] if latest_events else [],
    )

    unresolved_ratio_1d = 0.0
    if latest_scenes and ROLE_RECOGNITION_ENABLED:
        unresolved_count = sum(
            1
            for scene in latest_scenes
            if bool(scene.get("role", {}).get("needs_review"))
        )
        unresolved_ratio_1d = unresolved_count / len(latest_scenes)

    # 截断保护：today_focus 和 pending_followups 不超过 80 字
    def _truncate(text: str, limit: int = 80) -> str:
        if len(text) <= limit:
            return text
        first = re.split(r'[。！？!?]', text)[0]
        return (first[:limit] if first else text[:limit])

    latest_events = [_truncate(e) for e in latest_events]
    latest_todos = [_truncate(t) for t in latest_todos]

    ctx.realtime_context = RealtimeContext(
        today_focus=latest_events[:5],
        today_state=_today_state_from_scenes(latest_scenes),
        latest_scene_refs=[
            SceneRefDigest(
                scene_id=str(scene.get("scene_id", "")),
                time_range=f"{scene.get('time_start', '')}-{scene.get('time_end', '')}".strip("-"),
                summary=str(scene.get("summary", "")).strip() or str(scene.get("preview", "")).strip(),
            )
            for scene in latest_scenes[-5:]
        ],
        pending_followups_today=latest_todos[:5],
        ingestion_health=IngestionHealth(
            last_processed_date=latest_date,
            unresolved_scene_ratio_1d=round(unresolved_ratio_1d, 3),
            last_human_review_at=ctx.generated_at,
        ),
    )

    total_7d_interactions = sum(addressed_counts_7d.values()) or 1
    ctx.quality = QualityMetrics(
        coverage_days_30d=coverage_days_30d,
        scene_count_7d=scene_count_7d,
        human_confirmed_items_30d=0,
        uncertain_ratio_7d=round(uncertain_count_7d / total_7d_interactions, 3),
        stale_fields=[],
        last_human_review_at=ctx.generated_at,
    )

    top_projects = [item.title for item in ctx.rolling_context.active_projects[:2]]
    top_entities = [item.entity_id for item in ctx.rolling_context.entity_rollups[:2]]
    project_text = "、".join(top_projects) if top_projects else "日常事务"
    entity_text = "、".join(top_entities) if top_entities else "暂无"
    ctx.status_line = (
        f"最近{min(len(dates), 3)}天主要推进 {project_text}；"
        f"当前有 {len(ctx.rolling_context.open_loops)} 个待办未闭环；"
        f"高频互动对象是 {entity_text}。"
    )

    corrections = load_corrections(data_root)
    if corrections:
        ctx = apply_corrections(ctx, corrections)

    _append_update_log(data_root, ctx)
    return ctx
