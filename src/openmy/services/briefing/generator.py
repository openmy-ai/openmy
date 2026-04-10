#!/usr/bin/env python3
"""Daily Briefing 生成器 — 把一天的语音+屏幕数据变成 AI 可读的交接文档"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openmy.services.screen_recognition.settings import (
    load_screen_context_settings,
    screen_context_participation_enabled,
)


@dataclass
class TimeBlock:
    """一个时段的活动摘要"""

    period: str = ""
    summary: str = ""
    mode: str = "voice_only"
    apps_used: list[str] = field(default_factory=list)
    people_talked_to: list[str] = field(default_factory=list)
    scene_count: int = 0


@dataclass
class PersonInteraction:
    """与一个人的交互摘要"""

    name: str = ""
    scene_count: int = 0
    topics: list[str] = field(default_factory=list)


@dataclass
class DailyBriefing:
    """一天的完整交接文档"""

    date: str = ""
    generated_at: str = ""
    summary: str = ""
    time_blocks: list[TimeBlock] = field(default_factory=list)
    key_events: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    todos_open: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    people_interaction_map: dict[str, Any] = field(default_factory=dict)
    work_sessions: dict[str, str] = field(default_factory=dict)
    screen_highlights: list[str] = field(default_factory=list)
    completion_candidates: list[str] = field(default_factory=list)
    total_scenes: int = 0
    total_words: int = 0
    voice_hours: float = 0.0
    screen_recognition_available: bool = False


def _time_to_period(time_str: str) -> str:
    """把 HH:MM 归入时段。"""
    try:
        hour = int(time_str.split(":")[0])
    except (ValueError, IndexError):
        return "其他"

    if hour < 6:
        return "凌晨"
    if hour < 9:
        return "早上"
    if hour < 12:
        return "上午"
    if hour < 14:
        return "中午"
    if hour < 17:
        return "下午"
    if hour < 19:
        return "傍晚"
    if hour < 22:
        return "晚上"
    return "深夜"


def _time_range_for_period(period: str) -> str:
    """返回时段的时间范围文字。"""
    ranges = {
        "凌晨": "00:00-06:00",
        "早上": "06:00-09:00",
        "上午": "09:00-12:00",
        "中午": "12:00-14:00",
        "下午": "14:00-17:00",
        "傍晚": "17:00-19:00",
        "晚上": "19:00-22:00",
        "深夜": "22:00-24:00",
    }
    return ranges.get(period, "")


def _minutes_between(time_start: str, time_end: str) -> int:
    try:
        start = datetime.strptime(time_start, "%H:%M")
        end = datetime.strptime(time_end, "%H:%M")
    except ValueError:
        return 0
    minutes = int((end - start).total_seconds() // 60)
    return max(0, minutes)


def _get_screen_context_apps(client, date_str: str, time_start: str, time_end: str) -> list[str]:
    """查询屏幕上下文服务，获取指定时间段使用的 App 列表。"""
    if not client:
        return []
    try:
        start_iso = f"{date_str}T{time_start}:00+08:00"
        end_iso = f"{date_str}T{time_end}:59+08:00"
        events = client.search_ocr(start_time=start_iso, end_time=end_iso, limit=50)
        apps = set()
        for event in events:
            if event.app_name and event.app_name not in ("loginwindow", "screencaptureui"):
                apps.add(event.app_name)
        return sorted(apps)
    except Exception:
        return []


def _get_screen_context_app_usage(client, date_str: str) -> dict[str, float]:
    """用 activity_summary API 获取各 App 真实使用时长（分钟）。"""
    if not client:
        return {}
    try:
        start_iso = f"{date_str}T00:00:00+08:00"
        end_iso = f"{date_str}T23:59:59+08:00"
        # 优先用 activity_summary（精确时长）
        if hasattr(client, "activity_summary"):
            data = client.activity_summary(start_iso, end_iso)
            result: dict[str, float] = {}
            for app in data.get("apps", []):
                name = app.get("name", "")
                minutes = app.get("minutes", 0)
                if name and name not in ("loginwindow", "screencaptureui") and minutes > 0:
                    result[name] = round(minutes, 1)
            # 按时长排序，取前 10
            return dict(sorted(result.items(), key=lambda x: x[1], reverse=True)[:10])
        # 降级：用 search_ocr 粗估
        events = client.search_ocr(start_time=start_iso, end_time=end_iso, limit=500)
        app_counts: Counter[str] = Counter()
        for event in events:
            if event.app_name and event.app_name not in ("loginwindow", "screencaptureui"):
                app_counts[event.app_name] += 1
        return dict(app_counts.most_common(10))
    except Exception:
        return {}


def generate_briefing(scenes_path: Path, date_str: str, screen_client=None) -> DailyBriefing:
    """生成 Daily Briefing。"""
    briefing = DailyBriefing(date=date_str, generated_at=datetime.now().isoformat())
    screen_settings = load_screen_context_settings()
    screen_participation_enabled = screen_context_participation_enabled(screen_settings)

    if not scenes_path.exists():
        briefing.summary = f"{date_str} 没有语音数据"
        return briefing

    data = json.loads(scenes_path.read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])
    briefing.total_scenes = len(scenes)
    briefing.total_words = sum(len(scene.get("text", "")) for scene in scenes)
    briefing.voice_hours = round(
        sum(_minutes_between(scene.get("time_start", ""), scene.get("time_end", "")) for scene in scenes) / 60,
        1,
    )

    scene_has_screen_context = any(
        isinstance(scene.get("screen_context"), dict) and (
            scene.get("screen_context", {}).get("summary") or scene.get("screen_context", {}).get("primary_app")
        )
        for scene in scenes
    )

    if scene_has_screen_context:
        briefing.screen_recognition_available = True

    if screen_participation_enabled and screen_client:
        try:
            briefing.screen_recognition_available = screen_client.is_available()
        except Exception:
            pass

    period_scenes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scene in scenes:
        period_scenes[_time_to_period(scene.get("time_start", ""))].append(scene)

    people: dict[str, PersonInteraction] = {}
    period_order = ["凌晨", "早上", "上午", "中午", "下午", "傍晚", "晚上", "深夜", "其他"]
    for period in period_order:
        if period not in period_scenes:
            continue

        grouped_scenes = period_scenes[period]
        time_range = _time_range_for_period(period)
        addressed_people: list[str] = []
        summaries: list[str] = []

        for scene in grouped_scenes:
            role = scene.get("role", {})
            addressed_to = role.get("addressed_to", "")
            screen_context = scene.get("screen_context", {}) if isinstance(scene.get("screen_context", {}), dict) else {}
            if addressed_to:
                addressed_people.append(addressed_to)
                if addressed_to not in people:
                    people[addressed_to] = PersonInteraction(name=addressed_to)
                people[addressed_to].scene_count += 1
                summary = scene.get("summary", "")
                if summary and len(people[addressed_to].topics) < 5:
                    people[addressed_to].topics.append(summary)

            summary = scene.get("summary", "")
            if summary:
                summaries.append(summary)

            screen_summary = str(screen_context.get("summary", "")).strip()
            if screen_summary and screen_summary not in briefing.screen_highlights:
                briefing.screen_highlights.append(screen_summary)

            for candidate in screen_context.get("completion_candidates", []):
                if not isinstance(candidate, dict):
                    continue
                label = str(candidate.get("label", "") or candidate.get("kind", "")).strip()
                if label and label not in briefing.completion_candidates:
                    briefing.completion_candidates.append(label)

        apps: list[str] = []
        mode = "voice_only"
        if scene_has_screen_context:
            apps = sorted(
                {
                    str(scene.get("screen_context", {}).get("primary_app", "")).strip()
                    for scene in grouped_scenes
                    if isinstance(scene.get("screen_context"), dict)
                    and str(scene.get("screen_context", {}).get("primary_app", "")).strip()
                }
            )
            if apps:
                mode = "dual"
        if screen_participation_enabled and briefing.screen_recognition_available and time_range:
            start_time, end_time = time_range.split("-")
            provider_apps = _get_screen_context_apps(screen_client, date_str, start_time, end_time)
            apps = provider_apps or apps
            if apps:
                mode = "dual"

        summary_parts: list[str] = []
        if summaries:
            summary_parts.append(summaries[0])
            if len(summaries) > 1:
                summary_parts.append(f"等 {len(summaries)} 段对话")

        briefing.time_blocks.append(
            TimeBlock(
                period=f"{period} ({time_range})" if time_range else period,
                summary=" / ".join(summary_parts) if summary_parts else f"{len(grouped_scenes)} 段语音",
                mode=mode,
                apps_used=apps[:8],
                people_talked_to=sorted(set(addressed_people)),
                scene_count=len(grouped_scenes),
            )
        )

    for name, interaction in people.items():
        briefing.people_interaction_map[name] = {
            "scene_count": interaction.scene_count,
            "topics": interaction.topics[:5],
        }

    # 从 scene summaries 里提取关键事件、决策和待办
    # 规则：每个 summary 只进一个桶，优先级：决策 > 待办 > 关键事件
    # 避免和 time_blocks 里的 summary 重复
    time_block_texts = {block.summary for block in briefing.time_blocks}
    seen_events: set[str] = set()
    for scene in scenes:
        summary = scene.get("summary", "")
        if not summary or summary in seen_events:
            continue
        seen_events.add(summary)
        # 跳过已经在 time_blocks 里完整出现的
        if summary in time_block_texts:
            continue
        if any(keyword in summary for keyword in ["决定", "确定", "选择", "定了"]):
            briefing.decisions.append(summary)
        elif any(keyword in summary for keyword in ["需要", "要去", "要做", "要买", "要找", "记得", "别忘", "待处理", "待确认", "还没"]):
            briefing.todos_open.append(summary)
        else:
            briefing.key_events.append(summary)

    if screen_participation_enabled and briefing.screen_recognition_available:
        app_usage = _get_screen_context_app_usage(screen_client, date_str)
        for app, minutes in app_usage.items():
            if isinstance(minutes, (int, float)) and minutes > 0:
                if minutes >= 60:
                    briefing.work_sessions[app] = f"约{int(minutes // 60)}小时{int(minutes % 60)}分钟"
                else:
                    briefing.work_sessions[app] = f"约{int(minutes)}分钟"
            else:
                briefing.work_sessions[app] = "<1分钟"

    if not briefing.work_sessions and briefing.screen_highlights:
        app_counts: Counter[str] = Counter()
        for scene in scenes:
            screen_context = scene.get("screen_context", {}) if isinstance(scene.get("screen_context", {}), dict) else {}
            app_name = str(screen_context.get("primary_app", "")).strip()
            if app_name:
                app_counts[app_name] += 1
        for app, count in app_counts.most_common(5):
            briefing.work_sessions[app] = f"{count} 段场景"

    summary_parts: list[str] = []
    people_names = list(briefing.people_interaction_map.keys())
    if people_names:
        summary_parts.append(f"跟 {'、'.join(people_names[:3])} 有互动")
    if briefing.time_blocks:
        active_periods = [block.period.split(" ")[0] for block in briefing.time_blocks]
        summary_parts.append(f"活跃时段：{'、'.join(active_periods)}")
    if briefing.screen_highlights:
        summary_parts.append(f"屏幕上主要在处理 {briefing.screen_highlights[0]}")
    elif briefing.work_sessions:
        top_apps = list(briefing.work_sessions.keys())[:3]
        summary_parts.append(f"主要用了 {'、'.join(top_apps)}")

    briefing.summary = "。".join(summary_parts) + "。" if summary_parts else f"{date_str} 的记录"
    briefing.key_events = briefing.key_events[:10]
    briefing.decisions = briefing.decisions[:10]
    briefing.todos_open = briefing.todos_open[:10]
    briefing.screen_highlights = briefing.screen_highlights[:10]
    briefing.completion_candidates = briefing.completion_candidates[:10]
    return briefing


def save_briefing(briefing: DailyBriefing, output_path: Path) -> None:
    """保存 briefing 为 JSON。"""
    output_path.write_text(
        json.dumps(asdict(briefing), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
