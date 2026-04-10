from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass
class ScreenEvent:
    app_name: str = ""
    window_name: str = ""
    timestamp: str = ""
    frame_id: int = 0
    text: str = ""
    url: str = ""


class ScreenRecognitionClient:
    def __init__(self, base_url: str = "http://localhost:3030", timeout: int = 2):
        self.base_url = base_url
        self.timeout = timeout

    def is_available(self) -> bool:
        """GET /health, 返回 True/False，不抛异常。"""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            return resp.status == 200
        except Exception:
            return False

    def search_ocr(
        self,
        start_time: str,
        end_time: str,
        app_name: str | None = None,
        limit: int = 100,
    ) -> list[ScreenEvent]:
        """GET /search?content_type=ocr&...，失败返回空列表。"""
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

    def activity_summary(self, start_time: str, end_time: str) -> dict:
        """GET /activity-summary — 时段内的应用使用摘要。"""
        params = {"start_time": start_time, "end_time": end_time}
        try:
            req = urllib.request.Request(f"{self.base_url}/activity-summary?{urlencode(params)}")
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return {}

    def search_elements(self, start_time: str, end_time: str, limit: int = 50) -> list[dict]:
        """GET /elements — UI 元素搜索。"""
        params = {"start_time": start_time, "end_time": end_time, "limit": limit}
        try:
            req = urllib.request.Request(f"{self.base_url}/elements?{urlencode(params)}")
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("data", [])
        except Exception:
            return []

    def get_memories(self, limit: int = 20) -> list[dict]:
        """GET /memories — 用户记忆列表。"""
        params = {"limit": limit, "order_by": "created_at", "order_dir": "desc"}
        try:
            req = urllib.request.Request(f"{self.base_url}/memories?{urlencode(params)}")
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []
