from __future__ import annotations

import argparse
from pathlib import Path

from openmy.commands.common import DATA_ROOT, _upsert_project_env, console, doc_url
from openmy.utils.errors import FriendlyCliError


def cmd_screen(args: argparse.Namespace) -> int:
    from openmy.services.screen_recognition.capture import (
        is_capture_supported,
        read_status,
        run_capture_loop,
        start_capture_daemon,
        stop_capture_daemon,
    )
    from openmy.services.screen_recognition.settings import (
        load_screen_context_settings,
        save_screen_context_settings,
    )

    action = str(getattr(args, "action", "") or "").strip().lower()
    settings = load_screen_context_settings(data_root=DATA_ROOT)

    if action == "on":
        settings.enabled = True
        if settings.participation_mode == "off":
            settings.participation_mode = "summary_only"
        save_screen_context_settings(settings, data_root=DATA_ROOT)
        _upsert_project_env("SCREEN_RECOGNITION_ENABLED", "true")
        if not is_capture_supported():
            raise FriendlyCliError(
                "当前机器不支持内置屏幕识别。",
                code="screen_capture_unsupported",
                fix="这块先在 macOS（苹果系统）上用；别的系统先跳过屏幕采集。",
                doc_url=doc_url("readme"),
                message_en="Built-in screen recognition is not supported on this machine.",
                fix_en="Use this feature on macOS for now, or skip screen capture on this system.",
            )
        status = start_capture_daemon(
            data_root=DATA_ROOT,
            interval_seconds=settings.capture_interval_seconds,
            retention_hours=settings.screenshot_retention_hours,
        )
        console.print(f"[green]✅ 屏幕识别已开启（后台进程 {status.pid}）[/green]")
        return 0

    if action == "off":
        settings.enabled = False
        settings.participation_mode = "off"
        save_screen_context_settings(settings, data_root=DATA_ROOT)
        _upsert_project_env("SCREEN_RECOGNITION_ENABLED", "false")
        stop_capture_daemon(data_root=DATA_ROOT)
        console.print("[green]✅ 屏幕识别已关闭[/green]")
        return 0

    if action == "status":
        status = read_status(DATA_ROOT)
        running = "运行中" if status.running else "未运行"
        console.print(f"[cyan]ℹ️ 屏幕识别状态：{running}[/cyan]")
        return 0

    if action == "daemon":
        loop_data_root = Path(getattr(args, "data_root", DATA_ROOT) or DATA_ROOT)
        run_capture_loop(
            data_root=loop_data_root,
            interval_seconds=max(1, int(getattr(args, "interval", settings.capture_interval_seconds) or 1)),
            retention_hours=max(1, int(getattr(args, "retention_hours", settings.screenshot_retention_hours) or 1)),
        )
        return 0

    raise FriendlyCliError(
        "screen 只支持 on、off、status 这三个动作。",
        code="screen_action_invalid",
        fix="改成 `openmy screen on`、`openmy screen off` 或 `openmy screen status`。",
        doc_url=doc_url("readme"),
        message_en="screen only supports on, off, and status.",
        fix_en="Use openmy screen on, openmy screen off, or openmy screen status.",
    )
