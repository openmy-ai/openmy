from __future__ import annotations

from datetime import datetime

from openmy.domain.models import SceneBlock, ScreenSession


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _scene_range(scene: SceneBlock, date_str: str) -> tuple[datetime | None, datetime | None]:
    try:
        start = datetime.fromisoformat(f"{date_str}T{scene.time_start}:00+08:00")
        end_clock = scene.time_end or scene.time_start
        end = datetime.fromisoformat(f"{date_str}T{end_clock}:59+08:00")
        return start, end
    except ValueError:
        return None, None


def align_scene_sessions(scene: SceneBlock, sessions: list[ScreenSession], date_str: str) -> list[ScreenSession]:
    scene_start, scene_end = _scene_range(scene, date_str)
    if not scene_start or not scene_end:
        return []

    aligned: list[ScreenSession] = []
    for session in sessions:
        start = _parse_dt(session.start_time)
        end = _parse_dt(session.end_time)
        if not start or not end:
            continue
        if start <= scene_end and end >= scene_start:
            aligned.append(session)
    return aligned
