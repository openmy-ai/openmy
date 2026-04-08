#!/usr/bin/env python3
"""DayTape — 个人上下文引擎 CLI."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from rich import box
from rich.console import Console
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


def get_date_status(date: str) -> dict:
    """获取某一天的处理阶段。"""
    day_dir = DATA_ROOT / date
    legacy = LEGACY_ROOT / f"{date}.md"

    status = {
        "date": date,
        "has_transcript": (day_dir / "transcript.md").exists() or legacy.exists(),
        "has_raw": (day_dir / "transcript.raw.md").exists() or (LEGACY_ROOT / f"{date}.raw.md").exists(),
        "has_scenes": (day_dir / "scenes.json").exists() or (LEGACY_ROOT / f"{date}.scenes.json").exists(),
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
        scenes_path = LEGACY_ROOT / f"{date}.scenes.json"
    if scenes_path.exists():
        try:
            data = json.loads(scenes_path.read_text(encoding="utf-8"))
            status["scene_count"] = len(data.get("scenes", []))
            status["role_distribution"] = data.get("stats", {}).get("role_distribution", {})
        except Exception:
            pass

    return status


def stage_label(status: dict) -> str:
    if status["has_briefing"]:
        return "[green]✅ 完成[/green]"
    if status["has_scenes"]:
        return "[yellow]📊 已归因[/yellow]"
    if status["has_transcript"]:
        return "[blue]📝 已转写[/blue]"
    if status["has_raw"]:
        return "[dim]🎙️ 已录入[/dim]"
    return "[dim]❌ 无数据[/dim]"


def role_bar(distribution: dict, width: int = 20) -> str:
    total = sum(distribution.values())
    if total == 0:
        return "[dim]—[/dim]"

    parts: list[str] = []
    for role, count in sorted(distribution.items(), key=lambda item: -item[1]):
        color = ROLE_COLORS.get(role, "white")
        bar_len = max(1, round(count / total * width))
        parts.append(f"[{color}]{'█' * bar_len}[/{color}]")
    return "".join(parts)


def cmd_status(_args: argparse.Namespace) -> int:
    """列出所有日期及处理状态。"""
    dates = find_all_dates()
    if not dates:
        console.print("[dim]没有找到任何数据[/dim]")
        return 0

    table = Table(title="📅 DayTape 数据总览", box=box.ROUNDED, show_lines=True)
    table.add_column("日期", style="bold")
    table.add_column("状态", justify="center")
    table.add_column("字数", justify="right")
    table.add_column("场景", justify="right")
    table.add_column("角色分布", min_width=20)

    for date in dates:
        status = get_date_status(date)
        table.add_row(
            date,
            stage_label(status),
            f"{status['word_count']:,}" if status["word_count"] else "—",
            str(status["scene_count"]) if status["scene_count"] else "—",
            role_bar(status["role_distribution"]),
        )

    console.print(table)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daytape",
        description="🎙️ DayTape — 个人上下文引擎",
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

    p_run = sub.add_parser("run", help="全流程处理")
    p_run.add_argument("date", help="日期 YYYY-MM-DD")
    p_run.add_argument("--audio", nargs="+", help="音频文件路径")
    p_run.add_argument("--skip-transcribe", action="store_true", help="跳过转写（使用已有 raw）")

    p_correct = sub.add_parser("correct", help="纠正转写错词")
    p_correct.add_argument("date", help="日期 YYYY-MM-DD")
    p_correct.add_argument("wrong", help="错误写法")
    p_correct.add_argument("right", help="正确写法")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "status": cmd_status,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    console.print(f"[yellow]命令 '{args.command}' 尚未实现[/yellow]")
    return 1
