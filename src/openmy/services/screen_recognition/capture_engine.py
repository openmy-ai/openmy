from __future__ import annotations

import ctypes
import gc
import multiprocessing as mp
import os
import queue
import shlex
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

from openmy.services.screen_recognition.capture_common import (
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    DEFAULT_CAPTURE_WORKER_TIMEOUT_SECONDS,
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


def _capture_worker(
    screenshot_path: str,
    data_root: str | None,
    languages: list[str] | None,
    result_queue: mp.Queue,
) -> None:
    root = Path(data_root) if data_root else None
    payload = extract_text_from_image(Path(screenshot_path), data_root=root, languages=languages)
    result_queue.put(
        {
            "text": payload.text,
            "text_json": payload.text_json,
            "confidence": payload.confidence,
            "engine": payload.engine,
        }
    )


def _ocr_context() -> mp.context.BaseContext:
    return mp.get_context("spawn")


def _release_memory_pressure() -> None:
    gc.collect()
    if sys.platform != "darwin":
        return
    try:
        libc = ctypes.CDLL("libSystem.B.dylib")
        relief = libc.malloc_zone_pressure_relief
        relief.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        relief.restype = ctypes.c_size_t
        relief(None, 0)
    except Exception:  # pragma: no cover
        return


def _is_screen_locked() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import Quartz  # type: ignore

        session = Quartz.CGSessionCopyCurrentDictionary() or {}
        return bool(session.get("CGSSessionScreenIsLocked", False))
    except Exception:
        return False


def _run_ocr_in_subprocess(
    screenshot_path: Path,
    *,
    data_root: Path | None = None,
    languages: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CAPTURE_WORKER_TIMEOUT_SECONDS,
) -> OcrPayload:
    context = _ocr_context()
    result_queue = context.Queue()
    process = context.Process(
        target=_capture_worker,
        args=(str(screenshot_path), str(data_root) if data_root else None, languages, result_queue),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(1)
        if process.is_alive():
            process.kill()
            process.join(1)
        result_queue.close()
        result_queue.join_thread()
        process.close()
        raise TimeoutError(f"屏幕识别子进程超时（{timeout_seconds}秒）")
    try:
        payload = result_queue.get_nowait()
    except queue.Empty as exc:  # pragma: no cover
        raise RuntimeError("屏幕识别子进程没有返回结果") from exc
    finally:
        result_queue.close()
        result_queue.join_thread()
        process.close()
    return OcrPayload(
        text=str(payload.get("text", "") or ""),
        text_json=[item for item in payload.get("text_json", []) if isinstance(item, dict)],
        confidence=float(payload.get("confidence", 0.0) or 0.0),
        engine=str(payload.get("engine", "") or ""),
    )


def capture_screen_event(
    *,
    data_root: Path | None = None,
    frame_id: int | None = None,
    languages: list[str] | None = None,
    ocr_cache: OcrCache | None = None,
    worker_timeout_seconds: int = DEFAULT_CAPTURE_WORKER_TIMEOUT_SECONDS,
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
    window_id = f"{metadata.app_name}::{metadata.window_name}"
    ocr = ocr_cache.get(window_id, content_hash) if ocr_cache is not None else None
    if ocr is None:
        try:
            ocr = _run_ocr_in_subprocess(
                shot_path,
                data_root=data_root,
                languages=languages,
                timeout_seconds=worker_timeout_seconds,
            )
        except Exception:
            shot_path.unlink(missing_ok=True)
            raise
        if ocr_cache is not None:
            ocr_cache.put(window_id, content_hash, ocr)
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
        screen_locked=False,
        ocr_text_json=ocr.text_json,
    )


def capture_once(
    *,
    data_root: Path | None = None,
    retention_hours: int = DEFAULT_SCREENSHOT_RETENTION_HOURS,
    ocr_cache: OcrCache | None = None,
) -> tuple[ScreenEventRecord, str, bool]:
    root = Path(data_root or DEFAULT_DATA_ROOT)
    status = read_status(root)
    if _is_screen_locked():
        status.last_error = ""
        write_status(status, root)
        _release_memory_pressure()
        return (
            ScreenEventRecord(
                frame_id=0,
                timestamp="",
                app_name="",
                window_name="",
                browser_url="",
                text="",
                screenshot_path="",
                content_hash="",
                ocr_engine="",
                screen_locked=True,
            ),
            "",
            False,
        )
    event = capture_screen_event(data_root=root, ocr_cache=ocr_cache)
    window_id = f"{event.app_name}::{event.window_name}"
    is_duplicate = window_id == status.last_window_id and event.content_hash == status.last_content_hash
    if is_duplicate:
        Path(event.screenshot_path).unlink(missing_ok=True)
    else:
        append_event(event, data_root=root)
        cleanup_old_snapshots(data_root=root, retention_hours=retention_hours)
    status.last_capture_at = event.timestamp
    status.last_frame_id = event.frame_id
    status.last_window_id = window_id
    status.last_content_hash = event.content_hash
    status.last_error = ""
    write_status(status, root)
    _release_memory_pressure()
    return event, window_id, is_duplicate


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
    if sys.platform.startswith("win"):
        status.running = False
        status.last_error = "内置截屏暂不支持 Windows"
        write_status(status, data_root)
        return status
    if not is_capture_supported():
        status.running = False
        status.last_error = "当前机器不支持内置截屏识别"
        write_status(status, data_root)
        return status

    log_handle = open(log_path(data_root), "a", encoding="utf-8")
    tick_cmd = " ".join(
        shlex.quote(part)
        for part in [
            sys.executable,
            "-m",
            "openmy.services.screen_recognition.capture_tick",
            "--retention-hours",
            str(retention_hours),
            "--data-root",
            str(Path(data_root or DEFAULT_DATA_ROOT)),
        ]
    )
    interval = max(1, int(interval_seconds))
    shell_script = (
        "fail=0; "
        f"while true; do {tick_cmd} && fail=0 || fail=$((fail+1)); "
        f"if [ \"$fail\" -gt 5 ]; then sleep 60; else sleep {interval}; fi; "
        "done"
    )
    cmd = ["/bin/sh", "-lc", shell_script]
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
    while True:
        try:
            capture_once(data_root=root, retention_hours=retention_hours, ocr_cache=ocr_cache)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            status.last_error = str(exc)
            write_status(status, root)
        time.sleep(max(1, interval_seconds))
