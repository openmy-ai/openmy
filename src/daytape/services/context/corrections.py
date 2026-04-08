#!/usr/bin/env python3
"""Active Context 纠正事件系统."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from daytape.services.context.active_context import ActiveContext, EntityRegistryCard

CORRECTIONS_FILE = "corrections.jsonl"
_SPACE_RE = re.compile(r"\s+")


@dataclass
class CorrectionEvent:
    """一条追加式纠正事件."""

    correction_id: str
    created_at: str
    actor: str
    op: str
    target_type: str
    target_id: str
    payload: dict[str, Any]
    reason: str = ""


def _normalize(text: str) -> str:
    return _SPACE_RE.sub("", str(text or "")).strip().lower()


def _matches(query: str, *candidates: str) -> bool:
    normalized_query = _normalize(query)
    if not normalized_query:
        return False

    for candidate in candidates:
        normalized_candidate = _normalize(candidate)
        if normalized_candidate and normalized_query == normalized_candidate:
            return True

    if len(normalized_query) < 2:
        return False

    for candidate in candidates:
        normalized_candidate = _normalize(candidate)
        if not normalized_candidate:
            continue
        if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
            return True
    return False


def _dedupe_strings(items: list[str], limit: int = 5) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item).strip()
        key = _normalize(text)
        if not text or key in seen:
            continue
        seen.add(key)
        output.append(text)
        if len(output) >= limit:
            break
    return output


def _build_status_line(ctx: ActiveContext) -> str:
    top_projects = [item.title for item in ctx.rolling_context.active_projects[:2] if item.title]
    top_entities = [item.entity_id for item in ctx.rolling_context.entity_rollups[:2] if item.entity_id]
    project_text = "、".join(top_projects) if top_projects else "日常事务"
    entity_text = "、".join(top_entities) if top_entities else "暂无"
    return (
        f"最近主要推进 {project_text}；"
        f"当前有 {len(ctx.rolling_context.open_loops)} 个待办未闭环；"
        f"高频互动对象是 {entity_text}。"
    )


def create_correction_event(
    actor: str,
    op: str,
    target_type: str,
    target_id: str,
    payload: dict[str, Any] | None = None,
    reason: str = "",
) -> CorrectionEvent:
    """创建一条新的 correction 事件。"""
    now = datetime.now().astimezone()
    stamp = now.strftime("%Y%m%d_%H%M%S_%f")
    return CorrectionEvent(
        correction_id=f"corr_{stamp}",
        created_at=now.isoformat(),
        actor=actor,
        op=op,
        target_type=target_type,
        target_id=target_id,
        payload=payload or {},
        reason=reason,
    )


def append_correction(data_root: Path, event: CorrectionEvent) -> None:
    """追加一条 correction 到 data_root/corrections.jsonl。"""
    path = data_root / CORRECTIONS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


def load_corrections(data_root: Path) -> list[CorrectionEvent]:
    """读取所有 corrections，按时间排序。"""
    path = data_root / CORRECTIONS_FILE
    if not path.exists():
        return []

    events: list[CorrectionEvent] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            events.append(CorrectionEvent(**json.loads(line)))
        except Exception:
            continue
    return sorted(events, key=lambda item: item.created_at)


def _find_project_index(ctx: ActiveContext, query: str) -> int:
    for index, project in enumerate(ctx.rolling_context.active_projects):
        if _matches(query, project.project_id, project.id, project.title):
            return index
    return -1


def _find_entity(ctx: ActiveContext, query: str) -> EntityRegistryCard | None:
    for entity in ctx.stable_profile.key_people_registry:
        if _matches(query, entity.entity_id, entity.id, entity.display_name, *entity.aliases):
            return entity
    return None


def apply_corrections(ctx: ActiveContext, corrections: list[CorrectionEvent]) -> ActiveContext:
    """把 corrections 应用到 ActiveContext 上，返回修正后的版本。"""
    if not corrections:
        return ctx

    corrected = ActiveContext.from_dict(ctx.to_dict())

    for corr in corrections:
        if corr.op == "reject_loop":
            corrected.rolling_context.open_loops = [
                loop
                for loop in corrected.rolling_context.open_loops
                if not _matches(corr.target_id, loop.loop_id, loop.id, loop.title)
            ]
            continue

        if corr.op == "close_loop":
            corrected.rolling_context.open_loops = [
                loop
                for loop in corrected.rolling_context.open_loops
                if not _matches(corr.target_id, loop.loop_id, loop.id, loop.title)
            ]
            continue

        if corr.op == "keep_loop":
            for loop in corrected.rolling_context.open_loops:
                if _matches(corr.target_id, loop.loop_id, loop.id, loop.title):
                    loop.last_seen_at = corr.created_at
            continue

        if corr.op == "merge_project":
            source_index = _find_project_index(corrected, corr.target_id)
            if source_index < 0:
                continue

            merge_target = str(corr.payload.get("merge_into", "")).strip()
            merge_title = str(corr.payload.get("merge_into_title", "")).strip()
            source = corrected.rolling_context.active_projects[source_index]
            target_index = _find_project_index(corrected, merge_target or merge_title)

            if target_index >= 0 and target_index != source_index:
                target = corrected.rolling_context.active_projects[target_index]
                target.next_actions = _dedupe_strings(target.next_actions + source.next_actions, limit=8)
                target.blockers = _dedupe_strings(target.blockers + source.blockers, limit=5)
                if not target.current_goal and source.current_goal:
                    target.current_goal = source.current_goal
                if source.last_touched_at > target.last_touched_at:
                    target.last_touched_at = source.last_touched_at
                corrected.rolling_context.active_projects = [
                    project
                    for index, project in enumerate(corrected.rolling_context.active_projects)
                    if index != source_index
                ]
            else:
                source.title = merge_title or merge_target or source.title
            continue

        if corr.op == "reject_project":
            corrected.rolling_context.active_projects = [
                project
                for project in corrected.rolling_context.active_projects
                if not _matches(corr.target_id, project.project_id, project.id, project.title)
            ]
            continue

        if corr.op == "reject_decision":
            corrected.rolling_context.recent_decisions = [
                decision
                for decision in corrected.rolling_context.recent_decisions
                if not _matches(
                    corr.target_id,
                    decision.decision_id,
                    decision.id,
                    decision.decision,
                    decision.topic,
                )
            ]
            corrected.rolling_context.recent_changes = [
                change
                for change in corrected.rolling_context.recent_changes
                if not _matches(corr.target_id, change.change_id, change.summary, *change.affected_ids)
            ]
            continue

        if corr.op == "confirm_entity":
            entity = _find_entity(corrected, corr.target_id)
            override_name = str(corr.payload.get("display_name", "")).strip()
            if entity is None:
                entity = EntityRegistryCard(
                    id=corr.target_id,
                    entity_id=corr.target_id,
                    display_name=override_name or corr.target_id,
                    aliases=[corr.target_id],
                    confidence=1.0,
                    source_rank="human_confirmed",
                    last_confirmed_at=corr.created_at,
                )
                corrected.stable_profile.key_people_registry.append(entity)

            old_names = {entity.entity_id, entity.display_name, *entity.aliases}
            if "relation_type" in corr.payload:
                entity.relation_type = str(corr.payload.get("relation_type", "")).strip()
            if override_name:
                entity.display_name = override_name
                entity.entity_id = override_name
            entity.source_rank = "human_confirmed"
            entity.last_confirmed_at = corr.created_at
            entity.confidence = max(entity.confidence, 1.0)
            entity.aliases = _dedupe_strings(entity.aliases + [corr.target_id], limit=6)

            replacement_name = entity.display_name or entity.entity_id
            for rollup in corrected.rolling_context.entity_rollups:
                if any(_matches(name, rollup.entity_id) for name in old_names if name):
                    rollup.entity_id = replacement_name

    corrected.status_line = _build_status_line(corrected)
    return corrected
