from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openmy.services.screen_recognition.capture_common import (
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    DEFAULT_SCREENSHOT_RETENTION_HOURS,
    DEFAULT_DATA_ROOT,
    EVENT_FILENAME,
    ScreenEventRecord,
    _date_range,
    _now_local,
    _parse_time,
    event_store_path,
    safe_write_json,
)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_events_for_date(date_str: str, data_root: Path | None = None) -> list[ScreenEventRecord]:
    path = event_store_path(date_str, data_root)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [ScreenEventRecord.from_dict(item) for item in payload if isinstance(item, dict)]


def save_events_for_date(date_str: str, events: list[ScreenEventRecord], data_root: Path | None = None) -> None:
    safe_write_json(event_store_path(date_str, data_root), [item.to_dict() for item in events])


def next_frame_id(date_str: str, data_root: Path | None = None) -> int:
    events = load_events_for_date(date_str, data_root)
    if not events:
        return 1
    return max(item.frame_id for item in events) + 1


def append_event(record: ScreenEventRecord, *, data_root: Path | None = None) -> None:
    date_str = (_parse_time(record.timestamp) or _now_local()).date().isoformat()
    events = load_events_for_date(date_str, data_root)
    events.append(record)
    save_events_for_date(date_str, events, data_root)


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
        for record in load_events_for_date(date_str, data_root):
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
