from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openmy.utils.io import safe_write_json
from openmy.utils.paths import DATA_ROOT as DEFAULT_DATA_ROOT
from openmy.utils.paths import PROJECT_ROOT

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
            log_path=str(payload.get("log_path", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    import sys

    return sys.platform


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
