from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from openmy.services.screen_recognition.capture import (
    activity_summary as local_activity_summary,
    daemon_running,
    is_capture_supported,
    query_events,
    read_status,
    search_elements as local_search_elements,
)


@dataclass
class ScreenEvent:
    app_name: str = ""
    window_name: str = ""
    timestamp: str = ""
    frame_id: int = 0
    text: str = ""
    url: str = ""


class ScreenRecognitionClient:
    def __init__(self, base_url: str | None = None, timeout: int = 2, data_root: str | Path | None = None):
        self.base_url = (base_url or "").strip()
        self.timeout = timeout
        self.data_root = Path(data_root).expanduser() if data_root else None
        self._use_http = self.base_url.startswith(("http://", "https://"))

    def is_available(self) -> bool:
        """本地模式看能力和本地数据；兼容旧的 HTTP 模式。"""
        if self._use_http:
            try:
                req = urllib.request.Request(f"{self.base_url}/health")
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                return resp.status == 200
            except Exception:
                return False
        if not is_capture_supported():
            return False
        if daemon_running(self.data_root):
            return True
        status = read_status(self.data_root)
        return bool(status.last_capture_at)

    def daemon_running(self) -> bool:
        if self._use_http:
            return self.is_available()
        return daemon_running(self.data_root)

    def search_ocr(
        self,
        start_time: str,
        end_time: str,
        app_name: str | None = None,
        limit: int = 100,
    ) -> list[ScreenEvent]:
        if self._use_http:
            params = {
                "content_type": "ocr",
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            }
            if app_name:
                params["app_name"] = app_name

            try:
                req = urllib.request.Request(f"{self.base_url}/search?{urlencode(params)}")
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                data = json.loads(resp.read().decode("utf-8"))
                events: list[ScreenEvent] = []
                for item in data.get("data", []):
                    content = item.get("content", {})
                    events.append(
                        ScreenEvent(
                            app_name=content.get("app_name", ""),
                            window_name=content.get("window_name", ""),
                            timestamp=content.get("timestamp", ""),
                            frame_id=content.get("frame_id", 0),
                            text=content.get("text", "")[:200],
                            url=content.get("browser_url", "") or "",
                        )
                    )
                return events
            except Exception:
                return []

        try:
            return [
                ScreenEvent(
                    app_name=item.app_name,
                    window_name=item.window_name,
                    timestamp=item.timestamp,
                    frame_id=item.frame_id,
                    text=item.text[:200],
                    url=item.browser_url,
                )
                for item in query_events(
                    start_time,
                    end_time,
                    data_root=self.data_root,
                    app_name=app_name,
                    limit=limit,
                )
            ]
        except Exception:
            return []

    def activity_summary(self, start_time: str, end_time: str) -> dict:
        if self._use_http:
            params = {"start_time": start_time, "end_time": end_time}
            try:
                req = urllib.request.Request(f"{self.base_url}/activity-summary?{urlencode(params)}")
                resp = urllib.request.urlopen(req, timeout=30)
                return json.loads(resp.read().decode("utf-8"))
            except Exception:
                return {}
        try:
            return local_activity_summary(start_time, end_time, data_root=self.data_root)
        except Exception:
            return {}

    def search_elements(self, start_time: str, end_time: str, limit: int = 50) -> list[dict]:
        if self._use_http:
            params = {"start_time": start_time, "end_time": end_time, "limit": limit}
            try:
                req = urllib.request.Request(f"{self.base_url}/elements?{urlencode(params)}")
                resp = urllib.request.urlopen(req, timeout=10)
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data", [])
            except Exception:
                return []
        try:
            return local_search_elements(start_time, end_time, data_root=self.data_root, limit=limit)
        except Exception:
            return []

    def get_memories(self, limit: int = 20) -> list[dict]:
        if not self._use_http:
            return []
        params = {"limit": limit, "order_by": "created_at", "order_dir": "desc"}
        try:
            req = urllib.request.Request(f"{self.base_url}/memories?{urlencode(params)}")
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []
