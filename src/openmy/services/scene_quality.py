from __future__ import annotations

import re
from typing import Any

ASSISTANT_REPLY_PHRASES = (
    "请提供您需要转写的音频文件",
    "我无法直接接收或播放音频文件",
    "请您将音频的内容",
    "我将严格按照您的要求进行处理",
)

TECH_TALK_MARKERS = (
    "postgres",
    "postgresql",
    "jsonb",
    "pubsub",
    "ted talk",
    "mysql",
    "sql",
    "数据源",
    "订阅",
    "同步",
    "演示",
)

LOW_SIGNAL_LATIN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 ._\-]{0,24}$")


def inspect_scene_text(text: str) -> dict[str, Any]:
    content = str(text or "").strip()
    lowered = content.lower()
    flags: list[str] = []
    reasons: list[str] = []

    if not content:
        flags.append("empty")
        reasons.append("空内容")

    if "[助手回复]" in content or "[疑似串台]" in content:
        flags.append("assistant_reply")
        reasons.append("清洗阶段已经标过助手回复或串台")
    else:
        for phrase in ASSISTANT_REPLY_PHRASES:
            if phrase in content:
                flags.append("assistant_reply")
                reasons.append(f"命中固定助手腔：{phrase}")
                break

    tech_hits = [marker for marker in TECH_TALK_MARKERS if marker in lowered]
    if len(set(tech_hits)) >= 2 and len(content) >= 40:
        flags.append("technical_crosstalk")
        reasons.append("同一段里连续出现多个技术讲解词，像外放内容")

    if len(content) <= 12 and LOW_SIGNAL_LATIN_RE.fullmatch(content):
        flags.append("low_signal_fragment")
        reasons.append("只有很短的拉丁字母碎片，信息量太低")

    suspicious = any(flag in {"assistant_reply", "technical_crosstalk"} for flag in flags)
    usable = not suspicious and "low_signal_fragment" not in flags and "empty" not in flags

    return {
        "quality_flags": flags,
        "suspicious_content": suspicious,
        "suspicious_reasons": reasons,
        "usable_for_downstream": usable,
    }


def annotate_scene_payload(scene: dict[str, Any]) -> dict[str, Any]:
    payload = dict(scene if isinstance(scene, dict) else {})
    quality = inspect_scene_text(str(payload.get("text", "") or ""))
    payload.update(quality)
    return payload


def scene_is_usable_for_downstream(scene: dict[str, Any]) -> bool:
    payload = annotate_scene_payload(scene)
    return bool(payload.get("usable_for_downstream", False))
