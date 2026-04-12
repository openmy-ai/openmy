from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

from openmy.services.screen_recognition.capture_common import (
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    DEFAULT_DATA_ROOT,
    DEFAULT_SCREENSHOT_RETENTION_HOURS,
    DaemonStatus,
    OcrPayload,
    PROJECT_ROOT,
    ScreenEventRecord,
    _now_local,
    _pid_is_running,
    ensure_runtime_dir,
    is_capture_supported,
    log_path,
    pid_path,
    read_status,
    screenshot_dir,
    write_status,
)
from openmy.services.screen_recognition.capture_store import (
    _file_hash,
    append_event,
    cleanup_old_snapshots,
    next_frame_id,
)
from openmy.services.screen_recognition.ocr_bridge import (
    capture_screenshot,
    extract_text_from_image,
    get_frontmost_context,
)


class OcrCache:
    """Port of Screenpipe's window OCR cache idea: key by window + image hash, age out quickly."""

    def __init__(self, max_entries: int = 100, max_age_seconds: int = 300):
        self.max_entries = max_entries
        self.max_age_seconds = max_age_seconds
        self._items: OrderedDict[tuple[str, str], tuple[float, OcrPayload]] = OrderedDict()

    def get(self, window_id: str, content_hash: str) -> OcrPayload | None:
        key = (window_id, content_hash)
        item = self._items.get(key)
        if not item:
            return None
        created_at, payload = item
        if time.time() - created_at > self.max_age_seconds:
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return payload

    def put(self, window_id: str, content_hash: str, payload: OcrPayload) -> None:
        key = (window_id, content_hash)
        self._items[key] = (time.time(), payload)
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)


def capture_screen_event(
    *,
    data_root: Path | None = None,
    frame_id: int | None = None,
    languages: list[str] | None = None,
) -> ScreenEventRecord:
    now = _now_local()
    date_str = now.date().isoformat()
    screens_dir = screenshot_dir(date_str, data_root)
    screens_dir.mkdir(parents=True, exist_ok=True)
    frame_number = frame_id or next_frame_id(date_str, data_root)
    shot_path = screens_dir / f"{int(now.timestamp() * 1000)}_f{frame_number}.png"
    metadata = get_frontmost_context(data_root=data_root)
    capture_screenshot(shot_path)
    content_hash = _file_hash(shot_path)
    ocr = extract_text_from_image(shot_path, data_root=data_root, languages=languages)
    return ScreenEventRecord(
        frame_id=frame_number,
        timestamp=now.isoformat(),
        app_name=metadata.app_name,
        window_name=metadata.window_name,
        browser_url=metadata.browser_url,
        text=ocr.text,
        screenshot_path=str(shot_path),
        content_hash=content_hash,
        ocr_engine=ocr.engine,
        ocr_text_json=ocr.text_json,
    )


def start_capture_daemon(
    *,
    data_root: Path | None = None,
    interval_seconds: int = DEFAULT_CAPTURE_INTERVAL_SECONDS,
    retention_hours: int = DEFAULT_SCREENSHOT_RETENTION_HOURS,
) -> DaemonStatus:
    ensure_runtime_dir(data_root)
    status = read_status(data_root)
    if _pid_is_running(status.pid):
        status.running = True
        write_status(status, data_root)
        return status
    if not is_capture_supported():
        status.running = False
        status.last_error = "当前机器不支持内置截屏识别"
        write_status(status, data_root)
        return status

    log_handle = open(log_path(data_root), "a", encoding="utf-8")
    cmd = [
        sys.executable,
        "-m",
        "openmy.cli",
        "_screen-capture-loop",
        "--interval",
        str(interval_seconds),
        "--retention-hours",
        str(retention_hours),
        "--data-root",
        str(Path(data_root or DEFAULT_DATA_ROOT)),
    ]
    process = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=log_handle,
        stderr=log_handle,
        start_new_session=True,
    )
    status.pid = process.pid
    status.running = True
    status.started_at = _now_local().isoformat()
    status.last_error = ""
    write_status(status, data_root)
    pid_path(data_root).write_text(str(process.pid), encoding="utf-8")
    return status


def stop_capture_daemon(*, data_root: Path | None = None) -> DaemonStatus:
    status = read_status(data_root)
    pid_value = status.pid
    if _pid_is_running(pid_value):
        try:
            os.killpg(pid_value, signal.SIGTERM)
        except OSError:
            try:
                os.kill(pid_value, signal.SIGTERM)
            except OSError:
                pass
    status.running = False
    status.pid = 0
    write_status(status, data_root)
    pid_path(data_root).unlink(missing_ok=True)
    return status


def run_capture_loop(
    *,
    data_root: Path | None = None,
    interval_seconds: int = DEFAULT_CAPTURE_INTERVAL_SECONDS,
    retention_hours: int = DEFAULT_SCREENSHOT_RETENTION_HOURS,
) -> None:
    root = Path(data_root or DEFAULT_DATA_ROOT)
    ensure_runtime_dir(root)
    status = read_status(root)
    status.pid = os.getpid()
    status.running = True
    if not status.started_at:
        status.started_at = _now_local().isoformat()
    write_status(status, root)

    ocr_cache = OcrCache()
    last_key = ""
    last_hash = ""
    while True:
        try:
            event = capture_screen_event(data_root=root)
            window_id = f"{event.app_name}::{event.window_name}"
            if window_id == last_key and event.content_hash == last_hash:
                Path(event.screenshot_path).unlink(missing_ok=True)
            else:
                cached = ocr_cache.get(window_id, event.content_hash)
                if cached is not None:
                    event.text = cached.text
                    event.ocr_text_json = cached.text_json
                    event.ocr_engine = cached.engine
                else:
                    ocr_cache.put(
                        window_id,
                        event.content_hash,
                        OcrPayload(
                            text=event.text,
                            text_json=list(event.ocr_text_json),
                            confidence=0.0,
                            engine=event.ocr_engine,
                        ),
                    )
                append_event(event, data_root=root)
                last_key = window_id
                last_hash = event.content_hash
                status.last_capture_at = event.timestamp
                status.last_frame_id = event.frame_id
                status.last_error = ""
                write_status(status, root)
                cleanup_old_snapshots(data_root=root, retention_hours=retention_hours)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            status.last_error = str(exc)
            write_status(status, root)
        time.sleep(max(1, interval_seconds))
