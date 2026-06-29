"""auto.py — 设备自动入口（智能入口）命令。

  openmy auto            前台常驻守护（调试用，Ctrl+C 停）
  openmy auto scan       扫一次已插着的设备并处理后退出（launchd 调用）
  openmy auto install    安装登录自启 + 插盘唤醒的后台守护
  openmy auto uninstall  卸载后台守护
  openmy auto status     查看守护安装/运行状态

后台模式用 macOS LaunchAgent：登录时跑一次（处理已插的盘）、每次有卷挂载时
唤醒扫描一次（StartOnMount），不需要常驻轮询，省资源。
"""

from __future__ import annotations

import argparse
import platform
import plistlib
import subprocess
import sys
from pathlib import Path

from openmy.utils.paths import PROJECT_ROOT

PLIST_LABEL = "ai.openmy.device-watcher"


def _require_macos() -> bool:
    if platform.system() != "Darwin":
        print("后台守护目前只支持 macOS。其它系统可用 `openmy auto` 前台运行。")
        return False
    return True


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def _log_dir() -> Path:
    path = Path.home() / ".openmy" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_plist_bytes() -> bytes:
    log_dir = _log_dir()
    spec = {
        "Label": PLIST_LABEL,
        "ProgramArguments": [sys.executable, "-m", "openmy", "auto", "scan"],
        "RunAtLoad": True,        # 登录时跑一次，处理已经插着的盘
        "StartOnMount": True,     # 每次有卷挂载时唤醒，扫一次后退出
        "WorkingDirectory": str(PROJECT_ROOT),
        "EnvironmentVariables": {
            "OPENMY_PROJECT_ROOT": str(PROJECT_ROOT),
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "StandardOutPath": str(log_dir / "device-watcher.log"),
        "StandardErrorPath": str(log_dir / "device-watcher.log"),
    }
    return plistlib.dumps(spec)


def _install() -> int:
    if not _require_macos():
        return 1
    plist = _plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)
    # 先尝试卸载旧的，避免重复加载
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, check=False)
    plist.write_bytes(_build_plist_bytes())
    result = subprocess.run(
        ["launchctl", "load", "-w", str(plist)], capture_output=True, check=False
    )
    if result.returncode != 0:
        print("❌ 后台守护安装失败：", result.stderr.decode(errors="replace").strip())
        return 1
    print("✅ 后台守护已开启。插上 DJI Mic 就会自动整理，整理好通知你。")
    return 0


def _uninstall() -> int:
    if not _require_macos():
        return 1
    plist = _plist_path()
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, check=False)
    if plist.exists():
        plist.unlink()
    print("✅ 后台守护已关闭。")
    return 0


def _status() -> int:
    plist = _plist_path()
    if not plist.exists():
        print("后台守护：未安装。运行 `openmy auto install` 开启。")
        return 0
    result = subprocess.run(
        ["launchctl", "list", PLIST_LABEL], capture_output=True, check=False
    )
    state = "运行中" if result.returncode == 0 else "已安装但未加载"
    print(f"后台守护：{state}。")
    return 0


def _scan() -> int:
    from openmy.services.device_watcher import run_once

    count = run_once()
    if count == 0:
        print("没有发现新录音。")
    return 0


def _run() -> int:
    from openmy.services.device_watcher import watch_devices

    watch_devices()
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    action = getattr(args, "auto_action", None) or "run"
    return {
        "run": _run,
        "scan": _scan,
        "install": _install,
        "uninstall": _uninstall,
        "status": _status,
    }.get(action, _run)()
