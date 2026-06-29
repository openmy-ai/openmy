"""device_watcher.py — 设备自动入口守护。

监测 /Volumes 出现 DJI Mic 卷 → 把新录音拷贝到本地 → 自动转写整理 → 完成桌面通知。
全程无感：用户插上 DJI Mic 就走完，处理好了才被一条通知轻拍一下。

识别策略：DJI Mic 3 内录盘的卷名是 "NO NAME"（不是 spec 假设的 "DJI*"），
所以靠卷里有没有 TX01_MIC*.wav 文件来认，而不是靠卷名。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from openmy.services.notify import (
    build_completion_message,
    build_error_message,
    build_start_message,
    send_notification,
)
from openmy.services.watcher import DJI_FILENAME_RE, extract_date_from_filename
from openmy.utils.paths import DATA_ROOT

VOLUMES_ROOT = Path("/Volumes")

# 扫描外部卷时的安全上限，避免误扫大盘卡死
_MAX_SCAN_DEPTH = 3
_MAX_SCAN_ENTRIES = 50000


def _openmy_home() -> Path:
    return Path.home() / ".openmy"


def staging_dir() -> Path:
    path = _openmy_home() / "inbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_path() -> Path:
    return _openmy_home() / "device_ledger.json"


# ---------------------------------------------------------------------------
# 设备检测
# ---------------------------------------------------------------------------

def _root_device() -> int:
    try:
        return os.stat("/").st_dev
    except OSError:
        return -1


def list_external_volumes() -> list[Path]:
    """列出 /Volumes 下的外部卷（排除指向启动盘的那个）。"""
    if not VOLUMES_ROOT.exists():
        return []
    root_dev = _root_device()
    volumes: list[Path] = []
    for entry in VOLUMES_ROOT.iterdir():
        try:
            if not entry.is_dir():
                continue
            if entry.stat().st_dev == root_dev:
                continue  # 启动盘本身，跳过
        except OSError:
            continue
        volumes.append(entry)
    return volumes


def find_dji_recordings(volume: Path) -> list[Path]:
    """在一个卷里找 DJI Mic 录音，带深度与条目数上限防止扫穿大盘。"""
    found: list[Path] = []
    scanned = 0
    stack: list[tuple[Path, int]] = [(volume, 0)]
    while stack:
        directory, depth = stack.pop()
        try:
            entries = list(directory.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in entries:
            scanned += 1
            if scanned > _MAX_SCAN_ENTRIES:
                return found
            try:
                if entry.is_dir():
                    if depth < _MAX_SCAN_DEPTH:
                        stack.append((entry, depth + 1))
                elif entry.suffix.lower() == ".wav" and DJI_FILENAME_RE.search(entry.name):
                    found.append(entry)
            except OSError:
                continue
    return found


# ---------------------------------------------------------------------------
# 拷贝 + 去重账本
# ---------------------------------------------------------------------------

def _load_ledger(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _ledger_key(src: Path) -> str:
    """文件名 + 大小作为唯一键（DJI 文件名含时间戳，基本唯一）。"""
    try:
        size = src.stat().st_size
    except OSError:
        size = 0
    return f"{src.name}:{size}"


def copy_new_recordings(
    recordings: list[Path], destination: Path, ledger: dict[str, Any]
) -> list[Path]:
    """把账本里没有的录音拷贝到本地，返回这次新拷贝的文件路径。"""
    copied: list[Path] = []
    for src in recordings:
        key = _ledger_key(src)
        if key in ledger:
            continue
        dest = destination / src.name
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            print(f"❌ 拷贝失败 {src.name}: {exc}")
            continue
        ledger[key] = {"name": src.name, "copied_to": str(dest)}
        copied.append(dest)
        print(f"📥 已拷贝到本地: {src.name}")
    return copied


# ---------------------------------------------------------------------------
# 触发处理 + 通知
# ---------------------------------------------------------------------------

def group_by_date(files: list[Path]) -> dict[str, list[str]]:
    """按 DJI 文件名里的日期分组；认不出日期的归到 'unknown'。"""
    grouped: dict[str, list[str]] = {}
    for path in files:
        date_str = extract_date_from_filename(path.name) or "unknown"
        grouped.setdefault(date_str, []).append(str(path))
    return grouped


def _read_briefing(date: str) -> dict[str, Any] | None:
    path = DATA_ROOT / date / "daily_briefing.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _run_pipeline(date: str, files: list[str]) -> int:
    cmd = [sys.executable, "-m", "openmy", "run", date, "--audio", *files]
    try:
        return subprocess.run(cmd, check=False).returncode
    except Exception as exc:  # noqa: BLE001 - 守护不能被单次失败拖垮
        print(f"❌ 管线执行失败: {exc}")
        return 1


def process_and_notify(copied: list[Path]) -> None:
    for date_str, files in group_by_date(copied).items():
        send_notification(*build_start_message(date_str, len(files)))
        print(f"\n🚀 整理 {date_str}（{len(files)} 段）…")
        code = _run_pipeline(date_str, files)
        if code in (0, 2):  # 0 完成 / 2 部分完成
            briefing = _read_briefing(date_str)
            title, message = build_completion_message(date_str, briefing)
            send_notification(title, message, sound=True)
            print(f"✅ {message}")
        else:
            title, message = build_error_message(date_str, "转写整理失败")
            send_notification(title, message)
            print(f"❌ {message}")


# ---------------------------------------------------------------------------
# 守护主循环
# ---------------------------------------------------------------------------

def scan_once(ledger: dict[str, Any], volumes: list[Path]) -> list[Path]:
    """扫描给定的卷，拷贝新录音并返回这次拷贝的文件。"""
    dest = staging_dir()
    all_copied: list[Path] = []
    for volume in volumes:
        recordings = find_dji_recordings(volume)
        if not recordings:
            continue
        print(f"🎙️ 在 {volume.name} 发现 {len(recordings)} 段 DJI 录音")
        copied = copy_new_recordings(recordings, dest, ledger)
        if copied:
            all_copied.extend(copied)
    if all_copied:
        _save_ledger(ledger_path(), ledger)
    return all_copied


def run_once() -> int:
    """扫一次当前已挂载的外部卷，拷贝并处理新录音，返回新拷贝的文件数。

    launchd 的 StartOnMount / RunAtLoad 每次唤醒都调它，扫完即退，不常驻。
    """
    ledger = _load_ledger(ledger_path())
    copied = scan_once(ledger, list_external_volumes())
    if copied:
        process_and_notify(copied)
    return len(copied)


def watch_devices(poll_seconds: int = 5) -> None:
    """启动设备守护：第一次把已插着的盘也处理，之后只对新挂载的卷动手。"""
    ledger = _load_ledger(ledger_path())
    seen: set[str] = set()
    first = True

    print("🔌 设备守护已启动，等待 DJI Mic 插入…")
    print("   按 Ctrl+C 停止\n")
    try:
        while True:
            current = list_external_volumes()
            current_names = {str(v) for v in current}
            if first:
                targets = current
            else:
                targets = [v for v in current if str(v) not in seen]
            if targets:
                copied = scan_once(ledger, targets)
                if copied:
                    process_and_notify(copied)
            seen = current_names
            first = False
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("\n👋 设备守护已停止")


if __name__ == "__main__":
    watch_devices()
