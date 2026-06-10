from __future__ import annotations

import ctypes
import gc
import json
import multiprocessing as mp
import os
import queue
import shlex
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openmy.utils.io import safe_write_json
from openmy.utils.paths import DATA_ROOT as DEFAULT_DATA_ROOT
from openmy.utils.paths import PROJECT_ROOT as _PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants (formerly in capture_common)
# ---------------------------------------------------------------------------

RUNTIME_DIRNAME = "screen_capture"
EVENT_FILENAME = "screen_events.json"
OCR_HELPER_NAME = "apple_vision_ocr"
CONTEXT_HELPER_NAME = "frontmost_context"
STATUS_FILENAME = "status.json"
PID_FILENAME = "capture.pid"
LOG_FILENAME = "capture.log"
SWIFT_SOURCE_NAME = "apple_vision_ocr.swift"
CONTEXT_SWIFT_SOURCE_NAME = "frontmost_context.swift"
DEFAULT_CAPTURE_INTERVAL_SECONDS = 15
DEFAULT_SCREENSHOT_RETENTION_HOURS = 24
DEFAULT_EVENT_RETENTION_DAYS = 14
DEFAULT_CAPTURE_WORKER_TIMEOUT_SECONDS = 30
DEFAULT_OCR_LANGUAGES = ["zh-Hans", "zh-Hant", "en-US"]
PROJECT_ROOT = _PROJECT_ROOT

# ---------------------------------------------------------------------------
# Dataclasses (formerly in capture_common)
# ---------------------------------------------------------------------------


@dataclass
class CaptureMetadata:
    app_name: str = ""
    window_name: str = ""
    browser_url: str = ""


@dataclass
class OcrPayload:
    text: str = ""
    text_json: list[dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    engine: str = ""


@dataclass
class ScreenEventRecord:
    frame_id: int
    timestamp: str
    app_name: str
    window_name: str
    browser_url: str
    text: str
    screenshot_path: str
    content_hash: str
    ocr_engine: str
    screen_locked: bool = False
    ocr_text_json: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScreenEventRecord":
        return cls(
            frame_id=int(payload.get("frame_id", 0) or 0),
            timestamp=str(payload.get("timestamp", "") or ""),
            app_name=str(payload.get("app_name", "") or ""),
            window_name=str(payload.get("window_name", "") or ""),
            browser_url=str(payload.get("browser_url", "") or ""),
            text=str(payload.get("text", "") or ""),
            screenshot_path=str(payload.get("screenshot_path", "") or ""),
            content_hash=str(payload.get("content_hash", "") or ""),
            ocr_engine=str(payload.get("ocr_engine", "") or ""),
            screen_locked=bool(payload.get("screen_locked", False)),
            ocr_text_json=[item for item in payload.get("ocr_text_json", []) if isinstance(item, dict)],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DaemonStatus:
    pid: int = 0
    running: bool = False
    supported: bool = False
    started_at: str = ""
    last_capture_at: str = ""
    last_error: str = ""
    last_frame_id: int = 0
    last_window_id: str = ""
    last_content_hash: str = ""
    log_path: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "DaemonStatus":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            pid=int(payload.get("pid", 0) or 0),
            running=bool(payload.get("running", False)),
            supported=bool(payload.get("supported", False)),
            started_at=str(payload.get("started_at", "") or ""),
            last_capture_at=str(payload.get("last_capture_at", "") or ""),
            last_error=str(payload.get("last_error", "") or ""),
            last_frame_id=int(payload.get("last_frame_id", 0) or 0),
            last_window_id=str(payload.get("last_window_id", "") or ""),
            last_content_hash=str(payload.get("last_content_hash", "") or ""),
            log_path=str(payload.get("log_path", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Path helpers (formerly in capture_common)
# ---------------------------------------------------------------------------


def runtime_dir(data_root: Path | None = None) -> Path:
    root = Path(data_root or DEFAULT_DATA_ROOT)
    return root / "runtime" / RUNTIME_DIRNAME


def status_path(data_root: Path | None = None) -> Path:
    return runtime_dir(data_root) / STATUS_FILENAME


def pid_path(data_root: Path | None = None) -> Path:
    return runtime_dir(data_root) / PID_FILENAME


def log_path(data_root: Path | None = None) -> Path:
    return runtime_dir(data_root) / LOG_FILENAME


def helper_binary_path(data_root: Path | None = None) -> Path:
    return runtime_dir(data_root) / OCR_HELPER_NAME


def context_helper_binary_path(data_root: Path | None = None) -> Path:
    return runtime_dir(data_root) / CONTEXT_HELPER_NAME


def helper_source_path() -> Path:
    return Path(__file__).with_name(SWIFT_SOURCE_NAME)


def context_helper_source_path() -> Path:
    return Path(__file__).with_name(CONTEXT_SWIFT_SOURCE_NAME)


def day_dir(date_str: str, data_root: Path | None = None) -> Path:
    root = Path(data_root or DEFAULT_DATA_ROOT)
    return root / date_str


def event_store_path(date_str: str, data_root: Path | None = None) -> Path:
    return day_dir(date_str, data_root) / EVENT_FILENAME


def screen_events_path(date_str: str, data_root: Path | None = None) -> Path:
    return event_store_path(date_str, data_root)


def screenshot_dir(date_str: str, data_root: Path | None = None) -> Path:
    return day_dir(date_str, data_root) / "screens"


# ---------------------------------------------------------------------------
# Utility helpers (formerly in capture_common)
# ---------------------------------------------------------------------------


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _date_range(start_time: datetime, end_time: datetime) -> list[str]:
    current = start_time.date()
    dates: list[str] = []
    while current <= end_time.date():
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def is_capture_supported() -> bool:
    return sys_platform() == "darwin" and shutil_which("screencapture") is not None and shutil_which("swiftc") is not None


def sys_platform() -> str:
    import sys as _sys

    return _sys.platform


def ensure_runtime_dir(data_root: Path | None = None) -> Path:
    root = runtime_dir(data_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def read_status(data_root: Path | None = None) -> DaemonStatus:
    path = status_path(data_root)
    if not path.exists():
        return DaemonStatus(supported=is_capture_supported(), log_path=str(log_path(data_root)))
    try:
        return DaemonStatus.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return DaemonStatus(supported=is_capture_supported(), log_path=str(log_path(data_root)))


def write_status(status: DaemonStatus, data_root: Path | None = None) -> None:
    status.supported = is_capture_supported()
    status.log_path = str(log_path(data_root))
    safe_write_json(status_path(data_root), status.to_dict())


def _pid_is_running(pid_value: int) -> bool:
    if pid_value <= 0:
        return False
    try:
        os.kill(pid_value, 0)
    except OSError:
        return False
    return True


def daemon_running(data_root: Path | None = None) -> bool:
    status = read_status(data_root)
    return _pid_is_running(status.pid)


# ---------------------------------------------------------------------------
# Capture engine
# ---------------------------------------------------------------------------


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
    from openmy.services.screen_recognition.ocr_bridge import extract_text_from_image

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
    from openmy.services.screen_recognition.capture_store import _file_hash, next_frame_id
    from openmy.services.screen_recognition.ocr_bridge import capture_screenshot, get_frontmost_context

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
    from openmy.services.screen_recognition.capture_store import append_event, cleanup_old_snapshots

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
