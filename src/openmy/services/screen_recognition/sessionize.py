from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from openmy.domain.models import ScreenFrameRef, ScreenSession


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_domain(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc or ""


def _append_text(existing: str, new_text: str) -> str:
    new_text = str(new_text or "").strip()
    if not new_text:
        return existing
    if not existing:
        return new_text[:400]
    if new_text in existing:
        return existing
    return f"{existing}\n{new_text}"[:400]


def sessionize_screen_events(events, gap_seconds: int = 15) -> list[ScreenSession]:
    if not events:
        return []

    sorted_events = sorted(events, key=lambda item: item.timestamp or "")
    sessions: list[ScreenSession] = []
    current: dict | None = None

    for event in sorted_events:
        parsed_ts = _parse_timestamp(event.timestamp)
        key = (event.app_name, event.window_name, _extract_domain(getattr(event, "url", "")))
        if current and current["key"] == key:
            prev_ts = _parse_timestamp(current["end_time"])
            if parsed_ts and prev_ts and 0 <= (parsed_ts - prev_ts).total_seconds() <= gap_seconds:
                current["end_time"] = event.timestamp
                if event.frame_id:
                    current["frame_ids"].append(event.frame_id)
                    current["frame_refs"].append(ScreenFrameRef(frame_id=event.frame_id, timestamp=event.timestamp))
                current["text"] = _append_text(current["text"], getattr(event, "text", ""))
                continue

        if current:
            current.pop("key", None)
            sessions.append(ScreenSession(**current))

        current = {
            "session_id": f"screen_{len(sessions) + 1:03d}",
            "key": key,
            "app_name": event.app_name,
            "window_name": event.window_name,
            "url_domain": _extract_domain(getattr(event, "url", "")),
            "start_time": event.timestamp,
            "end_time": event.timestamp,
            "frame_ids": [event.frame_id] if event.frame_id else [],
            "frame_refs": [ScreenFrameRef(frame_id=event.frame_id, timestamp=event.timestamp)] if event.frame_id else [],
            "text": _append_text("", getattr(event, "text", "")),
        }

    if current:
        current.pop("key", None)
        sessions.append(ScreenSession(**current))

    for session in sessions:
        session.summary = session.summary or ""
    return sessions
