#!/usr/bin/env python3
"""watcher.py — 录音文件监控器。

监控指定目录，DJI Mic 录音落盘后自动触发 openmy run。
默认策略是“watchdog 事件优先 + 目录扫描兜底”：

- 有 watchdog：监听目录事件，再用轮询确认文件稳定落盘
- 没有 watchdog：自动降级成纯扫描模式
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from openmy.config import get_audio_source_dir
from openmy.utils.errors import FriendlyCliError, doc_url

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - 通过纯扫描模式兜底
    class FileSystemEventHandler:  # type: ignore[override]
        pass

    Observer = None


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

    def __init__(self, cooldown_seconds: int = 30, stable_passes: int = 1):
        super().__init__()
        self.cooldown = cooldown_seconds
        self.stable_passes = stable_passes
        self._pending: dict[str, list[str]] = {}  # date → [file_paths]
        self._last_trigger: dict[str, float] = {}
        self._scan_state: dict[str, dict[str, int | str]] = {}
        self._queued_files: set[str] = set()

    def _remember_candidate(self, path: Path, *, from_scan: bool) -> None:
        if not path.is_file() or path.suffix.lower() != ".wav":
            return
        date_str = extract_date_from_filename(path.name)
        if not date_str:
            return
        try:
            stat = path.stat()
        except OSError:
            return

        key = str(path.resolve())
        signature = (stat.st_size, stat.st_mtime_ns)
        current = self._scan_state.get(key)
        if (
            current
            and from_scan
            and bool(current.get("seen_by_scan"))
            and (current["size"], current["mtime_ns"]) == signature
        ):
            current["stable_rounds"] = int(current["stable_rounds"]) + 1
        else:
            self._scan_state[key] = {
                "date": date_str,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "stable_rounds": 0,
                "seen_by_scan": from_scan,
            }
            return

        if from_scan:
            self._scan_state[key]["seen_by_scan"] = True

        stable_rounds = int(self._scan_state[key]["stable_rounds"])
        if stable_rounds < self.stable_passes or key in self._queued_files:
            return

        self._queued_files.add(key)
        self._pending.setdefault(date_str, []).append(key)
        print(f"📎 检测到稳定录音: {path.name} → {date_str}")

    def on_created(self, event):
        if event.is_directory:
            return
        self._remember_candidate(Path(event.src_path), from_scan=False)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._remember_candidate(Path(event.src_path), from_scan=False)

    def scan_directory(self, directory: Path) -> None:
        for wav_path in directory.rglob("*.wav"):
            self._remember_candidate(wav_path, from_scan=True)

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


def create_observer(path: Path, handler: AudioFileHandler):
    if Observer is None:
        return None
    observer = Observer()
    observer.schedule(handler, str(path), recursive=True)
    observer.start()
    return observer


def resolve_watch_directory(directory: str | None = None) -> Path:
    raw = str(directory or "").strip() or get_audio_source_dir()
    if not raw:
        raise FriendlyCliError(
            "还没告诉我该监控哪个录音目录。",
            code="watch_directory_missing",
            fix="运行 `openmy skill profile.set --audio-source 你的录音目录 --json`，或者直接给 `openmy watch 目录路径`。",
            doc_url=doc_url("一分钟跑起来"),
            message_en="No watch directory was provided and OPENMY_AUDIO_SOURCE_DIR is not configured.",
            fix_en="Run openmy skill profile.set --audio-source YOUR_DIRECTORY --json or pass a directory to openmy watch.",
        )
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise FriendlyCliError(
            "你给的录音目录不存在。",
            code="watch_directory_not_found",
            fix="先确认目录路径写对了，再重试。",
            doc_url=doc_url("一分钟跑起来"),
            message_en=f"The watch directory does not exist: {path}",
            fix_en="Check the directory path and retry.",
        )
    return path


def watch(directory: str | None = None, cooldown: int = 30):
    """启动监控。"""
    try:
        path = resolve_watch_directory(directory)
    except FriendlyCliError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    handler = AudioFileHandler(cooldown_seconds=cooldown)
    observer = create_observer(path, handler)

    print(f"👁️ 监控中: {path}")
    print(f"   冷却时间: {cooldown}秒")
    if observer is None:
        print("   模式：纯扫描（watchdog 不可用）")
    else:
        print("   模式：事件监听 + 扫描兜底")
    print("   按 Ctrl+C 停止\n")

    try:
        while True:
            time.sleep(5)
            handler.scan_directory(path)
            handler.check_and_trigger()
    except KeyboardInterrupt:
        if observer is not None:
            observer.stop()
    if observer is not None:
        observer.join()


if __name__ == "__main__":
    watch(sys.argv[1] if len(sys.argv) >= 2 else None)
