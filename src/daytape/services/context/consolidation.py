#!/usr/bin/env python3
"""Active Context 汇总器 — 把日级数据提升为全局状态快照。"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from daytape.services.context.active_context import (
    ActiveContext,
    ChangeItem,
    CommunicationContract,
    DecisionItem,
    EntityRegistryCard,
    EntityRollup,
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
from daytape.services.context.corrections import apply_corrections, load_corrections


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
        "meta": project_root / f"{date_str}.meta.json",
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


def _extract_projects(briefing: dict[str, Any], meta: dict[str, Any]) -> dict[str, list[str]]:
    projects: dict[str, list[str]] = defaultdict(list)

    summary = str(briefing.get("summary", "")).strip()
    if "OpenMy" in summary or "DayTape" in summary:
        projects["OpenMy"].append(summary)

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

    for item in briefing.get("todos_open", []):
        title = str(item).strip()
        if not title:
            continue
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
                last_seen_at=f"{date_str}T23:59:59+08:00",
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
                last_seen_at=f"{date_str}T23:59:59+08:00",
            ),
        )

    return list(loops.values())


def _make_decisions(briefing: dict[str, Any], meta: dict[str, Any], date_str: str) -> list[DecisionItem]:
    items: dict[str, DecisionItem] = {}

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
            ),
        )

    return list(items.values())


def _today_state_from_scenes(scenes: list[dict[str, Any]]) -> TodayState:
    if not scenes:
        return TodayState(primary_mode="idle", confidence=0.2)

    summaries = " ".join(str(scene.get("summary", "")) for scene in scenes)
    primary_mode = "design" if any(word in summaries for word in ["OpenMy", "DayTape", "CLI", "设计", "代码"]) else "conversation"
    energy = "high" if len(scenes) >= 6 else "medium"
    interaction_load = "high" if len({scene.get("role", {}).get("addressed_to", "") for scene in scenes if scene.get("role", {}).get("addressed_to", "")}) >= 2 else "medium"

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
        scenes = scenes_payload.get("scenes", [])

        if date_str == latest_date:
            latest_scenes = scenes
            latest_briefing = briefing_payload
            latest_meta = meta_payload

        if delta_days <= 29 and scenes:
            coverage_days_30d += 1
        if delta_days <= 6:
            scene_count_7d += len(scenes)

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
            all_loops.setdefault(loop.title, loop)

        for decision in _make_decisions(briefing_payload, meta_payload, date_str):
            all_decisions.setdefault(decision.decision, decision)

        for project_title, snippets in _extract_projects(briefing_payload, meta_payload).items():
            if not project_title:
                continue
            all_projects[project_title] = {
                "title": project_title,
                "snippets": snippets,
                "last_touched_at": f"{date_str}T23:59:59+08:00",
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

    ctx.stable_profile.key_people_registry = [
        EntityRegistryCard(
            id=_slug("entity", name),
            entity_id=name,
            display_name=name,
            relation_type=_known_relation_type(name),
            aliases=[name],
            confidence=0.9,
            source_rank="aggregate",
            last_seen_at=max(addressed_date_hits[name]) + "T23:59:59+08:00",
        )
        for name, date_hits in sorted(addressed_date_hits.items())
        if len(date_hits) >= 2
    ]

    ctx.rolling_context = RollingContext(
        recent_changes=recent_changes[:10],
        active_projects=[
            ProjectCard(
                id=_slug("project", title),
                project_id=_slug("project", title),
                title=title,
                status="active",
                priority="high" if "OpenMy" in title or "DayTape" in title else "medium",
                current_goal=snippets["snippets"][0] if snippets["snippets"] else title,
                next_actions=[
                    loop.title
                    for loop in all_loops.values()
                    if title in loop.title or title == "OpenMy"
                ][:3],
                blockers=[],
                momentum="steady",
                last_touched_at=snippets["last_touched_at"],
                confidence=0.85,
                source_rank="aggregate",
            )
            for title, snippets in sorted(all_projects.items())
        ],
        open_loops=sorted(all_loops.values(), key=lambda item: item.title)[:10],
        recent_decisions=sorted(
            all_decisions.values(),
            key=lambda item: item.effective_from,
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
    if not latest_todos:
        latest_todos = [
            str(item.get("task", "")).strip()
            for item in latest_meta.get("todos", [])
            if isinstance(item, dict) and str(item.get("task", "")).strip()
        ]

    unresolved_ratio_1d = 0.0
    if latest_scenes:
        unresolved_count = sum(
            1
            for scene in latest_scenes
            if bool(scene.get("role", {}).get("needs_review"))
        )
        unresolved_ratio_1d = unresolved_count / len(latest_scenes)

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
