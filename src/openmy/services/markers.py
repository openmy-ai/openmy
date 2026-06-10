"""归因式转写标记的单一解析来源（ADR-0001）。

转写层输出的封闭标记枚举在此定义，cleaner / scene_quality / distiller /
转写确认等全部消费方一律引用本模块，不得各自写正则——历史教训是
"改一处漏一处"（上次 usable 过滤就漏改了 show.py）。

标记格式（2026-06-10 经固定测试集对照验证后冻结，attribution_v2）：
- 行级来源前缀：``我：``（佩戴者）、``人：``（在场他人/通话对方）、``外：``（设备单向外放）
- 行内存疑：``[?词]``——模型拿不准但未放弃的内容
- 整词未识别：``[无法识别]``；整段无人声：``[无人声]``

畸形标记策略：未闭合的 ``[?`` 按行尾闭合处理（行余部分计为存疑）；
空 ``[?]`` 忽略。两者都不抛错、不吞正文。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

# ── 封闭枚举 ────────────────────────────────────────────────

SOURCE_WEARER = "wearer"
SOURCE_OTHERS = "others"
SOURCE_PLAYBACK = "playback"
SOURCE_UNMARKED = "unmarked"

ATTRIBUTION_PREFIXES: dict[str, str] = {
    "我：": SOURCE_WEARER,
    "人：": SOURCE_OTHERS,
    "外：": SOURCE_PLAYBACK,
}

UNRECOGNIZED_TAG = "[无法识别]"
NO_SPEECH_TAG = "[无人声]"

# [?内容]：不跨行、内容里不含另一个 [?；空 [?] 不算存疑
_UNCERTAIN_RE = re.compile(r"\[\?([^\[\]\n]+)\]")
# 未闭合的 [?……行尾（后面没有 ]）
_UNCERTAIN_OPEN_RE = re.compile(r"\[\?([^\[\]\n]+)$")
# 空 [?]
_UNCERTAIN_EMPTY_RE = re.compile(r"\[\?\]")


@dataclass
class UncertainSpan:
    """一处存疑转写：原词、所在行号（0 起）、该行净文本上下文。"""

    text: str
    line_index: int
    line_text: str
    raw: str  # 原始标记形态，如 "[?宿州]"；未闭合时为 "[?词"


def parse_attribution(line: str) -> tuple[str, str]:
    """解析一行的来源前缀，返回 (来源类别, 去前缀正文)。

    无前缀的行返回 (SOURCE_UNMARKED, 原文)——旧转写、其他 STT 引擎
    的输出都落在这里，下游对它们沿用原有行为。
    """
    stripped = line.lstrip()
    for prefix, source in ATTRIBUTION_PREFIXES.items():
        if stripped.startswith(prefix):
            return source, stripped[len(prefix):].lstrip()
    return SOURCE_UNMARKED, line


def strip_uncertain_marks(text: str, *, replace_with_content: bool = True) -> str:
    """剥离存疑括号。replace_with_content=True 时保留括号内的词，
    False 时把整个存疑片段替换为 [无法识别]（蒸馏前的确定性排除用）。"""
    replacement = r"\1" if replace_with_content else UNRECOGNIZED_TAG
    result = _UNCERTAIN_RE.sub(replacement, text)
    result = _UNCERTAIN_EMPTY_RE.sub("", result)
    # 未闭合：按行尾闭合处理
    lines = result.split("\n")
    for index, line in enumerate(lines):
        match = _UNCERTAIN_OPEN_RE.search(line)
        if match:
            tail = match.group(1) if replace_with_content else UNRECOGNIZED_TAG
            lines[index] = line[: match.start()] + tail
    return "\n".join(lines)


def strip_markers(text: str) -> str:
    """剥离全部归因前缀与存疑括号，返回净文本。

    [无法识别] / [无人声] 不剥——它们在旧格式中已存在，下游
    （乱码占比检测等）对它们有既定语义。
    """
    lines = []
    for line in text.split("\n"):
        _, body = parse_attribution(line)
        lines.append(body)
    return strip_uncertain_marks("\n".join(lines))


def iter_uncertain_spans(text: str) -> Iterator[UncertainSpan]:
    """枚举存疑片段（含未闭合形态），供转写确认环节提取待问项。"""
    for line_index, line in enumerate(text.split("\n")):
        _, body = parse_attribution(line)
        for match in _UNCERTAIN_RE.finditer(line):
            yield UncertainSpan(
                text=match.group(1),
                line_index=line_index,
                line_text=strip_uncertain_marks(body),
                raw=match.group(0),
            )
        open_match = _UNCERTAIN_OPEN_RE.search(line)
        if open_match:
            yield UncertainSpan(
                text=open_match.group(1),
                line_index=line_index,
                line_text=strip_uncertain_marks(body),
                raw=open_match.group(0),
            )


def has_attribution_markers(text: str) -> bool:
    """场景文本是否含归因前缀——蒸馏层"读标记还是猜"的门控开关。"""
    return any(
        parse_attribution(line)[0] != SOURCE_UNMARKED
        for line in text.split("\n")
    )
