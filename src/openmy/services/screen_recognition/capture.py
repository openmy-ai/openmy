# screenpipe-derived built-in screen capture helpers for OpenMy.
# Ported from the MIT-licensed Screenpipe project (https://github.com/mediar-ai/screenpipe),
# adapted to OpenMy's local JSON event store and Python runtime.

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections import OrderedDict, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openmy.utils.io import safe_write_json

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
RUNTIME_DIRNAME = "screen_capture"
EVENT_FILENAME = "screen_events.json"
OCR_HELPER_NAME = "apple_vision_ocr"
CONTEXT_HELPER_NAME = "frontmost_context"
STATUS_FILENAME = "status.json"
PID_FILENAME = "capture.pid"
LOG_FILENAME = "capture.log"
SWIFT_SOURCE_NAME = "apple_vision_ocr.swift"
CONTEXT_SWIFT_SOURCE_NAME = "frontmost_context.swift"
DEFAULT_CAPTURE_INTERVAL_SECONDS = 5
DEFAULT_SCREENSHOT_RETENTION_HOURS = 24
DEFAULT_EVENT_RETENTION_DAYS = 14
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


def is_capture_supported() -> bool:
    return sys.platform == "darwin" and shutil_which("screencapture") is not None and shutil_which("swiftc") is not None


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


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


def ensure_runtime_dir(data_root: Path | None = None) -> Path:
    root = runtime_dir(data_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def compile_vision_helper(data_root: Path | None = None) -> Path:
    ensure_runtime_dir(data_root)
    source = helper_source_path()
    binary = helper_binary_path(data_root)
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    cmd = [
        "swiftc",
        str(source),
        "-O",
        "-framework",
        "Foundation",
        "-framework",
        "Vision",
        "-framework",
        "AppKit",
        "-framework",
        "CoreGraphics",
        "-o",
        str(binary),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return binary


def compile_context_helper(data_root: Path | None = None) -> Path:
    ensure_runtime_dir(data_root)
    source = context_helper_source_path()
    binary = context_helper_binary_path(data_root)
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    cmd = [
        "swiftc",
        str(source),
        "-O",
        "-framework",
        "Foundation",
        "-framework",
        "AppKit",
        "-framework",
        "CoreGraphics",
        "-o",
        str(binary),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return binary


def capture_screenshot(output_path: Path, display_id: str | None = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["screencapture", "-x"]
    if display_id:
        cmd.extend(["-D", str(display_id)])
    cmd.append(str(output_path))
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return output_path


def _run_osascript(script: str) -> str:
    result = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_frontmost_context(data_root: Path | None = None) -> CaptureMetadata:
    app_name = ""
    window_name = ""
    browser_url = ""

    try:
        helper = compile_context_helper(data_root)
        result = subprocess.run([str(helper)], check=False, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            payload = json.loads(result.stdout)
            app_name = str(payload.get("app_name", "") or "").strip()
            window_name = str(payload.get("window_name", "") or "").strip()
    except Exception:
        app_name = ""
        window_name = ""

    if not app_name:
        app_name = _run_osascript(
            'tell application "System Events" to get name of first application process whose frontmost is true'
        ).strip()
    if not window_name:
        window_name = _run_osascript(
            'tell application "System Events" to tell (first application process whose frontmost is true) to get name of front window'
        ).strip()

    if app_name == "Google Chrome":
        browser_url = _run_osascript(
            'tell application "Google Chrome" to get URL of active tab of front window'
        )
    elif app_name == "Arc":
        browser_url = _run_osascript(
            'tell application "Arc" to get URL of active tab of front window'
        )
    elif app_name == "Safari":
        browser_url = _run_osascript('tell application "Safari" to get URL of front document')

    return CaptureMetadata(
        app_name=app_name.strip(),
        window_name=window_name.strip(),
        browser_url=browser_url.strip(),
    )


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_text_from_image(
    image_path: Path,
    *,
    data_root: Path | None = None,
    languages: list[str] | None = None,
) -> OcrPayload:
    languages = languages or list(DEFAULT_OCR_LANGUAGES)
    helper = compile_vision_helper(data_root)
    cmd = [str(helper), str(image_path), ",".join(languages)]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout)
            return OcrPayload(
                text=str(payload.get("text", "") or "").strip(),
                text_json=[item for item in payload.get("text_json", []) if isinstance(item, dict)],
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                engine=str(payload.get("engine", "apple-vision") or "apple-vision"),
            )
        except Exception:
            pass

    if shutil_which("tesseract"):
        return extract_text_with_tesseract(image_path)

    stderr = result.stderr.strip() or "Vision helper failed"
    return OcrPayload(text="", text_json=[], confidence=0.0, engine=f"error:{stderr}")


def extract_text_with_tesseract(image_path: Path) -> OcrPayload:
    cmd = ["tesseract", str(image_path), "stdout", "tsv"]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return OcrPayload(text="", text_json=[], confidence=0.0, engine="tesseract")
    lines = result.stdout.splitlines()
    if not lines:
        return OcrPayload(text="", text_json=[], confidence=0.0, engine="tesseract")
    rows = []
    full_text: list[str] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        text = parts[11].strip()
        if not text:
            continue
        try:
            left, top, width, height = int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9])
            conf = float(parts[10]) if parts[10] not in {"-1", ""} else 0.0
        except ValueError:
            continue
        rows.append(
            {
                "left": str(left),
                "top": str(top),
                "width": str(width),
                "height": str(height),
                "conf": str(conf),
                "text": text,
            }
        )
        full_text.append(text)
    confidence = sum(float(item.get("conf", 0.0)) for item in rows) / len(rows) if rows else 0.0
    return OcrPayload(text=" ".join(full_text).strip(), text_json=rows, confidence=confidence, engine="tesseract")


def _load_events_for_date(date_str: str, data_root: Path | None = None) -> list[ScreenEventRecord]:
    path = event_store_path(date_str, data_root)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [ScreenEventRecord.from_dict(item) for item in payload if isinstance(item, dict)]


def _save_events_for_date(date_str: str, events: list[ScreenEventRecord], data_root: Path | None = None) -> None:
    safe_write_json(event_store_path(date_str, data_root), [item.to_dict() for item in events])


def next_frame_id(date_str: str, data_root: Path | None = None) -> int:
    events = _load_events_for_date(date_str, data_root)
    if not events:
        return 1
    return max(item.frame_id for item in events) + 1


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
    screenshot_path = screens_dir / f"{int(now.timestamp() * 1000)}_f{frame_number}.png"
    metadata = get_frontmost_context(data_root=data_root)
    capture_screenshot(screenshot_path)
    content_hash = _file_hash(screenshot_path)
    ocr = extract_text_from_image(screenshot_path, data_root=data_root, languages=languages)
    return ScreenEventRecord(
        frame_id=frame_number,
        timestamp=now.isoformat(),
        app_name=metadata.app_name,
        window_name=metadata.window_name,
        browser_url=metadata.browser_url,
        text=ocr.text,
        screenshot_path=str(screenshot_path),
        content_hash=content_hash,
        ocr_engine=ocr.engine,
        ocr_text_json=ocr.text_json,
    )


def append_event(record: ScreenEventRecord, *, data_root: Path | None = None) -> None:
    date_str = (_parse_time(record.timestamp) or _now_local()).date().isoformat()
    events = _load_events_for_date(date_str, data_root)
    events.append(record)
    _save_events_for_date(date_str, events, data_root)


def query_events(
    start_time: str,
    end_time: str,
    *,
    data_root: Path | None = None,
    app_name: str | None = None,
    limit: int = 100,
) -> list[ScreenEventRecord]:
    start_dt = _parse_time(start_time)
    end_dt = _parse_time(end_time)
    if not start_dt or not end_dt or end_dt < start_dt:
        return []
    results: list[ScreenEventRecord] = []
    expected_app = (app_name or "").strip().lower()
    for date_str in _date_range(start_dt, end_dt):
        for record in _load_events_for_date(date_str, data_root):
            ts = _parse_time(record.timestamp)
            if not ts:
                continue
            if ts < start_dt or ts > end_dt:
                continue
            if expected_app and record.app_name.lower() != expected_app:
                continue
            results.append(record)
    results.sort(key=lambda item: item.timestamp)
    if limit > 0:
        return results[:limit]
    return results


def search_elements(
    start_time: str,
    end_time: str,
    *,
    data_root: Path | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in query_events(start_time, end_time, data_root=data_root, limit=0):
        for item in record.ocr_text_json:
            rows.append(
                {
                    "frame_id": record.frame_id,
                    "timestamp": record.timestamp,
                    "app_name": record.app_name,
                    "window_name": record.window_name,
                    "text": str(item.get("text", "") or ""),
                    "bounds": {
                        "left": item.get("left", "0"),
                        "top": item.get("top", "0"),
                        "width": item.get("width", "0"),
                        "height": item.get("height", "0"),
                    },
                }
            )
            if limit > 0 and len(rows) >= limit:
                return rows
    return rows


def activity_summary(
    start_time: str,
    end_time: str,
    *,
    data_root: Path | None = None,
    capture_interval_seconds: int = DEFAULT_CAPTURE_INTERVAL_SECONDS,
) -> dict[str, Any]:
    events = query_events(start_time, end_time, data_root=data_root, limit=0)
    if not events:
        return {
            "apps": [],
            "windows": [],
            "time_range": {"start": start_time, "end": end_time},
            "total_frames": 0,
        }

    app_groups: dict[str, list[ScreenEventRecord]] = defaultdict(list)
    window_groups: dict[tuple[str, str, str], list[ScreenEventRecord]] = defaultdict(list)
    for event in events:
        app_groups[event.app_name or "未知应用"].append(event)
        window_groups[(event.app_name or "未知应用", event.window_name, event.browser_url)].append(event)

    def _minutes(group: list[ScreenEventRecord]) -> float:
        stamps = [_parse_time(item.timestamp) for item in group]
        stamps = [item for item in stamps if item is not None]
        if len(stamps) < 2:
            return round(capture_interval_seconds / 60, 2)
        seconds = max(capture_interval_seconds, int((max(stamps) - min(stamps)).total_seconds()) + capture_interval_seconds)
        return round(seconds / 60, 2)

    apps = []
    for name, group in sorted(app_groups.items(), key=lambda item: item[0]):
        apps.append(
            {
                "name": name,
                "minutes": _minutes(group),
                "frame_count": len(group),
                "first_seen": group[0].timestamp,
                "last_seen": group[-1].timestamp,
            }
        )
    apps.sort(key=lambda item: (-item["minutes"], item["name"]))

    windows = []
    for (app_name, window_name, browser_url), group in window_groups.items():
        windows.append(
            {
                "app_name": app_name,
                "window_name": window_name,
                "browser_url": browser_url,
                "minutes": _minutes(group),
                "frame_count": len(group),
            }
        )
    windows.sort(key=lambda item: (-item["minutes"], item["app_name"], item["window_name"]))
    return {
        "apps": apps,
        "windows": windows,
        "time_range": {"start": start_time, "end": end_time},
        "total_frames": len(events),
    }


def cleanup_old_snapshots(*, data_root: Path | None = None, retention_hours: int = DEFAULT_SCREENSHOT_RETENTION_HOURS) -> None:
    cutoff = _now_local() - timedelta(hours=max(1, retention_hours))
    for event_file in Path(data_root or DEFAULT_DATA_ROOT).glob(f"*/{EVENT_FILENAME}"):
        date_dir = event_file.parent
        screen_dir = date_dir / "screens"
        if not screen_dir.exists():
            continue
        for image_path in screen_dir.glob("*.png"):
            modified = datetime.fromtimestamp(image_path.stat().st_mtime, tz=cutoff.tzinfo)
            if modified < cutoff:
                image_path.unlink(missing_ok=True)


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
