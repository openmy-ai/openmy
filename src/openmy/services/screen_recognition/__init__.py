"""屏幕上下文服务。"""

from openmy.services.screen_recognition.capture_engine import (
    capture_once,
    daemon_running,
    is_capture_supported,
    read_status,
    run_capture_loop,
    start_capture_daemon,
    stop_capture_daemon,
)
from openmy.services.screen_recognition.capture_store import (
    activity_summary,
    query_events,
    search_elements,
)
from openmy.services.screen_recognition.settings import (
    ScreenContextSettings,
    load_screen_context_settings,
)

__all__ = [
    "ScreenContextSettings",
    "activity_summary",
    "capture_once",
    "daemon_running",
    "is_capture_supported",
    "load_screen_context_settings",
    "query_events",
    "read_status",
    "run_capture_loop",
    "search_elements",
    "start_capture_daemon",
    "stop_capture_daemon",
]
