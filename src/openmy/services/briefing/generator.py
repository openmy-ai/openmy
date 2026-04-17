#!/usr/bin/env python3
"""Daily Briefing 生成器 — 把一天的语音+屏幕数据变成 AI 可读的交接文档"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openmy.config import ROLE_RECOGNITION_ENABLED
from openmy.services.screen_recognition.settings import (
    ScreenContextSettings,
    load_screen_context_settings,
    screen_context_participation_enabled,
)
from openmy.services.scene_quality import annotate_scene_payload, scene_is_usable_for_downstream
from openmy.utils.time import iso_at, iso_now


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


def _sanitize_briefing_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    replacements = [
        ("今天大家", "今天我和其他人"),
        ("大家都", "我们都"),
        ("大家对", "我们对"),
        ("大家聊", "我和其他人聊"),
        ("大家", "我们"),
        ("有人说", "对方说"),
        ("有人提到", "对方提到"),
        ("有人在", "对方在"),
        ("有人", "对方"),
    ]
    for old, new in replacements:
        cleaned = cleaned.replace(old, new)
    return cleaned


def _get_screen_context_apps(client, date_str: str, time_start: str, time_end: str, *, data_root: Path | None = None) -> list[str]:
    """查询屏幕上下文服务，获取指定时间段使用的 App 列表。"""
    if not client:
        return []
    try:
        start_iso = iso_at(date_str, time_start, data_root=data_root, seconds=0)
        end_iso = iso_at(date_str, time_end, data_root=data_root, seconds=59)
        events = client.search_ocr(start_time=start_iso, end_time=end_iso, limit=50)
        apps = set()
        for event in events:
            if event.app_name and event.app_name not in ("loginwindow", "screencaptureui"):
                apps.add(event.app_name)
        return sorted(apps)
    except Exception:
        return []


def _get_screen_context_app_usage(client, date_str: str, *, data_root: Path | None = None) -> dict[str, float]:
    """用 activity_summary API 获取各 App 真实使用时长（分钟）。"""
    if not client:
        return {}
    try:
        start_iso = iso_at(date_str, "00:00", data_root=data_root, seconds=0)
        end_iso = iso_at(date_str, "23:59", data_root=data_root, seconds=59)
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
        # 降级：用 search_ocr 粗估（返回帧计数，非精确时长）
        events = client.search_ocr(start_time=start_iso, end_time=end_iso, limit=500)
        app_counts: Counter[str] = Counter()
        for event in events:
            if event.app_name and event.app_name not in ("loginwindow", "screencaptureui"):
                app_counts[event.app_name] += 1
        # 标记为帧计数而非分钟，使用负值区分
        return {app: -count for app, count in app_counts.most_common(10)}
    except Exception:
        return {}


def generate_briefing(scenes_path: Path, date_str: str, screen_client=None) -> DailyBriefing:
    """生成 Daily Briefing。"""
    data_root = None
    if (scenes_path.parent / "profile.json").exists():
        data_root = scenes_path.parent
    elif (scenes_path.parent.parent / "profile.json").exists():
        data_root = scenes_path.parent.parent

    briefing = DailyBriefing(date=date_str, generated_at=iso_now(data_root=data_root))
    if data_root:
        screen_settings = load_screen_context_settings(data_root=data_root)
    else:
        screen_settings = ScreenContextSettings()
        if "OPENMY_SCREEN_CONTEXT_ENABLED" in os.environ:
            screen_settings.enabled = os.environ["OPENMY_SCREEN_CONTEXT_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
        if "OPENMY_SCREEN_CONTEXT_MODE" in os.environ:
            screen_settings.participation_mode = os.environ["OPENMY_SCREEN_CONTEXT_MODE"].strip().lower() or screen_settings.participation_mode
            if screen_settings.participation_mode == "off":
                screen_settings.enabled = False
    screen_participation_enabled = screen_context_participation_enabled(screen_settings)

    if not scenes_path.exists():
        briefing.summary = f"{date_str} 没有语音数据"
        return briefing

    data = json.loads(scenes_path.read_text(encoding="utf-8"))
    scenes = [annotate_scene_payload(scene) for scene in data.get("scenes", []) if isinstance(scene, dict)]
    usable_scenes = [scene for scene in scenes if scene_is_usable_for_downstream(scene)]
    briefing.total_scenes = len(scenes)
    briefing.total_words = sum(len(scene.get("text", "")) for scene in usable_scenes)
    briefing.voice_hours = round(
        sum(_minutes_between(scene.get("time_start", ""), scene.get("time_end", "")) for scene in usable_scenes) / 60,
        1,
    )

    scene_has_screen_context = any(
        isinstance(scene.get("screen_context"), dict) and (
            scene.get("screen_context", {}).get("summary") or scene.get("screen_context", {}).get("primary_app")
        )
        for scene in usable_scenes
    )

    if scene_has_screen_context and screen_participation_enabled:
        briefing.screen_recognition_available = True

    if screen_client and screen_settings.participation_mode != "off":
        try:
            briefing.screen_recognition_available = screen_client.is_available()
            if briefing.screen_recognition_available:
                screen_participation_enabled = True
        except Exception:
            pass
    elif screen_settings.participation_mode == "off":
        briefing.screen_recognition_available = False

    period_scenes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scene in usable_scenes:
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
            raw_role = scene.get("role", {}) if isinstance(scene.get("role", {}), dict) else {}
            role = raw_role if ROLE_RECOGNITION_ENABLED or str(raw_role.get("source", "")).strip() == "human_confirmed" else {}
            addressed_to = role.get("addressed_to", "") if isinstance(role, dict) else ""
            screen_context = scene.get("screen_context", {}) if isinstance(scene.get("screen_context", {}), dict) else {}
            if addressed_to:
                addressed_people.append(addressed_to)
                if addressed_to not in people:
                    people[addressed_to] = PersonInteraction(name=addressed_to)
                people[addressed_to].scene_count += 1
                summary = _sanitize_briefing_text(scene.get("summary", ""))
                if summary and len(people[addressed_to].topics) < 5:
                    people[addressed_to].topics.append(summary)

            summary = _sanitize_briefing_text(scene.get("summary", ""))
            if summary:
                summaries.append(summary)

            if screen_participation_enabled:
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
        if screen_participation_enabled and scene_has_screen_context:
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
            provider_apps = _get_screen_context_apps(screen_client, date_str, start_time, end_time, data_root=data_root)
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

    # 从 scene summaries 里提取关键事件和待办
    # decisions 不再从 summary 关键词分桶，改由 enrich_briefing_from_meta() 从 meta.json 回灌
    time_block_texts = {block.summary for block in briefing.time_blocks}
    time_block_prefixes = {block.summary[:20] for block in briefing.time_blocks if len(block.summary) >= 20}
    seen_events: set[str] = set()
    for scene in usable_scenes:
        summary = _sanitize_briefing_text(scene.get("summary", ""))
        if not summary or summary in seen_events:
            continue
        seen_events.add(summary)
        # 跳过已经在 time_blocks 里完整出现的
        if summary in time_block_texts:
            continue
        # 跳过前 20 字和 time_block summary 重叠的
        if len(summary) >= 20 and summary[:20] in time_block_prefixes:
            continue
        if any(keyword in summary for keyword in ["需要", "要去", "要做", "要买", "要找", "记得", "别忘", "待处理", "待确认", "还没"]):
            briefing.todos_open.append(summary)
        else:
            briefing.key_events.append(summary)

    if screen_participation_enabled and briefing.screen_recognition_available:
        app_usage = _get_screen_context_app_usage(screen_client, date_str, data_root=data_root)
        for app, minutes in app_usage.items():
            if isinstance(minutes, (int, float)) and minutes > 0:
                if minutes >= 60:
                    briefing.work_sessions[app] = f"约{int(minutes // 60)}小时{int(minutes % 60)}分钟"
                else:
                    briefing.work_sessions[app] = f"约{int(minutes)}分钟"
            elif isinstance(minutes, (int, float)) and minutes < 0:
                # Negative = frame count from search_ocr fallback
                briefing.work_sessions[app] = f"{abs(int(minutes))}段截屏"
            else:
                briefing.work_sessions[app] = "<1分钟"

    if screen_participation_enabled and not briefing.work_sessions and briefing.screen_highlights:
        app_counts: Counter[str] = Counter()
        for scene in usable_scenes:
            screen_context = scene.get("screen_context", {}) if isinstance(scene.get("screen_context", {}), dict) else {}
            app_name = str(screen_context.get("primary_app", "")).strip()
            if app_name:
                app_counts[app_name] += 1
        for app, count in app_counts.most_common(5):
            briefing.work_sessions[app] = f"{count} 段场景"

    people_names = list(briefing.people_interaction_map.keys())
    active_periods = [block.period.split(" ")[0] for block in briefing.time_blocks] if briefing.time_blocks else []
    top_apps = list(briefing.work_sessions.keys())[:3] if briefing.work_sessions else []

    summary_parts: list[str] = []
    first_signal = ""
    if people_names:
        first_signal = "people"
        summary_parts.append(f"我跟 {'、'.join(people_names[:3])} 有互动")
    elif top_apps:
        first_signal = "apps"
        summary_parts.append(f"我主要用了 {'、'.join(top_apps)}")
    elif briefing.screen_highlights:
        first_signal = "screen"
        summary_parts.append(f"我在屏幕上主要在处理 {briefing.screen_highlights[0]}")
    elif briefing.time_blocks:
        first_signal = "time_block"
        summary_parts.append(briefing.time_blocks[0].summary)
    elif active_periods:
        first_signal = "periods"
        summary_parts.append(f"我活跃时段：{'、'.join(active_periods)}")

    if active_periods:
        period_summary = f"活跃时段：{'、'.join(active_periods)}"
        if period_summary not in summary_parts:
            summary_parts.append(period_summary)

    if briefing.screen_highlights and first_signal != "screen":
        highlight_summary = f"屏幕上主要在处理 {briefing.screen_highlights[0]}"
        if highlight_summary not in summary_parts:
            summary_parts.append(highlight_summary)
    elif top_apps and first_signal != "apps":
        app_summary = f"主要用了 {'、'.join(top_apps)}"
        if app_summary not in summary_parts:
            summary_parts.append(app_summary)

    briefing.summary = "。".join(summary_parts) + "。" if summary_parts else f"我在 {date_str} 的记录较少。"
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


def enrich_briefing_from_meta(briefing_path: Path, meta_path: Path) -> bool:
    """从 meta.json 回灌 intents/facts/role_hints 到已生成的 briefing（方案 B 后置回灌）。

    Returns True if briefing was updated, False if skipped.
    """
    if not briefing_path.exists() or not meta_path.exists():
        return False

    try:
        briefing = json.loads(briefing_path.read_text(encoding="utf-8"))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    changed = False

    # 1. intents[kind=decision] → briefing.decisions
    existing_decisions = set(briefing.get("decisions", []))
    for intent in meta.get("intents", []):
        if intent.get("kind") != "decision":
            continue
        what = str(intent.get("what", "")).strip()
        if what and what not in existing_decisions:
            briefing.setdefault("decisions", []).append(what)
            existing_decisions.add(what)
            changed = True

    # 2. intents[kind=action_item|commitment, status!=done] → briefing.todos_open
    existing_todos = set(briefing.get("todos_open", []))
    for intent in meta.get("intents", []):
        if intent.get("kind") not in ("action_item", "commitment"):
            continue
        if intent.get("status") in ("done", "closed", "cancelled", "abandoned", "rejected"):
            continue
        what = str(intent.get("what", "")).strip()
        if what and what not in existing_todos:
            briefing.setdefault("todos_open", []).append(what)
            existing_todos.add(what)
            changed = True

    # 3. facts → briefing.insights
    existing_insights = {
        str(i.get("content", "")).strip() if isinstance(i, dict) else str(i).strip()
        for i in briefing.get("insights", [])
    }
    for fact in meta.get("facts", []):
        content = str(fact.get("content", "")).strip()
        if content and content not in existing_insights:
            briefing.setdefault("insights", []).append({
                "topic": str(fact.get("topic", "")).strip(),
                "content": content,
            })
            existing_insights.add(content)
            changed = True

    # 4. role_hints (confidence ≥ 0.7) → briefing.people_interaction_map + time_blocks
    existing_people = set(briefing.get("people_interaction_map", {}).keys())
    for hint in meta.get("role_hints", []):
        confidence = hint.get("confidence", 0)
        if not isinstance(confidence, (int, float)) or confidence < 0.7:
            continue
        role = str(hint.get("role", "")).strip()
        if not role or role in ("自己", "未确定", "") or role in existing_people:
            continue
        briefing.setdefault("people_interaction_map", {})[role] = {
            "scene_count": 1,
            "topics": [str(hint.get("evidence", "")).strip()],
        }
        existing_people.add(role)
        changed = True

        # 回灌到对应 time_block 的 people_talked_to
        hint_time = str(hint.get("time", "")).strip()
        if hint_time:
            hint_period = _time_to_period(hint_time)
            for block in briefing.get("time_blocks", []):
                block_period = str(block.get("period", "")).split(" ")[0] if isinstance(block, dict) else ""
                if block_period == hint_period:
                    people_list = block.get("people_talked_to", [])
                    if role not in people_list:
                        people_list.append(role)
                        block["people_talked_to"] = people_list

    # 截断
    briefing["decisions"] = briefing.get("decisions", [])[:10]
    briefing["todos_open"] = briefing.get("todos_open", [])[:10]
    briefing["insights"] = briefing.get("insights", [])[:10]

    if changed:
        briefing_path.write_text(
            json.dumps(briefing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return changed
