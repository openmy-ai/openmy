"""notify.py — macOS 桌面通知（零依赖，走 osascript）。

设备守护在后台无感处理录音，完成后用一条系统通知把价值递到用户面前：
"今天 X 小时录音整理好了，N 件事值得看"。非 macOS 或发送失败时静默返回，
守护进程绝不能因为通知发不出去而崩溃。
"""

from __future__ import annotations

import platform
import subprocess
from typing import Any


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _escape(text: str) -> str:
    """转义 AppleScript 双引号字符串里的特殊字符。"""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def send_notification(
    title: str,
    message: str,
    *,
    subtitle: str | None = None,
    sound: bool = False,
) -> bool:
    """发一条 macOS 通知。失败/非 macOS 返回 False，从不抛异常。"""
    if not _is_macos():
        return False
    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    if subtitle:
        script += f' subtitle "{_escape(subtitle)}"'
    if sound:
        script += ' sound name "Glass"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _voice_hours(briefing: dict[str, Any] | None) -> float | None:
    if not briefing:
        return None
    raw = briefing.get("voice_hours")
    try:
        hours = float(raw)
    except (TypeError, ValueError):
        return None
    return hours if hours >= 0.05 else None


def _worth_looking_count(briefing: dict[str, Any] | None) -> int:
    """"值得看"的条数 = 关键事件数（最稳的字段）。"""
    if not briefing:
        return 0
    events = briefing.get("key_events")
    return len(events) if isinstance(events, list) else 0


def build_completion_message(
    date: str, briefing: dict[str, Any] | None
) -> tuple[str, str]:
    """生成完成通知的 (title, message)。纯函数，便于单测。"""
    title = "OpenMy"
    hours = _voice_hours(briefing)
    count = _worth_looking_count(briefing)

    if hours:
        head = f"{date} {hours:.1f} 小时录音整理好了"
    else:
        head = f"{date} 录音整理好了"

    tail = f"，{count} 件事值得看" if count else ""
    return title, head + tail


def build_start_message(date: str, file_count: int) -> tuple[str, str]:
    return "OpenMy", f"检测到 DJI Mic，{file_count} 段新录音正在整理…"


def build_error_message(date: str, reason: str) -> tuple[str, str]:
    return "OpenMy", f"{date} 处理出错：{reason}"
