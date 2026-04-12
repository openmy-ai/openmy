#!/usr/bin/env python3
"""Active Context 展示器 — 生成不同层级的文本视图。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openmy.services.context.active_context import ActiveContext


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _reference_date(ctx: ActiveContext) -> datetime.date:
    generated_date = None
    raw_generated = str(ctx.generated_at or "").strip()
    if raw_generated:
        try:
            generated_date = datetime.fromisoformat(raw_generated.replace("Z", "+00:00")).date()
        except ValueError:
            generated_date = None

    raw = str(ctx.realtime_context.ingestion_health.last_processed_date or "").strip()
    if raw:
        try:
            candidate = datetime.strptime(raw, "%Y-%m-%d").date()
            if generated_date is not None and candidate > generated_date:
                return generated_date
            return candidate
        except ValueError:
            pass
    if generated_date is not None:
        return generated_date
    return datetime.now().date()


def _aggregate_lines(review: dict, *, kind: str) -> list[str]:
    if not review:
        return []
    lines: list[str] = []
    summary = str(review.get("summary", "") or "").strip()
    if summary:
        lines.append(summary)
    if kind == "monthly":
        direction = str(review.get("direction", "") or "").strip()
        if direction:
            lines.append(f"接下来盯：{direction}")
        elif review.get("projects"):
            lines.append(f"主线：{'、'.join(review.get('projects', [])[:3])}")
    else:
        focus = str(review.get("next_week_focus", "") or "").strip()
        if focus:
            lines.append(f"接下来盯：{focus}")
        elif review.get("open_items"):
            lines.append(f"待处理：{'、'.join(review.get('open_items', [])[:3])}")
    return lines[:3]


def _unresolved_loops(ctx: ActiveContext):
    return [
        item
        for item in ctx.rolling_context.open_loops
        if item.status == "open" and item.current_state in {"", "active", "future"}
    ]


def render_level0(ctx: ActiveContext) -> str:
    """Level 0：极简摘要。"""
    top_changes = [item.summary for item in ctx.rolling_context.recent_changes[:2]]
    open_loops = _unresolved_loops(ctx)
    lines = [ctx.status_line]
    lines.append(f"当前未闭环事项：{len(open_loops)} 个")
    if top_changes:
        lines.append(f"最近变化：{'；'.join(top_changes)}")
    return "\n".join(line for line in lines if line.strip())


def render_level1(ctx: ActiveContext) -> str:
    """Level 1：压缩文本版。"""
    parts = ["当前状态", ctx.status_line, ""]

    identity = ctx.stable_profile.identity
    parts.extend(
        [
            "你是谁",
            f"- 名字：{identity.preferred_name or identity.canonical_name or '未设置'}",
            f"- 语言：{identity.primary_language}",
            f"- 时区：{identity.timezone}",
            "",
        ]
    )

    if ctx.rolling_context.active_projects:
        parts.append("最近项目")
        for item in ctx.rolling_context.active_projects[:5]:
            parts.append(f"- {item.title}：{item.current_goal}")
        parts.append("")

    open_loops = _unresolved_loops(ctx)
    if open_loops:
        parts.append("待处理")
        for item in open_loops[:10]:
            parts.append(f"- {item.title}")
        parts.append("")

    if ctx.rolling_context.recent_decisions:
        parts.append("最近决定")
        for item in ctx.rolling_context.recent_decisions[:5]:
            parts.append(f"- {item.decision}")
        parts.append("")

    parts.append("今天重点")
    if ctx.realtime_context.today_focus:
        for item in ctx.realtime_context.today_focus[:5]:
            parts.append(f"- {item}")
    else:
        parts.append("- 暂无")

    today_state = ctx.realtime_context.today_state
    if today_state.primary_mode:
        parts.extend(
            [
                "",
                "今天状态",
                f"- 当前模式：{today_state.primary_mode}",
            ]
        )
        if today_state.dominant_topics:
            parts.append(f"- 主要话题：{'、'.join(today_state.dominant_topics[:3])}")

    return "\n".join(parts).strip()


def render_compact_md(ctx: ActiveContext, data_root: Path | None = None) -> str:
    """Markdown 版压缩视图 — 用于 Agent 启动时无感注入。"""
    lines = [
        "# Active Context",
        "",
        "## 当前状态",
        ctx.status_line or "暂无",
        "",
    ]

    # 身份（Agent 需要知道用叫什么、说什么语言）
    identity = ctx.stable_profile.identity
    if identity.preferred_name or identity.canonical_name:
        name = identity.preferred_name or identity.canonical_name
        lines.append(f"用户：{name}（{identity.primary_language}，{identity.timezone}）")
        lines.append("")

    if data_root is not None:
        from openmy.services.aggregation import current_month_str, current_week_str

        reference_date = _reference_date(ctx)
        monthly_review = _read_json(data_root / "monthly" / f"{current_month_str(reference_date)}.json")
        weekly_review = _read_json(data_root / "weekly" / f"{current_week_str(reference_date)}.json")

        monthly_lines = _aggregate_lines(monthly_review, kind="monthly")
        if monthly_lines:
            lines.append("## 本月方向")
            lines.extend(monthly_lines)
            lines.append("")

        weekly_lines = _aggregate_lines(weekly_review, kind="weekly")
        if weekly_lines:
            lines.append("## 本周进展")
            lines.extend(weekly_lines)
            lines.append("")

    # 活跃项目
    if ctx.rolling_context.active_projects:
        lines.append("## 最近项目")
        for item in ctx.rolling_context.active_projects[:5]:
            lines.append(f"- {item.title}：{item.current_goal}")
        lines.append("")

    # 今天重点
    lines.append("## 今天重点")
    if ctx.realtime_context.today_focus:
        lines.extend([f"- {item}" for item in ctx.realtime_context.today_focus[:5]])
    else:
        lines.append("- 暂无")

    # 最近变化
    if ctx.rolling_context.recent_changes:
        lines.extend(["", "## 最近动态"])
        for item in ctx.rolling_context.recent_changes[:5]:
            lines.append(f"- {item.summary}")

    # 待处理
    open_loops = _unresolved_loops(ctx)
    if open_loops:
        lines.extend(["", "## 待处理"])
        lines.extend([f"- {item.title}" for item in open_loops[:10]])

    # 最近决定
    if ctx.rolling_context.recent_decisions:
        lines.extend(["", "## 最近决定"])
        lines.extend([f"- {item.decision}" for item in ctx.rolling_context.recent_decisions[:5]])

    return "\n".join(lines).strip() + "\n"
