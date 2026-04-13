from __future__ import annotations

import argparse
import re
from typing import Any

from rich import box
from rich.table import Table

from openmy.commands.common import DATA_ROOT, DATE_RE, console, write_json
from openmy.commands.show import (
    infer_scene_role_profile,
    read_scenes_payload,
    rebuild_scene_stats,
    resolve_day_paths,
)




def _upsert_word_correction(wrong: str, right: str):
    import json
    from pathlib import Path

    corrections_path = Path(__file__).resolve().parents[1] / "resources" / "corrections.json"
    corrections_path.parent.mkdir(parents=True, exist_ok=True)
    if corrections_path.exists():
        try:
            payload = json.loads(corrections_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"corrections": []}
    else:
        payload = {"corrections": []}
    corrections = payload.get("corrections", [])
    if not isinstance(corrections, list):
        corrections = []
    updated = False
    for item in corrections:
        if item.get("wrong") == wrong:
            item["right"] = right
            updated = True
            break
    if not updated:
        corrections.append({"wrong": wrong, "right": right})
    payload["corrections"] = corrections
    corrections_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return corrections_path

def _cmd_correct_typo(date_str: str, wrong: str, right: str) -> int:
    """纠正转写错词。"""
    paths = resolve_day_paths(date_str)
    transcript_path = paths["transcript"]
    if not transcript_path.exists():
        console.print(f"[red]❌ 找不到 {date_str} 的 transcript.md[/red]")
        return 1

    from openmy.services.cleaning.cleaner import sync_correction_to_vocab

    content = transcript_path.read_text(encoding="utf-8")
    replaced_count = content.count(wrong)
    transcript_path.write_text(content.replace(wrong, right), encoding="utf-8")

    corrections_path = _upsert_word_correction(wrong, right)
    sync_correction_to_vocab(wrong, right)

    console.print(f"[green]✅ 纠错完成[/green]: {wrong} → {right}，替换 {replaced_count} 处")
    console.print(f"[dim]词典: {corrections_path}[/dim]")
    return 0


def _load_context_snapshot():
    from openmy.services.context.active_context import ActiveContext

    ctx_path = DATA_ROOT / "active_context.json"
    if not ctx_path.exists():
        console.print("[red]❌ 还没有活动上下文快照，请先运行 `python3 -m openmy context`[/red]")
        return None
    return ActiveContext.load(ctx_path)


def _normalize_match_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip().lower()


def _score_match(query: str, *candidates: str) -> int:
    normalized_query = _normalize_match_text(query)
    if not normalized_query:
        return -1

    best = -1
    for candidate in candidates:
        normalized_candidate = _normalize_match_text(candidate)
        if not normalized_candidate:
            continue
        if normalized_query == normalized_candidate:
            return 1000 + len(normalized_candidate)
        if normalized_query in normalized_candidate:
            best = max(best, 500 - max(0, len(normalized_candidate) - len(normalized_query)))
        elif normalized_candidate in normalized_query:
            best = max(best, 100 - max(0, len(normalized_query) - len(normalized_candidate)))
    return best


def _resolve_item(items: list[Any], query: str, candidate_getter):
    best_item = None
    best_score = -1
    for item in items:
        score = _score_match(query, *candidate_getter(item))
        if score > best_score:
            best_score = score
            best_item = item
    if best_score < 0:
        return None
    return best_item


def _append_context_correction(
    op: str,
    target_type: str,
    target_id: str,
    payload: dict[str, Any] | None = None,
    reason: str = "",
) -> int:
    from openmy.services.context.corrections import append_correction, create_correction_event

    event = create_correction_event(
        actor="user",
        op=op,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        reason=reason,
    )
    append_correction(DATA_ROOT, event)
    return 0


def _cmd_correct_scene_role(date_str: str, scene_query: str, addressed_to: str) -> int:
    """人工修正某个场景的角色归因。"""
    scenes_path, data = read_scenes_payload(date_str)
    if not scenes_path.exists():
        console.print(f"[red]❌ 找不到 {date_str}/scenes.json，先运行 openmy roles {date_str}[/red]")
        return 1

    scenes = data.get("scenes", []) if isinstance(data.get("scenes", []), list) else []
    target = None
    for scene in scenes:
        if _score_match(
            scene_query,
            str(scene.get("scene_id", "")),
            str(scene.get("time_start", "")),
            str(scene.get("time_end", "")),
        ) >= 0:
            target = scene
            break

    if target is None:
        console.print(f"[red]❌ 没找到场景：{scene_query}[/red]")
        return 1

    scene_id = str(target.get("scene_id", "")).strip() or scene_query
    old_role = target.get("role", {}) if isinstance(target.get("role", {}), dict) else {}
    old_addressed_to = str(old_role.get("addressed_to", "")).strip() or "未识别"
    scene_type, scene_type_label = infer_scene_role_profile(addressed_to)

    updated_role = dict(old_role)
    updated_role.update(
        {
            "category": scene_type,
            "entity_id": addressed_to,
            "relation_label": addressed_to,
            "scene_type": scene_type,
            "scene_type_label": scene_type_label,
            "addressed_to": addressed_to,
            "confidence": 1.0,
            "evidence_chain": [f"人工修正为 {addressed_to}"],
            "source": "human_confirmed",
            "source_label": "你确认的",
            "evidence": f"人工修正为 {addressed_to}",
            "needs_review": False,
        }
    )
    target["role"] = updated_role
    data["stats"] = rebuild_scene_stats(data)
    write_json(scenes_path, data)

    from openmy.services.context.corrections import append_correction, create_correction_event

    event = create_correction_event(
        actor="user",
        op="confirm_scene_role",
        target_type="scene",
        target_id=f"{date_str}:{scene_id}",
        payload={
            "date": date_str,
            "scene_id": scene_id,
            "from": old_addressed_to,
            "to": addressed_to,
            "time_start": str(target.get("time_start", "")),
        },
    )
    append_correction(DATA_ROOT, event)

    console.print(
        f"[green]✅ 已修正场景角色[/green]: {date_str} {scene_id} "
        f"{old_addressed_to} → {addressed_to}"
    )
    console.print(
        "[dim]如需同步到日报，请重新运行 "
        f"`python3 -m openmy briefing {date_str}` 或完整 "
        f"`python3 -m openmy run {date_str} --skip-transcribe`。[/dim]"
    )
    return 0


def cmd_correct_list(_args: argparse.Namespace) -> int:
    """查看 correction 历史。"""
    from openmy.services.context.corrections import load_corrections

    corrections = load_corrections(DATA_ROOT)
    if not corrections:
        console.print("[dim]还没有任何修正记录[/dim]")
        return 0

    table = Table(title="📝 修正历史", box=box.ROUNDED)
    table.add_column("时间")
    table.add_column("操作")
    table.add_column("对象")
    table.add_column("原因")
    for event in corrections:
        if event.op == "merge_project":
            target = f"{event.payload.get('target_title', event.target_id)} → {event.payload.get('merge_into_title', event.payload.get('merge_into', ''))}"
        else:
            target = str(event.payload.get("target_title", event.target_id))
        table.add_row(event.created_at[:16], event.op, target, event.reason or "—")
    console.print(table)
    return 0


def cmd_correct(args: argparse.Namespace) -> int:
    """终端纠错。"""
    tokens = list(args.correct_args)
    if not tokens:
        console.print("[yellow]用法：openmy correct <date> <wrong> <right> 或 openmy correct <action> ...[/yellow]")
        return 1

    if DATE_RE.match(tokens[0]):
        if len(tokens) != 3:
            console.print("[red]❌ 旧纠错命令需要 3 个参数：<date> <wrong> <right>[/red]")
            return 1
        return _cmd_correct_typo(tokens[0], tokens[1], tokens[2])

    action = tokens[0]

    if action == "typo":
        if len(tokens) != 4:
            console.print("[red]❌ typo 用法：openmy correct typo <date> <wrong> <right>[/red]")
            return 1
        return _cmd_correct_typo(tokens[1], tokens[2], tokens[3])

    if action == "scene-role":
        if len(tokens) != 4:
            console.print("[red]❌ scene-role 用法：openmy correct scene-role <date> <scene_id|time> <addressed_to>[/red]")
            return 1
        return _cmd_correct_scene_role(tokens[1], tokens[2], tokens[3])

    if action == "list":
        return cmd_correct_list(args)

    ctx = _load_context_snapshot()
    if ctx is None:
        return 1

    if action == "close-loop":
        if len(tokens) != 2:
            console.print("[red]❌ close-loop 用法：openmy correct close-loop <title> [--status done|abandoned][/red]")
            return 1
        loop = _resolve_item(
            ctx.rolling_context.open_loops,
            tokens[1],
            lambda item: [item.loop_id, item.id, item.title],
        )
        if loop is None:
            console.print(f"[red]❌ 没找到待办：{tokens[1]}[/red]")
            return 1
        _append_context_correction(
            op="close_loop",
            target_type="loop",
            target_id=loop.loop_id or loop.id or loop.title,
            payload={"status": args.status, "target_title": loop.title},
        )
        console.print(f"[green]✅ 已关闭待办[/green]: {loop.title}")
        console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    if action == "reject-loop":
        if len(tokens) != 2:
            console.print("[red]❌ reject-loop 用法：openmy correct reject-loop <title>[/red]")
            return 1
        loop = _resolve_item(
            ctx.rolling_context.open_loops,
            tokens[1],
            lambda item: [item.loop_id, item.id, item.title],
        )
        if loop is None:
            console.print(f"[red]❌ 没找到待办：{tokens[1]}[/red]")
            return 1
        _append_context_correction(
            op="reject_loop",
            target_type="loop",
            target_id=loop.loop_id or loop.id or loop.title,
            payload={"target_title": loop.title},
        )
        console.print(f"[green]✅ 已排除误判待办[/green]: {loop.title}")
        console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    if action == "merge-project":
        if len(tokens) != 3:
            console.print("[red]❌ merge-project 用法：openmy correct merge-project <from> <into>[/red]")
            return 1
        from_project = _resolve_item(
            ctx.rolling_context.active_projects,
            tokens[1],
            lambda item: [item.project_id, item.id, item.title],
        )
        into_project = _resolve_item(
            ctx.rolling_context.active_projects,
            tokens[2],
            lambda item: [item.project_id, item.id, item.title],
        )
        if from_project is None or into_project is None:
            console.print("[red]❌ 找不到要合并的项目，请先运行 context 确认当前项目名[/red]")
            return 1
        _append_context_correction(
            op="merge_project",
            target_type="project",
            target_id=from_project.project_id or from_project.id or from_project.title,
            payload={
                "target_title": from_project.title,
                "merge_into": into_project.project_id or into_project.id or into_project.title,
                "merge_into_title": into_project.title,
            },
        )
        console.print(f"[green]✅ 已合并项目[/green]: {from_project.title} → {into_project.title}")
        console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    if action == "reject-project":
        if len(tokens) != 2:
            console.print("[red]❌ reject-project 用法：openmy correct reject-project <title>[/red]")
            return 1
        project = _resolve_item(
            ctx.rolling_context.active_projects,
            tokens[1],
            lambda item: [item.project_id, item.id, item.title],
        )
        if project is None:
            console.print(f"[red]❌ 没找到项目：{tokens[1]}[/red]")
            return 1
        _append_context_correction(
            op="reject_project",
            target_type="project",
            target_id=project.project_id or project.id or project.title,
            payload={"target_title": project.title},
        )
        console.print(f"[green]✅ 已排除误判项目[/green]: {project.title}")
        console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    if action == "reject-decision":
        if len(tokens) != 2:
            console.print("[red]❌ reject-decision 用法：openmy correct reject-decision <text>[/red]")
            return 1
        decision = _resolve_item(
            ctx.rolling_context.recent_decisions,
            tokens[1],
            lambda item: [item.decision_id, item.id, item.decision, item.topic],
        )
        if decision is None:
            console.print(f"[red]❌ 没找到决策：{tokens[1]}[/red]")
            return 1
        _append_context_correction(
            op="reject_decision",
            target_type="decision",
            target_id=decision.decision_id or decision.id or decision.decision,
            payload={"target_title": decision.decision},
        )
        console.print(f"[green]✅ 已排除非关键决策[/green]: {decision.decision}")
        console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    console.print(f"[red]❌ 不支持的纠错动作：{action}[/red]")
    return 1
