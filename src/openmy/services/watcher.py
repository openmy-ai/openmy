#!/usr/bin/env python3
"""
watcher.py — 录音文件监控器

监控指定目录，DJI Mic 录音落盘后自动触发 openmy run。
用户零感知，录完音自动出日报。

用法：
  python3 -m openmy.services.watcher /Volumes/NO\ NAME
  python3 -m openmy.services.watcher ~/Desktop/recordings

需要 watchdog: pip install watchdog
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# DJI Mic 文件名格式：TX01_MIC001_20260401_104056_orig.wav
DJI_FILENAME_RE = re.compile(r"TX01_MIC\d+_(\d{8})_\d{6}.*\.wav$", re.IGNORECASE)


def extract_date_from_filename(filename: str) -> str | None:
    """从 DJI Mic 文件名提取日期 YYYY-MM-DD。"""
    m = DJI_FILENAME_RE.search(filename)
    if not m:
        return None
    raw = m.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


class AudioFileHandler(FileSystemEventHandler):
    """检测新音频文件，按日期攒批后触发管线。"""

    def __init__(self, cooldown_seconds: int = 30):
        super().__init__()
        self.cooldown = cooldown_seconds
        self._pending: dict[str, list[str]] = {}  # date → [file_paths]
        self._last_trigger: dict[str, float] = {}

    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not path.lower().endswith(".wav"):
            return
        date_str = extract_date_from_filename(Path(path).name)
        if not date_str:
            return

        self._pending.setdefault(date_str, []).append(path)
        print(f"📎 检测到录音: {Path(path).name} → {date_str}")

    def check_and_trigger(self):
        """定期检查是否有攒够的批次可以触发。"""
        now = time.time()
        for date_str in list(self._pending.keys()):
            files = self._pending[date_str]
            last = self._last_trigger.get(date_str, 0)
            if now - last < self.cooldown:
                continue
            if not files:
                continue

            self._last_trigger[date_str] = now
            audio_args = self._pending.pop(date_str)
            print(f"\n🚀 触发管线: {date_str} ({len(audio_args)} 个文件)")
            try:
                cmd = [sys.executable, "-m", "openmy", "run", date_str, "--audio"] + audio_args
                subprocess.run(cmd, check=False)
            except Exception as exc:
                print(f"❌ 管线执行失败: {exc}")


def watch(directory: str, cooldown: int = 30):
    """启动监控。"""
    path = Path(directory).resolve()
    if not path.exists():
        print(f"❌ 目录不存在: {path}")
        sys.exit(1)

    handler = AudioFileHandler(cooldown_seconds=cooldown)
    observer = Observer()
    observer.schedule(handler, str(path), recursive=True)
    observer.start()

    print(f"👁️ 监控中: {path}")
    print(f"   冷却时间: {cooldown}秒")
    print("   按 Ctrl+C 停止\n")

    try:
        while True:
            time.sleep(5)
            handler.check_and_trigger()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 -m openmy.services.watcher <监控目录>")
        sys.exit(1)
    watch(sys.argv[1])
