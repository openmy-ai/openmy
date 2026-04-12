from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openmy.utils.io import safe_write_json

WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")
PROJECT_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9._+-]{2,}\b")

PROJECT_STOPWORDS = {
    "Google",
    "Chrome",
    "Codex",
    "Telegram",
    "Safari",
    "Raycast",
    "OpenAI",
    "Obsidian",
    "Notion",
    "Antigravity",
}


def _today() -> date:
    return datetime.now().date()


def current_week_str(reference_date: date | None = None) -> str:
    target = reference_date or _today()
    iso_year, iso_week, _ = target.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def current_month_str(reference_date: date | None = None) -> str:
    target = reference_date or _today()
    return target.strftime("%Y-%m")


def parse_week_str(week_str: str | None) -> tuple[str, date, date]:
    normalized = (week_str or current_week_str()).strip()
    match = WEEK_RE.match(normalized)
    if not match:
        raise ValueError(f"Invalid ISO week: {normalized}")
    iso_year = int(match.group(1))
    iso_week = int(match.group(2))
    start = date.fromisocalendar(iso_year, iso_week, 1)
    end = date.fromisocalendar(iso_year, iso_week, 7)
    return normalized, start, end


def week_output_path(data_root: Path, week_str: str) -> Path:
    return data_root / "weekly" / f"{week_str}.json"


def list_week_dates(week_start: date, week_end: date) -> list[date]:
    days: list[date] = []
    cursor = week_start
    while cursor <= week_end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for raw in items:
        text = str(raw or "").strip()
        if not text:
            continue
        key = re.sub(r"\s+", "", text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(text)
    return merged


def _project_candidates_from_text(text: str) -> list[str]:
    candidates: list[str] = []
    cleaned = str(text or "").strip()
    if not cleaned:
        return candidates
    if "：" in cleaned:
        head = cleaned.split("：", 1)[0].strip()
        if 1 <= len(head) <= 24:
            candidates.append(head)
    if ":" in cleaned:
        head = cleaned.split(":", 1)[0].strip()
        if 1 <= len(head) <= 24:
            candidates.append(head)
    for token in PROJECT_TOKEN_RE.findall(cleaned):
        if token in PROJECT_STOPWORDS:
            continue
        candidates.append(token)
    return candidates


def _collect_projects(briefings: list[dict[str, Any]]) -> list[str]:
    items: list[str] = []
    for briefing in briefings:
        for field in ("summary",):
            items.extend(_project_candidates_from_text(str(briefing.get(field, "") or "")))
        for list_field in ("key_events", "decisions", "todos_open", "insights"):
            for entry in briefing.get(list_field, []) or []:
                items.extend(_project_candidates_from_text(str(entry or "")))
    filtered = [item for item in _dedupe(items) if len(item) <= 32]
    return filtered[:6]


def _synthesize_summary(*, included_days: int, projects: list[str], wins: list[str], challenges: list[str], open_items: list[str]) -> str:
    if included_days == 0:
        return ""
    project_text = "、".join(projects[:3]) if projects else "现有事项"
    parts = [f"本周共整理 {included_days} 天记录，主要围绕{project_text}推进。"]
    if wins:
        parts.append(f"已经往前推的事主要是：{'；'.join(wins[:2])}。")
    if open_items:
        parts.append(f"接下来还要盯：{'；'.join(open_items[:2])}。")
    elif challenges:
        parts.append(f"卡点主要是：{'；'.join(challenges[:2])}。")
    return "".join(parts[:3])


def generate_weekly_review(data_root: Path, week_str: str | None = None) -> dict[str, Any]:
    normalized_week, week_start, week_end = parse_week_str(week_str)
    briefings: list[dict[str, Any]] = []
    for day in list_week_dates(week_start, week_end):
        briefing = _read_json(data_root / day.isoformat() / "daily_briefing.json")
        if briefing:
            briefings.append(briefing)

    wins = _dedupe([item for briefing in briefings for item in briefing.get("key_events", []) or []])
    challenges = _dedupe([item for briefing in briefings for item in briefing.get("insights", []) or []])
    open_items = _dedupe([item for briefing in briefings for item in briefing.get("todos_open", []) or []])
    decisions = _dedupe([item for briefing in briefings for item in briefing.get("decisions", []) or []])
    projects = _collect_projects(briefings)
    summary = _synthesize_summary(
        included_days=len(briefings),
        projects=projects,
        wins=wins,
        challenges=challenges,
        open_items=open_items,
    )
    next_week_focus = "；".join(open_items[:3]) if open_items else ("；".join(challenges[:2]) if challenges else "")

    review = {
        "week": normalized_week,
        "date_range": f"{week_start.isoformat()} ~ {week_end.isoformat()}",
        "summary": summary,
        "projects": projects,
        "wins": wins,
        "challenges": challenges,
        "open_items": open_items,
        "decisions": decisions,
        "next_week_focus": next_week_focus,
    }
    safe_write_json(week_output_path(data_root, normalized_week), review)
    return review
