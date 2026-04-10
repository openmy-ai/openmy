#!/usr/bin/env python3
"""OpenMy — 个人上下文引擎 CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table


console = Console()
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_ROOT = ROOT_DIR / "data"
LEGACY_ROOT = ROOT_DIR

ROLE_COLORS = {
    "AI助手": "cyan",
    "商家": "yellow",
    "老婆": "magenta",
    "宠物": "green",
    "自己": "blue",
    "朋友": "bright_blue",
    "未识别": "dim",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
AUDIO_TIME_RE = re.compile(r".*?(\d{8})_(\d{2})(\d{2})(\d{2}).*")


def find_all_dates() -> list[str]:
    """扫描所有可用日期。"""
    dates: set[str] = set()
    if DATA_ROOT.exists():
        for child in DATA_ROOT.iterdir():
            if child.is_dir() and DATE_RE.match(child.name):
                dates.add(child.name)
    for path in LEGACY_ROOT.glob("*.md"):
        if path.name.endswith(".raw.md"):
            continue
        match = DATE_MD_RE.match(path.name)
        if match:
            dates.add(match.group(1))
    return sorted(dates, reverse=True)


def ensure_day_dir(date_str: str) -> Path:
    day_dir = DATA_ROOT / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def strip_document_header(markdown: str) -> str:
    if "---" not in markdown:
        return markdown
    parts = markdown.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return markdown


def get_date_status(date_str: str) -> dict[str, Any]:
    """获取某一天的处理阶段。"""
    day_dir = DATA_ROOT / date_str
    legacy = LEGACY_ROOT / f"{date_str}.md"

    status: dict[str, Any] = {
        "date": date_str,
        "has_transcript": (day_dir / "transcript.md").exists() or legacy.exists(),
        "has_raw": (day_dir / "transcript.raw.md").exists() or (LEGACY_ROOT / f"{date_str}.raw.md").exists(),
        "has_scenes": (day_dir / "scenes.json").exists() or (LEGACY_ROOT / f"{date_str}.scenes.json").exists(),
        "has_briefing": (day_dir / "daily_briefing.json").exists(),
        "word_count": 0,
        "scene_count": 0,
        "role_distribution": {},
    }

    transcript = day_dir / "transcript.md"
    if not transcript.exists():
        transcript = legacy
    if transcript.exists():
        content = transcript.read_text(encoding="utf-8")
        status["word_count"] = len(re.sub(r"\s+", "", content))

    scenes_path = day_dir / "scenes.json"
    if not scenes_path.exists():
        scenes_path = LEGACY_ROOT / f"{date_str}.scenes.json"
    if scenes_path.exists():
        data = read_json(scenes_path, {})
        status["scene_count"] = len(data.get("scenes", []))
        status["role_distribution"] = data.get("stats", {}).get("role_distribution", {})

    return status


def resolve_day_paths(date_str: str) -> dict[str, Path]:
    day_dir = DATA_ROOT / date_str
    if day_dir.exists():
        return {
            "dir": day_dir,
            "transcript": day_dir / "transcript.md",
            "raw": day_dir / "transcript.raw.md",
            "scenes": day_dir / "scenes.json",
            "briefing": day_dir / "daily_briefing.json",
        }

    return {
        "dir": day_dir,
        "transcript": LEGACY_ROOT / f"{date_str}.md",
        "raw": LEGACY_ROOT / f"{date_str}.raw.md",
        "scenes": LEGACY_ROOT / f"{date_str}.scenes.json",
        "briefing": day_dir / "daily_briefing.json",
    }


def stage_label(status: dict[str, Any]) -> str:
    if status["has_briefing"]:
        return "[green]✅ 完成[/green]"
    if status["has_scenes"]:
        return "[yellow]📊 已归因[/yellow]"
    if status["has_transcript"]:
        return "[blue]📝 已转写[/blue]"
    if status["has_raw"]:
        return "[dim]🎙️ 已录入[/dim]"
    return "[dim]❌ 无数据[/dim]"


def role_bar(distribution: dict[str, int], width: int = 20) -> str:
    total = sum(distribution.values())
    if total == 0:
        return "[dim]—[/dim]"

    parts: list[str] = []
    for role, count in sorted(distribution.items(), key=lambda item: -item[1]):
        color = ROLE_COLORS.get(role, "white")
        bar_len = max(1, round(count / total * width))
        parts.append(f"[{color}]{'█' * bar_len}[/{color}]")
    return "".join(parts)


def get_screen_client():
    try:
        from openmy.adapters.screen_recognition.client import ScreenRecognitionClient

        client = ScreenRecognitionClient()
        return client if client.is_available() else None
    except Exception:
        return None


def read_scenes_payload(date_str: str) -> tuple[Path, dict[str, Any]]:
    paths = resolve_day_paths(date_str)
    return paths["scenes"], read_json(paths["scenes"], {})


def parse_audio_time(audio_path: Path) -> str:
    match = AUDIO_TIME_RE.match(audio_path.name)
    if not match:
        return "00:00"
    return f"{match.group(2)}:{match.group(3)}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_correction(wrong: str, right: str, context: str = "") -> Path:
    from openmy.services.cleaning.cleaner import CORRECTIONS_FILE

    payload = {"_comment": "OpenMy 纠错词典", "corrections": []}
    if CORRECTIONS_FILE.exists():
        payload = read_json(CORRECTIONS_FILE, payload)
        payload.setdefault("_comment", "OpenMy 纠错词典")
        payload.setdefault("corrections", [])

    now = datetime.now().isoformat()
    today = date.today().isoformat()
    corrections = payload["corrections"]
    for item in corrections:
        if item.get("wrong") == wrong and item.get("right") == right:
            item["count"] = int(item.get("count", 0)) + 1
            item["context"] = context or item.get("context", "")
            item["last_updated"] = now
            write_json(CORRECTIONS_FILE, payload)
            return CORRECTIONS_FILE

    corrections.append(
        {
            "wrong": wrong,
            "right": right,
            "context": context,
            "count": 1,
            "first_seen": today,
            "last_updated": now,
        }
    )
    write_json(CORRECTIONS_FILE, payload)
    return CORRECTIONS_FILE


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

    corrections_path = upsert_correction(wrong, right)
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


def _resolve_item(items: list[Any], query: str, candidate_getter) -> Any | None:
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


def cmd_status(_args: argparse.Namespace) -> int:
    """列出所有日期及处理状态。"""
    dates = find_all_dates()
    if not dates:
        console.print("[dim]没有找到任何数据[/dim]")
        return 0

    table = Table(title="📅 OpenMy 数据总览", box=box.ROUNDED, show_lines=True)
    table.add_column("日期", style="bold")
    table.add_column("状态", justify="center")
    table.add_column("字数", justify="right")
    table.add_column("场景", justify="right")
    table.add_column("角色分布", min_width=20)

    for date_str in dates:
        status = get_date_status(date_str)
        table.add_row(
            date_str,
            stage_label(status),
            f"{status['word_count']:,}" if status["word_count"] else "—",
            str(status["scene_count"]) if status["scene_count"] else "—",
            role_bar(status["role_distribution"]),
        )

    console.print(table)
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    """终端查看某天概览。"""
    date_str = args.date
    status = get_date_status(date_str)
    if not status["has_transcript"]:
        console.print(f"[red]❌ {date_str} 没有数据[/red]")
        return 1

    paths = resolve_day_paths(date_str)
    if paths["briefing"].exists():
        briefing = read_json(paths["briefing"], {})
        console.print(
            Panel(
                briefing.get("summary", "无摘要"),
                title=f"📋 {date_str} 日报",
                border_style="magenta",
                padding=(1, 2),
            )
        )
        console.print()

    if paths["scenes"].exists():
        data = read_json(paths["scenes"], {})
        scenes = data.get("scenes", [])
        for scene in scenes:
            time_start = scene.get("time_start", "")
            role = scene.get("role", {})
            role_label = role.get("addressed_to", "") or role.get("scene_type_label", "未识别")
            color = ROLE_COLORS.get(role_label, "white")
            summary = scene.get("summary", "")
            preview = scene.get("preview") or scene.get("text", "")[:100]

            content_parts = []
            if summary:
                content_parts.append(summary)
            content_parts.append(f"[dim]{preview}[/dim]")

            console.print(
                Panel(
                    "\n".join(content_parts),
                    title=f"🕐 {time_start}  [{color}]{role_label}[/{color}]",
                    title_align="left",
                    border_style=color,
                    padding=(0, 1),
                )
            )

        dist = data.get("stats", {}).get("role_distribution", {})
        if dist:
            console.print()
            console.print("[bold]📊 角色分布[/bold]")
            total = sum(dist.values())
            max_bar = 30
            for role_name, count in sorted(dist.items(), key=lambda item: -item[1]):
                color = ROLE_COLORS.get(role_name, "white")
                bar_len = max(1, round(count / total * max_bar))
                pct = count / total * 100
                console.print(f"  [{color}]{'█' * bar_len}[/{color}] {role_name} {count}段 ({pct:.0f}%)")
    else:
        content = paths["transcript"].read_text(encoding="utf-8")
        console.print(Panel(Markdown(content[:2000]), title=f"📝 {date_str} 转写文本"))

    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """清洗转写文本。"""
    date_str = args.date
    paths = resolve_day_paths(date_str)
    raw_path = paths["raw"]
    if not raw_path.exists():
        console.print(f"[red]❌ 找不到 {date_str} 的原始转写[/red]")
        return 1

    from openmy.services.cleaning.cleaner import clean_text

    raw_text = raw_path.read_text(encoding="utf-8")
    with console.status("[bold green]🧹 清洗中..."):
        cleaned = clean_text(raw_text)

    output_path = ensure_day_dir(date_str) / "transcript.md"
    output_path.write_text(cleaned, encoding="utf-8")

    before = len(re.sub(r"\s+", "", raw_text))
    after = len(re.sub(r"\s+", "", cleaned))
    console.print(f"[green]✅ 清洗完成[/green]: {before:,} → {after:,} 字 (去除 {before - after:,} 字)")
    console.print(f"[dim]{output_path}[/dim]")
    return 0


def cmd_roles(args: argparse.Namespace) -> int:
    """切场景 + 角色归因。"""
    date_str = args.date
    paths = resolve_day_paths(date_str)
    transcript_path = paths["transcript"]
    if not transcript_path.exists():
        console.print(f"[red]❌ 找不到 {date_str} 的清洗后文本，先运行 openmy clean {date_str}[/red]")
        return 1

    from openmy.services.roles.resolver import resolve_roles, scenes_to_dict
    from openmy.services.segmentation.segmenter import segment

    markdown = strip_document_header(transcript_path.read_text(encoding="utf-8"))
    screen_client = get_screen_client()

    with console.status("[bold cyan]🏷️ 场景切分 + 角色归因..."):
        scenes = resolve_roles(segment(markdown), date_str=date_str, screen_client=screen_client)
        result = scenes_to_dict(scenes)

    output_path = ensure_day_dir(date_str) / "scenes.json"
    write_json(output_path, result)

    stats = result["stats"]
    console.print(f"[green]✅ 角色归因完成[/green]: {stats['total_scenes']} 个场景")
    for role_name, count in sorted(stats["role_distribution"].items(), key=lambda item: -item[1]):
        color = ROLE_COLORS.get(role_name, "white")
        console.print(f"  [{color}]■[/{color}] {role_name}: {count} 段")
    if stats["needs_review_count"]:
        console.print(f"  [yellow]⚠️ {stats['needs_review_count']} 段需要人工确认[/yellow]")
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    """蒸馏摘要。"""
    date_str = args.date
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        console.print("[red]❌ 缺少 GEMINI_API_KEY 环境变量[/red]")
        return 1

    scenes_path, data = read_scenes_payload(date_str)
    if not scenes_path.exists():
        console.print(f"[red]❌ 找不到 {date_str}/scenes.json，先运行 openmy roles {date_str}[/red]")
        return 1

    from openmy.config import GEMINI_MODEL
    from openmy.services.distillation.distiller import summarize_scene

    pending = [scene for scene in data.get("scenes", []) if not scene.get("summary")]
    if not pending:
        console.print(f"[green]✅ {date_str} 所有场景已有摘要，跳过[/green]")
        return 0

    console.print(f"[cyan]🧪 蒸馏 {len(pending)} 个场景...[/cyan]")
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("蒸馏中...", total=len(pending))
        for scene in data.get("scenes", []):
            if scene.get("summary"):
                continue
            text = scene.get("text", "").strip()
            scene["summary"] = summarize_scene(text, api_key, GEMINI_MODEL) if text else ""
            progress.advance(task)

    write_json(scenes_path, data)
    console.print(f"[green]✅ 蒸馏完成[/green]: {len(pending)} 个摘要已写入")
    return 0


def cmd_briefing(args: argparse.Namespace) -> int:
    """生成日报。"""
    date_str = args.date
    paths = resolve_day_paths(date_str)

    from openmy.services.briefing.generator import generate_briefing, save_briefing

    screen_client = get_screen_client()
    with console.status("[bold magenta]📋 生成日报中..."):
        briefing = generate_briefing(paths["scenes"], date_str, screen_client)
        output_path = ensure_day_dir(date_str) / "daily_briefing.json"
        save_briefing(briefing, output_path)

    console.print(f"[green]✅ 日报已生成[/green]: {output_path}")
    console.print(
        Panel(
            briefing.summary or f"{date_str} 的记录",
            title=f"📋 {date_str} 日报摘要",
            border_style="magenta",
            padding=(1, 2),
        )
    )
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """从 transcript 提取 intents / facts 结构。"""
    from openmy.services.extraction.extractor import run_extraction

    data = run_extraction(
        args.input_file,
        date=args.date,
        model=args.model,
        vault_path=args.vault_path,
        api_key=args.api_key,
        dry_run=args.dry_run,
    )
    if data is None:
        return 1

    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        console.print("[green]✅ 提取完成[/green]")
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


def cmd_context(args: argparse.Namespace) -> int:
    """生成/查看活动上下文。"""
    from openmy.services.context.active_context import ActiveContext
    from openmy.services.context.consolidation import consolidate
    from openmy.services.context.renderer import (
        render_compact_md,
        render_level0,
        render_level1,
    )

    ctx_path = DATA_ROOT / "active_context.json"
    compact_path = DATA_ROOT / "active_context.compact.md"
    existing = ActiveContext.load(ctx_path) if ctx_path.exists() else None

    with console.status("[bold cyan]🧠 正在生成活动上下文..."):
        ctx = consolidate(DATA_ROOT, existing_context=existing)
        ctx.save(ctx_path)

    if args.compact:
        markdown = render_compact_md(ctx)
        compact_path.write_text(markdown, encoding="utf-8")
        console.print(f"[green]✅ 已保存[/green]: {compact_path}")
        console.print(Markdown(markdown))
    elif args.level == 0:
        console.print(Panel(render_level0(ctx), title="🧠 Level 0", border_style="cyan"))
    else:
        console.print(Panel(render_level1(ctx), title="🧠 Active Context", border_style="cyan"))

    console.print(f"[dim]context_seq: {ctx.context_seq} | generated_at: {ctx.generated_at}[/dim]")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """给 Agent 用的统一入口。"""
    if args.recent:
        return cmd_context(argparse.Namespace(compact=False, level=0))

    if args.day:
        return cmd_view(argparse.Namespace(date=args.day))

    if args.reject_decision:
        return cmd_correct(argparse.Namespace(correct_args=["reject-decision", args.reject_decision], status="done"))

    if args.ingest:
        return cmd_run(
            argparse.Namespace(
                date=args.ingest,
                audio=args.audio,
                skip_transcribe=args.skip_transcribe,
            )
        )

    console.print("[red]❌ agent 入口需要指定动作[/red]")
    return 1


def transcribe_audio_files(date_str: str, audio_files: list[str]) -> int:
    """把本地音频文件转成 raw transcript。"""
    from openmy.services.ingest.audio_pipeline import transcribe_audio_files as run_ingest_pipeline

    try:
        output_path = run_ingest_pipeline(
            date_str=date_str,
            audio_files=audio_files,
            output_dir=ensure_day_dir(date_str),
        )
    except Exception as exc:
        console.print(f"[red]❌ 转写失败[/red]: {exc}")
        return 1

    console.print(f"[green]✅ 原始转写已生成[/green]: {output_path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """全流程：转写 → 清洗 → 角色 → 蒸馏 → 日报。"""
    date_str = args.date
    console.print(
        Panel(
            f"🎙️ OpenMy 全流程处理\n📅 日期: {date_str}",
            border_style="bright_blue",
        )
    )

    paths = resolve_day_paths(date_str)
    if args.audio and not args.skip_transcribe:
        console.print("[bold]Step 0: 🎙️ 转写音频[/bold]")
        result = transcribe_audio_files(date_str, args.audio)
        if result != 0:
            return result
        paths = resolve_day_paths(date_str)

    if args.skip_transcribe and not paths["raw"].exists() and not paths["transcript"].exists() and not paths["scenes"].exists():
        console.print(f"[red]❌ {date_str} 没有可复用的数据，至少需要 transcript/raw/scenes 之一[/red]")
        return 1

    if not args.audio and not args.skip_transcribe and not paths["raw"].exists() and not paths["transcript"].exists():
        console.print("[red]❌ 没有输入音频，也没有现成 raw/transcript 数据[/red]")
        return 1

    if not paths["transcript"].exists():
        console.print("\n[bold]🧹 清洗[/bold]")
        result = cmd_clean(args)
        if result != 0:
            console.print("[red]❌ 清洗失败，终止[/red]")
            return result
        paths = resolve_day_paths(date_str)
    else:
        console.print("\n[dim]⏭️ 跳过清洗：已存在 transcript.md[/dim]")

    scenes_data = read_json(paths["scenes"], {}) if paths["scenes"].exists() else {}
    if not paths["scenes"].exists():
        console.print("\n[bold]🔪 场景切分[/bold]")
        transcript_path = paths["transcript"]
        if not transcript_path.exists():
            console.print(f"[red]❌ 找不到 {date_str} 的转写文本[/red]")
            return 1

        from openmy.services.segmentation.segmenter import segment, build_scenes_payload

        markdown = strip_document_header(transcript_path.read_text(encoding="utf-8"))
        with console.status("[bold cyan]🔪 场景切分中..."):
            raw_scenes = segment(markdown)
            result = build_scenes_payload(raw_scenes)
            result["stats"] = {"total_scenes": len(raw_scenes)}

        output_path = ensure_day_dir(date_str) / "scenes.json"
        write_json(output_path, result)
        console.print(f"[green]✅ 场景切分完成[/green]: {len(raw_scenes)} 个场景")
        console.print("[dim]ℹ️ 角色归因已冻结，如需手动归因可运行 openmy roles {date_str}[/dim]")
        paths = resolve_day_paths(date_str)
        scenes_data = read_json(paths["scenes"], {})
    else:
        console.print("\n[dim]⏭️ 跳过场景切分：已存在 scenes.json[/dim]")

    # ── 角色识别（在蒸馏之前，给已有 scenes 补充 role 信息）──
    if os.getenv("GEMINI_API_KEY", "").strip():
        console.print("\n[bold]👥 角色识别[/bold]")
        try:
            from openmy.domain.models import SceneBlock
            from openmy.services.roles.resolver import tag_all_scenes, resolve_roles as _resolve_roles, scenes_to_dict

            # 读取已有 scenes，只做角色归因，不重新切分
            raw_scenes_list = scenes_data.get("scenes", [])
            scene_blocks = [SceneBlock.from_dict(s) if hasattr(SceneBlock, 'from_dict') else SceneBlock(
                scene_id=s.get('scene_id', ''),
                time_start=s.get('time_start', ''),
                time_end=s.get('time_end', ''),
                text=s.get('text', ''),
                preview=s.get('preview', ''),
            ) for s in raw_scenes_list]
            screen_client = get_screen_client()
            scene_blocks = _resolve_roles(scene_blocks, date_str=date_str, screen_client=screen_client)
            result = scenes_to_dict(scene_blocks)

            output_path = ensure_day_dir(date_str) / "scenes.json"
            write_json(output_path, result)
            paths = resolve_day_paths(date_str)
            scenes_data = read_json(paths["scenes"], {})
            console.print("[green]✅ 角色识别完成[/green]")
        except Exception as exc:
            console.print(f"[yellow]⚠️ 角色识别异常: {exc}，继续[/yellow]")
    else:
        console.print("\n[dim]⏭️ 跳过角色识别：缺少 GEMINI_API_KEY[/dim]")

    missing_summaries = [scene for scene in scenes_data.get("scenes", []) if not scene.get("summary")]
    if missing_summaries:
        if os.getenv("GEMINI_API_KEY", "").strip():
            console.print("\n[bold]🧪 蒸馏[/bold]")
            result = cmd_distill(args)
            if result != 0:
                console.print("[red]❌ 蒸馏失败，终止[/red]")
                return result
        else:
            console.print("\n[yellow]⏭️ 跳过蒸馏：缺少 GEMINI_API_KEY，继续生成基础日报[/yellow]")
    else:
        console.print("\n[dim]⏭️ 跳过蒸馏：场景摘要已齐全[/dim]")

    console.print("\n[bold]📋 日报[/bold]")
    result = cmd_briefing(args)
    if result != 0:
        console.print("[red]❌ 日报生成失败，终止[/red]")
        return result

    # ── 结构化提取（intents + facts）──
    if os.getenv("GEMINI_API_KEY", "").strip() and paths["transcript"].exists():
        console.print("\n[bold]🔍 提取[/bold]")
        try:
            from openmy.services.extraction.extractor import run_extraction
            from openmy.config import GEMINI_MODEL as _extract_model
            run_extraction(
                str(paths["transcript"]),
                date=date_str,
                model=_extract_model,
            )
            console.print("[green]✅ 提取完成[/green]")
        except Exception as exc:
            console.print(f"[yellow]⚠️ 提取异常: {exc}，继续[/yellow]")
    else:
        console.print("\n[dim]⏭️ 跳过提取：缺少 API key 或转写文件[/dim]")

    # ── 聚合 active_context ──
    console.print("\n[bold]🧠 聚合上下文[/bold]")
    try:
        from openmy.services.context.consolidation import consolidate
        data_root = ensure_day_dir(date_str).parent
        consolidate(data_root)
        console.print("[green]✅ active_context 已更新[/green]")
    except Exception as exc:
        console.print(f"[yellow]⚠️ 聚合异常: {exc}，继续[/yellow]")

    console.print(
        Panel(
            f"[green]✅ {date_str} 处理完成！[/green]\n运行 [bold]openmy view {date_str}[/bold] 查看结果",
            border_style="green",
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openmy",
        description="🎙️ OpenMy — 个人上下文引擎",
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    sub.add_parser("status", help="列出所有日期及处理状态")

    p_view = sub.add_parser("view", help="终端查看某天的概览")
    p_view.add_argument("date", help="日期 YYYY-MM-DD")

    p_clean = sub.add_parser("clean", help="清洗转写文本")
    p_clean.add_argument("date", help="日期 YYYY-MM-DD")

    p_roles = sub.add_parser("roles", help="切场景 + 角色归因")
    p_roles.add_argument("date", help="日期 YYYY-MM-DD")

    p_distill = sub.add_parser("distill", help="蒸馏摘要（需要 GEMINI_API_KEY）")
    p_distill.add_argument("date", help="日期 YYYY-MM-DD")

    p_brief = sub.add_parser("briefing", help="生成日报")
    p_brief.add_argument("date", help="日期 YYYY-MM-DD")

    p_extract = sub.add_parser("extract", help="从转写中提取 intents / facts")
    p_extract.add_argument("input_file", help="清洗后的 Markdown 文件路径")
    p_extract.add_argument("--date", help="日期 YYYY-MM-DD，默认从文件名推断")
    p_extract.add_argument("--model", default="gemini-3.1-flash-lite-preview", help="Gemini 模型")
    p_extract.add_argument("--vault-path", help="Obsidian Vault 路径")
    p_extract.add_argument("--api-key", help="Gemini API key")
    p_extract.add_argument("--dry-run", action="store_true", help="只打印提取结果，不写入文件")

    p_run = sub.add_parser("run", help="全流程处理")
    p_run.add_argument("date", help="日期 YYYY-MM-DD")
    p_run.add_argument("--audio", nargs="+", help="音频文件路径")
    p_run.add_argument("--skip-transcribe", action="store_true", help="跳过转写（使用已有数据）")

    p_correct = sub.add_parser("correct", help="纠正转写或活动上下文")
    p_correct.add_argument("correct_args", nargs="*", help="纠错参数")
    p_correct.add_argument(
        "--status",
        default="done",
        choices=["done", "abandoned"],
        help="close-loop 的关闭状态",
    )

    p_context = sub.add_parser("context", help="生成/查看活动上下文")
    p_context.add_argument("--compact", action="store_true", help="输出 Markdown 压缩版")
    p_context.add_argument("--level", type=int, default=1, choices=[0, 1], help="输出层级 (0=极简, 1=完整)")

    p_agent = sub.add_parser("agent", help="给 Agent 调用的统一入口")
    agent_mode = p_agent.add_mutually_exclusive_group(required=True)
    agent_mode.add_argument("--recent", action="store_true", help="读取最近整体状态")
    agent_mode.add_argument("--day", help="查看某天结果 YYYY-MM-DD")
    agent_mode.add_argument("--ingest", help="处理某天输入 YYYY-MM-DD")
    agent_mode.add_argument("--reject-decision", dest="reject_decision", help="排除一条不重要的决策")
    p_agent.add_argument("--audio", nargs="+", help="给 --ingest 使用的音频文件路径")
    p_agent.add_argument("--skip-transcribe", action="store_true", help="给 --ingest 使用：复用已有数据")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "agent": cmd_agent,
        "briefing": cmd_briefing,
        "clean": cmd_clean,
        "context": cmd_context,
        "correct": cmd_correct,
        "distill": cmd_distill,
        "extract": cmd_extract,
        "roles": cmd_roles,
        "run": cmd_run,
        "status": cmd_status,
        "view": cmd_view,
    }

    handler = commands.get(args.command)
    if not handler:
        console.print(f"[yellow]命令 '{args.command}' 尚未实现[/yellow]")
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]已中断[/yellow]")
        return 130
    except Exception:
        console.print_exception(show_locals=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
