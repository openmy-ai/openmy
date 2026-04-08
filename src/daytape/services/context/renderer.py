#!/usr/bin/env python3
"""Active Context 展示器 — 生成不同层级的文本视图。"""

from __future__ import annotations

from daytape.services.context.active_context import ActiveContext


def render_level0(ctx: ActiveContext) -> str:
    """Level 0：极简摘要。"""
    top_changes = [item.summary for item in ctx.rolling_context.recent_changes[:2]]
    lines = [ctx.status_line]
    lines.append(f"当前未闭环事项：{len(ctx.rolling_context.open_loops)} 个")
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

    if ctx.rolling_context.open_loops:
        parts.append("待处理")
        for item in ctx.rolling_context.open_loops[:10]:
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


def render_compact_md(ctx: ActiveContext) -> str:
    """Markdown 版压缩视图。"""
    lines = [
        "# Active Context",
        "",
        "## 当前状态",
        ctx.status_line or "暂无",
        "",
        "## 今天重点",
    ]

    if ctx.realtime_context.today_focus:
        lines.extend([f"- {item}" for item in ctx.realtime_context.today_focus[:5]])
    else:
        lines.append("- 暂无")

    if ctx.rolling_context.open_loops:
        lines.extend(["", "## 待处理"])
        lines.extend([f"- {item.title}" for item in ctx.rolling_context.open_loops[:10]])

    if ctx.rolling_context.recent_decisions:
        lines.extend(["", "## 最近决定"])
        lines.extend([f"- {item.decision}" for item in ctx.rolling_context.recent_decisions[:5]])

    return "\n".join(lines).strip() + "\n"
