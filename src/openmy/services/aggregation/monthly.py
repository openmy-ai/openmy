from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openmy.services.aggregation.weekly import (
    _dedupe,
    _read_json,
    current_month_str,
    current_week_str,
    week_output_path,
)
from openmy.utils.io import safe_write_json


def _today() -> date:
    return datetime.now().date()


def parse_month_str(month_str: str | None) -> tuple[str, date, date]:
    normalized = (month_str or current_month_str()).strip()
    try:
        year_str, month_value = normalized.split("-", 1)
        year = int(year_str)
        month = int(month_value)
    except Exception as exc:
        raise ValueError(f"Invalid month: {normalized}") from exc
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return normalized, start, end


def month_output_path(data_root: Path, month_str: str) -> Path:
    return data_root / "monthly" / f"{month_str}.json"


def weekly_keys_for_month(month_start: date, month_end: date) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    cursor = month_start
    while cursor <= month_end:
        key = current_week_str(cursor)
        if key not in seen:
            seen.add(key)
            keys.append(key)
        cursor += timedelta(days=1)
    return keys


def _synthesize_month_summary(*, week_count: int, projects: list[str], decisions: list[str], open_items: list[str]) -> str:
    if week_count == 0:
        return ""
    project_text = "、".join(projects[:3]) if projects else "现有事项"
    parts = [f"本月共整理 {week_count} 份周回顾，主线集中在{project_text}。"]
    if decisions:
        parts.append(f"已经定下来的方向包括：{'；'.join(decisions[:2])}。")
    if open_items:
        parts.append(f"还没收完的事主要有：{'；'.join(open_items[:2])}。")
    return "".join(parts[:3])


def generate_monthly_review(data_root: Path, month_str: str | None = None) -> dict[str, Any]:
    normalized_month, month_start, month_end = parse_month_str(month_str)
    weekly_reviews: list[dict[str, Any]] = []
    for week_key in weekly_keys_for_month(month_start, month_end):
        weekly = _read_json(week_output_path(data_root, week_key))
        if weekly:
            weekly_reviews.append(weekly)

    projects = _dedupe([item for weekly in weekly_reviews for item in weekly.get("projects", []) or []])
    key_decisions = _dedupe([item for weekly in weekly_reviews for item in weekly.get("decisions", []) or []])
    open_items = _dedupe([item for weekly in weekly_reviews for item in weekly.get("open_items", []) or []])
    summary = _synthesize_month_summary(
        week_count=len(weekly_reviews),
        projects=projects,
        decisions=key_decisions,
        open_items=open_items,
    )
    direction = "；".join(open_items[:3]) if open_items else ("；".join(projects[:3]) if projects else "")

    review = {
        "month": normalized_month,
        "summary": summary,
        "projects": projects,
        "key_decisions": key_decisions,
        "open_items": open_items,
        "direction": direction,
    }
    safe_write_json(month_output_path(data_root, normalized_month), review)
    return review
