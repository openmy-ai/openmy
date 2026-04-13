from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from rich import box
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from openmy.commands.common import (
    AUDIO_TIME_RE,
    DATE_IN_FILENAME_RE,
    DATE_MD_RE,
    DATE_RE,
    ROLE_COLORS,
    console,
    get_screen_client,
    write_json,
)
from openmy.config import GEMINI_MODEL, get_llm_api_key
from openmy.services.feedback import (
    ask_feedback_opt_in,
    delete_feedback_data,
    load_settings as load_feedback_settings,
    load_telemetry,
    set_feedback_opt_in,
)
from openmy.services.query.context_query import query_context, render_query_result
from openmy.services.query.search_index import get_day_status_from_index, list_index_dates
from openmy.utils.paths import DATA_ROOT, LEGACY_ROOT


def _print_json(payload: Any) -> None:
    import sys

    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def find_all_dates() -> list[str]:
    """扫描所有可用日期。"""
    dates: set[str] = set()
    dates.update(list_index_dates(DATA_ROOT))
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
    from openmy.config import ROLE_RECOGNITION_ENABLED

    indexed = get_day_status_from_index(DATA_ROOT, date_str)
    if indexed is not None:
        return indexed

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
        if ROLE_RECOGNITION_ENABLED:
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

def read_scenes_payload(date_str: str) -> tuple[Path, dict[str, Any]]:
    paths = resolve_day_paths(date_str)
    return paths["scenes"], read_json(paths["scenes"], {})

def parse_audio_time(audio_path: Path) -> str:
    match = AUDIO_TIME_RE.match(audio_path.name)
    if not match:
        return "00:00"
    return f"{match.group(2)}:{match.group(3)}"

def infer_date_from_path(path: Path) -> str:
    """优先从父目录，再从文件名推断日期，支持 YYYY-MM-DD / YYYYMMDD。"""
    parent_name = path.parent.name
    if DATE_RE.match(parent_name):
        return parent_name

    match = DATE_IN_FILENAME_RE.search(path.name)
    if not match:
        return date.today().isoformat()
    if match.group("iso"):
        return match.group("iso")
    raw = match.group("compact")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

def infer_scene_role_profile(addressed_to: str) -> tuple[str, str]:
    """根据人工确认的对象名推导场景类别和展示标签。"""
    normalized = str(addressed_to or "").strip()
    lowered = normalized.lower()
    if not normalized:
        return ("uncertain", "不确定")
    if lowered in {"ai", "ai助手", "gpt", "chatgpt", "gemini", "claude", "codex"}:
        return ("ai", "跟AI说")
    if normalized in {"商家", "客服", "老板", "服务员"}:
        return ("merchant", "跟商家")
    if normalized in {"宠物", "小狗", "小猫"}:
        return ("pet", "跟宠物")
    if normalized in {"自己", "自言自语"}:
        return ("self", "自言自语")
    if normalized in {"未识别", "不确定"}:
        return ("uncertain", "不确定")
    return ("interpersonal", "跟人聊")

def rebuild_scene_stats(data: dict[str, Any]) -> dict[str, Any]:
    """根据 scenes 重新计算 role_distribution 和 needs_review_count。"""
    scenes = data.get("scenes", []) if isinstance(data.get("scenes", []), list) else []
    distribution: dict[str, int] = {}
    needs_review_count = 0
    for scene in scenes:
        role = scene.get("role", {}) if isinstance(scene.get("role", {}), dict) else {}
        addressed_to = str(role.get("addressed_to", "")).strip()
        label = addressed_to or str(role.get("scene_type_label", "")).strip() or "未识别"
        distribution[label] = distribution.get(label, 0) + 1
        if bool(role.get("needs_review")):
            needs_review_count += 1
    return {
        "total_scenes": len(scenes),
        "role_distribution": distribution,
        "needs_review_count": needs_review_count,
    }

def build_frozen_scene_stats(total_scenes: int) -> dict[str, Any]:
    return {
        "total_scenes": total_scenes,
        "role_distribution": {},
        "needs_review_count": 0,
        "role_recognition_status": "frozen",
    }

def freeze_scene_roles(data: dict[str, Any]) -> dict[str, Any]:
    scenes = data.get("scenes", []) if isinstance(data.get("scenes", []), list) else []
    frozen_role = {
        "category": "uncertain",
        "entity_id": "",
        "relation_label": "",
        "confidence": 0.0,
        "evidence_chain": [],
        "scene_type": "uncertain",
        "scene_type_label": "不确定",
        "addressed_to": "",
        "about": "",
        "source": "frozen",
        "source_label": "已冻结",
        "evidence": "角色识别已冻结",
        "needs_review": False,
    }
    for scene in scenes:
        role = scene.get("role", {}) if isinstance(scene.get("role", {}), dict) else {}
        if str(role.get("source", "")).strip() == "human_confirmed":
            continue
        scene["role"] = dict(frozen_role)
    data["stats"] = build_frozen_scene_stats(len(scenes))
    return data

def build_segmented_scenes_payload(markdown: str) -> dict[str, Any]:
    from openmy.services.segmentation.segmenter import build_scenes_payload, segment

    payload = build_scenes_payload(segment(markdown))
    return freeze_scene_roles(payload)

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
    """兼容旧命令名：当前只切场景，不再自动角色归因。"""
    date_str = args.date
    paths = resolve_day_paths(date_str)
    transcript_path = paths["transcript"]
    if not transcript_path.exists():
        console.print(f"[red]❌ 找不到 {date_str} 的清洗后文本，先运行 openmy clean {date_str}[/red]")
        return 1

    markdown = strip_document_header(transcript_path.read_text(encoding="utf-8"))

    with console.status("[bold cyan]🔪 场景切分中..."):
        result = build_segmented_scenes_payload(markdown)

    output_path = ensure_day_dir(date_str) / "scenes.json"
    write_json(output_path, result)

    stats = result["stats"]
    console.print(f"[green]✅ 场景切分完成[/green]: {stats['total_scenes']} 个场景")
    console.print("[dim]ℹ️ 自动角色识别已冻结，当前只生成场景，不做对象识别[/dim]")
    return 0

def cmd_distill(args: argparse.Namespace) -> int:
    """蒸馏摘要。"""
    date_str = args.date
    api_key = get_llm_api_key("distill")
    if not api_key:
        console.print(
            "[red]❌ 缺少 LLM provider key[/red]：请在当前项目根目录 `.env` 填 "
            "`GEMINI_API_KEY` 或 `OPENMY_LLM_API_KEY`。"
        )
        return 1

    scenes_path, data = read_scenes_payload(date_str)
    if not scenes_path.exists():
        console.print(f"[red]❌ 找不到 {date_str}/scenes.json，先运行 openmy roles {date_str}[/red]")
        return 1

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

def cmd_query(args: argparse.Namespace) -> int:
    result = query_context(
        DATA_ROOT,
        kind=args.kind,
        query=args.query or "",
        limit=args.limit,
        include_evidence=args.include_evidence,
    )
    if result.get("error"):
        if getattr(args, "json", False):
            _print_json(result)
        else:
            console.print(f"[red]❌ {result['error']}[/red]")
        return 1

    if getattr(args, "json", False):
        _print_json(result)
    else:
        console.print(Panel(render_query_result(result), title=f"🔎 {args.kind}", border_style="cyan"))
    return 0

def _render_review(title: str, payload: dict[str, Any], field_pairs: list[tuple[str, str]]) -> None:
    lines: list[str] = []
    summary = str(payload.get("summary", "") or "").strip()
    if summary:
        lines.append(summary)
        lines.append("")
    for field_name, label in field_pairs:
        value = payload.get(field_name)
        if isinstance(value, list) and value:
            lines.append(f"[bold]{label}[/bold]")
            lines.extend([f"- {item}" for item in value[:6]])
            lines.append("")
        elif isinstance(value, str) and value.strip():
            lines.append(f"[bold]{label}[/bold]")
            lines.append(value.strip())
            lines.append("")
    console.print(Panel(Markdown("\n".join(lines).strip() or "暂无内容"), title=title, border_style="cyan"))

def cmd_weekly(args: argparse.Namespace) -> int:
    from openmy.services.aggregation.weekly import current_week_str, generate_weekly_review

    week = getattr(args, "week", None) or current_week_str()
    review = generate_weekly_review(DATA_ROOT, week)
    _render_review(
        f"📅 本周回顾 · {review['week']}",
        review,
        [("projects", "主要项目"), ("wins", "推进了什么"), ("open_items", "还没收完"), ("next_week_focus", "下周先盯")],
    )
    return 0

def cmd_monthly(args: argparse.Namespace) -> int:
    from openmy.services.aggregation.monthly import generate_monthly_review
    from openmy.services.aggregation.weekly import current_month_str

    month = getattr(args, "month", None) or current_month_str()
    review = generate_monthly_review(DATA_ROOT, month)
    _render_review(
        f"🗓️ 本月回顾 · {review['month']}",
        review,
        [("projects", "主要项目"), ("key_decisions", "关键决定"), ("open_items", "还没收完"), ("direction", "接下来")],
    )
    return 0

def cmd_watch(args: argparse.Namespace) -> int:
    from openmy.services.watcher import watch

    watch(getattr(args, "directory", None))
    return 0

def cmd_feedback(args: argparse.Namespace) -> int:
    if getattr(args, "delete", False):
        delete_feedback_data()
        console.print("[green]✅ 本地反馈记录已经删掉了。[/green]")
        return 0

    if getattr(args, "show", False):
        settings = load_feedback_settings()
        telemetry = load_telemetry()
        console.print(
            Panel(
                "\n".join(
                    [
                        f"已同意：{'是' if settings.get('feedback_opt_in') else '否'}",
                        f"首次安装时间：{telemetry.get('first_install_time', '还没记')}",
                        f"首次成功处理时间：{telemetry.get('first_successful_processing_time', '还没记')}",
                        f"TTHW：{telemetry.get('tthw_seconds', '还没记')} 秒",
                        f"转写引擎：{telemetry.get('stt_provider', '还没记')}",
                        f"系统：{telemetry.get('os', '还没记')}",
                    ]
                ),
                title="本地反馈记录",
                border_style="cyan",
            )
        )
        return 0

    if getattr(args, "opt_in", False):
        set_feedback_opt_in(True)
        console.print("[green]✅ 已开启本地反馈记录。只记这台机器上的匿名使用指标，不上传。[/green]")
        return 0

    if getattr(args, "opt_out", False):
        set_feedback_opt_in(False)
        console.print("[green]✅ 已关闭本地反馈记录。旧数据还在，你随时可以删。[/green]")
        return 0

    settings = load_feedback_settings()
    if settings.get("feedback_opt_in") is None:
        decision = ask_feedback_opt_in()
        if decision is None:
            return 0
        set_feedback_opt_in(bool(decision))
        return 0

    if settings.get("feedback_opt_in"):
        console.print("[green]✅ 你已经开启了本地反馈记录。想看详情就运行 `openmy feedback --show`。[/green]")
    else:
        console.print("[yellow]ℹ️ 你现在没开本地反馈记录。想开启就运行 `openmy feedback --opt-in`。[/yellow]")
    return 0
