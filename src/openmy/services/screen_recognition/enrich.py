from __future__ import annotations

from openmy.domain.models import SceneBlock, ScreenSession
from openmy.services.screen_recognition.align import align_scene_sessions
from openmy.services.screen_recognition.privacy import apply_privacy_filters
from openmy.services.screen_recognition.sessionize import sessionize_screen_events
from openmy.services.screen_recognition.settings import ScreenContextSettings, load_screen_context_settings
from openmy.services.screen_recognition.summary import (
    build_screen_context,
    detect_completion_candidates,
    infer_activity_tags,
    summarize_screen_session,
)
from openmy.utils.time import iso_at


def enrich_scene_with_screen_context(
    scene: SceneBlock,
    sessions: list[ScreenSession],
    settings: ScreenContextSettings | None = None,
) -> SceneBlock:
    current_settings = settings or ScreenContextSettings()
    filtered = apply_privacy_filters(sessions, current_settings)
    for session in filtered:
        session.tags = session.tags or infer_activity_tags(
            session.app_name,
            session.window_name,
            session.url_domain,
            session.text,
        )
        session.summary = session.summary or summarize_screen_session(session)
        session.completion_candidates = session.completion_candidates or detect_completion_candidates(session)

    scene.screen_sessions = filtered
    scene.screen_context = build_screen_context(filtered, current_settings)
    return scene


def enrich_scenes_with_screen_context(
    scenes: list[SceneBlock],
    provider,
    date_str: str | None = None,
    settings: ScreenContextSettings | None = None,
) -> list[SceneBlock]:
    if not provider or not date_str:
        return scenes

    current_settings = settings or ScreenContextSettings()
    if not provider.is_available():
        return scenes

    for scene in scenes:
        if not scene.time_start:
            continue
        start_iso = iso_at(date_str, scene.time_start)
        end_clock = scene.time_end or scene.time_start
        end_iso = iso_at(date_str, end_clock, seconds=59)
        events = provider.fetch_ocr(start_iso, end_iso)
        sessions = align_scene_sessions(scene, sessionize_screen_events(events), date_str)
        enrich_scene_with_screen_context(scene, sessions, current_settings)
    return scenes
