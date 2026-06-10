from __future__ import annotations

import re
from typing import Any

from openmy.services.markers import (
    SOURCE_PLAYBACK,
    parse_attribution,
    strip_markers,
)

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

NO_SPEECH_MARKERS = {"[无人声]", "[无声]", "[静音]", "[silence]"}


def _garbled_ratio(text: str) -> float:
    """计算 [无法识别] 占总行数的比例。

    在 strip_markers 后的净文本上判定——归因前缀不影响行数，
    [?词] 还原为净文本后不计为乱码。
    """
    cleaned = strip_markers(text)
    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    if not lines:
        return 0.0
    garbled = sum(1 for line in lines if "[无法识别]" in line)
    return garbled / len(lines)


def _has_repeated_ngram(text: str, n: int = 4, min_count: int = 4, density_threshold: float = 0.04) -> bool:
    """检测同一 n 字短语密度是否过高（歌词/口水话重复模式）。

    触发条件：最高频 n-gram 的总覆盖字符占比 > density_threshold（默认 4%），
    且该 n-gram 至少出现 min_count 次。

    在 strip_markers 后的净文本上计算——归因前缀和存疑括号的重复
    字符不应触发歌词检测。
    """
    chars = re.sub(r"\s+", "", strip_markers(text))
    total = len(chars)
    if total < n * min_count:
        return False
    counts: dict[str, int] = {}
    for i in range(total - n + 1):
        gram = chars[i : i + n]
        counts[gram] = counts.get(gram, 0) + 1
    if not counts:
        return False
    max_count = max(counts.values())
    if max_count < min_count:
        return False
    # 密度 = 最高频 n-gram 覆盖字符 / 总字符
    density = (max_count * n) / total
    return density > density_threshold


def _non_playback_text(text: str) -> str:
    """剥离 外： 归因行后的剩余文本，用于串台/助手回复检测。

    如果场景全是 外： 行，返回空字符串——不应触发串台检测。
    """
    lines = []
    for line in text.split("\n"):
        source, _ = parse_attribution(line)
        if source != SOURCE_PLAYBACK:
            lines.append(line)
    return "\n".join(lines)


def inspect_scene_text(text: str) -> dict[str, Any]:
    content = str(text or "").strip()
    flags: list[str] = []
    reasons: list[str] = []

    # 净文本（剥前缀和存疑括号）用于长度判定
    net_content = strip_markers(content)

    if not content:
        flags.append("empty")
        reasons.append("空内容")

    # [无人声] 检测
    if content in NO_SPEECH_MARKERS:
        flags.append("no_speech")
        reasons.append("整段只有无人声标记")

    # 串台/助手回复只对非外放行判定——外放行已归因，不应被标为串台
    non_pb = _non_playback_text(content)
    non_pb_stripped = non_pb.strip()
    non_pb_lowered = strip_markers(non_pb_stripped).lower()

    if "[助手回复]" in non_pb_stripped or "[疑似串台]" in non_pb_stripped:
        flags.append("assistant_reply")
        reasons.append("清洗阶段已经标过助手回复或串台")
    else:
        for phrase in ASSISTANT_REPLY_PHRASES:
            if phrase in non_pb_stripped:
                flags.append("assistant_reply")
                reasons.append(f"命中固定助手腔：{phrase}")
                break

    tech_hits = [marker for marker in TECH_TALK_MARKERS if marker in non_pb_lowered]
    if len(set(tech_hits)) >= 2 and len(non_pb_stripped) >= 40:
        flags.append("technical_crosstalk")
        reasons.append("同一段里连续出现多个技术讲解词，像外放内容")

    if len(net_content) <= 12 and LOW_SIGNAL_LATIN_RE.fullmatch(net_content):
        flags.append("low_signal_fragment")
        reasons.append("只有很短的拉丁字母碎片，信息量太低")

    # [无法识别] 密度检测——在净文本上判定
    garbled = _garbled_ratio(content)
    if garbled >= 0.4 and len(net_content) >= 40:
        flags.append("low_quality_garbled")
        reasons.append(f"[无法识别] 占比 {garbled:.0%}，转写质量过低")

    # 歌词重复模式检测——在净文本上判定
    if _has_repeated_ngram(content, n=4, min_count=4, density_threshold=0.04):
        flags.append("music_lyrics")
        reasons.append("检测到高频重复短语，疑似背景音乐歌词")

    suspicious = any(flag in {"assistant_reply", "technical_crosstalk"} for flag in flags)
    unusable_flags = {"no_speech", "low_signal_fragment", "empty", "low_quality_garbled", "music_lyrics"}
    usable = not suspicious and not (set(flags) & unusable_flags)

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
