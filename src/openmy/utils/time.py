from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"
_TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_data_root() -> Path:
    return _project_root() / "data"


def _load_profile_timezone(data_root: Path) -> str:
    path = data_root / "profile.json"
    if not path.exists():
        return DEFAULT_TIMEZONE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_TIMEZONE
    timezone_name = str(payload.get("timezone", "") or "").strip()
    return timezone_name or DEFAULT_TIMEZONE


def get_user_timezone(data_root: Path | None = None) -> str:
    timezone_name = _load_profile_timezone(data_root or _default_data_root())
    try:
        ZoneInfo(timezone_name)
        return timezone_name
    except ZoneInfoNotFoundError:
        return DEFAULT_TIMEZONE


def iso_now(*, data_root: Path | None = None, dt: datetime | None = None) -> str:
    timezone_name = get_user_timezone(data_root)
    base = dt.astimezone(ZoneInfo(timezone_name)) if dt is not None else datetime.now(ZoneInfo(timezone_name))
    return base.isoformat(timespec="seconds")


def iso_at(
    date_str: str,
    time_str: str = "00:00",
    *,
    data_root: Path | None = None,
    timezone_name: str | None = None,
    seconds: int = 0,
) -> str:
    match = _TIME_RE.match((time_str or "").strip())
    hour = int(match.group(1)) if match else 0
    minute = int(match.group(2)) if match else 0
    year, month, day = (int(part) for part in date_str.split("-"))
    tz_name = timezone_name or get_user_timezone(data_root)
    try:
        tzinfo = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tzinfo = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime(year, month, day, hour, minute, seconds, tzinfo=tzinfo).isoformat(timespec="seconds")
