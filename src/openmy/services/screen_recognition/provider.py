from __future__ import annotations

from openmy.services.screen_recognition.settings import ScreenContextSettings


class ScreenContextProvider:
    def __init__(self, client=None, settings: ScreenContextSettings | None = None):
        self.client = client
        self.settings = settings or ScreenContextSettings()

    def is_enabled(self) -> bool:
        return bool(self.settings.enabled and self.settings.participation_mode != "off")

    def is_available(self) -> bool:
        if not self.is_enabled() or not self.client:
            return False
        try:
            return bool(self.client.is_available())
        except Exception:
            return False

    def fetch_ocr(self, start_time: str, end_time: str, app_name: str | None = None, limit: int = 100):
        if not self.is_available():
            return []
        try:
            return list(self.client.search_ocr(start_time, end_time, app_name=app_name, limit=limit))
        except Exception:
            return []

    def fetch_elements(self, start_time: str, end_time: str, limit: int = 50):
        if not self.is_available():
            return []
        try:
            return list(self.client.search_elements(start_time, end_time, limit=limit))
        except Exception:
            return []

    def fetch_activity_summary(self, start_time: str, end_time: str) -> dict:
        if not self.is_available():
            return {}
        try:
            return dict(self.client.activity_summary(start_time, end_time))
        except Exception:
            return {}
