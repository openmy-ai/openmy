from __future__ import annotations

from typing import Any


class ExportProvider:
    name = "unknown"

    def __init__(self, *, config: dict[str, Any]):
        self.config = config

    def export_daily_briefing(self, date: str, briefing: dict[str, Any]) -> dict[str, Any]:
        """导出日报，返回路径或链接等元数据。"""
        raise NotImplementedError

    def export_context_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """导出近况快照，返回路径或链接等元数据。"""
        raise NotImplementedError
