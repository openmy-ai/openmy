from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any
from urllib import error, request

from openmy.providers.export.base import ExportProvider
from openmy.utils.time import iso_at

NOTION_VERSION = "2025-09-03"
NOTION_API_BASE = "https://api.notion.com/v1"


class NotionExportProvider(ExportProvider):
    name = "notion"

    def __init__(self, *, config: dict[str, Any]):
        super().__init__(config=config)
        self.api_key = str(config.get("api_key", "") or "").strip()
        self.database_id = str(config.get("database_id", "") or "").strip()
        self.timeout = int(config.get("timeout", 30) or 30)

    def _require_config(self) -> None:
        if not self.api_key:
            raise RuntimeError("Notion export missing NOTION_API_KEY.")
        if not self.database_id:
            raise RuntimeError("Notion export missing NOTION_DATABASE_ID.")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def _request_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        # 坑 1：创建页面时用 database_id，不是 data_source_id。
        # 坑 2：Notion 有时限流会回 401，不是 token 过期；这里要等 2 秒再试。
        # 坑 3：数据库必须手动授权给 integration，否则会回 404。
        # 坑 4：Notion-Version header 必须显式填写。
        # 坑 5：请求之间要留 1-2 秒间隔，避免连发限流。
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(2):
            time.sleep(1 if attempt == 0 else 2)
            req = request.Request(
                f"{NOTION_API_BASE}{path}",
                data=body,
                headers=self._headers(),
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except error.HTTPError as exc:  # pragma: no cover - network path
                detail = exc.read().decode("utf-8", errors="ignore")
                if exc.code == 401 and attempt == 0:
                    last_error = RuntimeError(f"Notion temporary auth/rate-limit response: {detail or exc.reason}")
                    continue
                raise RuntimeError(f"Notion request failed: {detail or exc.reason}") from exc
            except error.URLError as exc:  # pragma: no cover - network path
                last_error = RuntimeError(f"Notion request failed: {exc.reason}")
                if attempt == 0:
                    time.sleep(2)
                    continue
                raise last_error from exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("Notion request failed.")

    def _notion_timestamp(self, date: str) -> str:
        # 坑 6：日期字段要带完整时间，不能只给 YYYY-MM-DD。
        return iso_at(date, "08:00")

    def _paragraph_block(self, text: str) -> dict[str, Any]:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    def _bullet_block(self, text: str) -> dict[str, Any]:
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    def export_daily_briefing(self, date: str, briefing: dict[str, Any]) -> dict[str, Any]:
        self._require_config()
        summary = str(briefing.get("summary", "") or "无摘要").strip()
        children = [self._paragraph_block(summary)]
        for heading, items in (
            ("关键事件", briefing.get("key_events", [])),
            ("决策", briefing.get("decisions", [])),
            ("待办", briefing.get("todos_open", [])),
            ("洞察", briefing.get("insights", [])),
        ):
            cleaned_items = [str(item).strip() for item in items if str(item).strip()]
            if not cleaned_items:
                continue
            children.append(self._paragraph_block(heading))
            children.extend(self._bullet_block(item) for item in cleaned_items)

        payload = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "天": {"title": [{"text": {"content": date}}]},
                "活动日期": {"date": {"start": self._notion_timestamp(date)}},
            },
            "children": children,
        }
        data = self._request_json("/pages", payload)
        return {"url": data.get("url", ""), "page_id": data.get("id", "")}

    def export_context_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        self._require_config()
        date = datetime.now().date().isoformat()
        summary = str(snapshot.get("status_line", "") or "OpenMy context snapshot").strip()
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "天": {"title": [{"text": {"content": f"Context {date}"}}]},
                "活动日期": {"date": {"start": self._notion_timestamp(date)}},
            },
            "children": [self._paragraph_block(summary)],
        }
        data = self._request_json("/pages", payload)
        return {"url": data.get("url", ""), "page_id": data.get("id", "")}
