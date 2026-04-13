from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any
from urllib import error, request

from openmy.providers.export.base import ExportProvider
from openmy.utils.time import iso_at
from openmy.utils.errors import FriendlyCliError, doc_url

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
            raise FriendlyCliError(
                "缺少 Notion 的 API key（访问口令），现在没法导出。",
                code="notion_key_missing",
                fix='先把 `NOTION_API_KEY` 写进配置里，再重试。',
                doc_url=doc_url("readme"),
                message_en="Notion export is missing NOTION_API_KEY.",
                fix_en="Add NOTION_API_KEY to the configuration, then retry.",
            )
        if not self.database_id:
            raise FriendlyCliError(
                "缺少 Notion 数据库编号，现在没法导出。",
                code="notion_database_missing",
                fix='先把 `NOTION_DATABASE_ID` 写进配置里，再重试。',
                doc_url=doc_url("readme"),
                message_en="Notion export is missing NOTION_DATABASE_ID.",
                fix_en="Add NOTION_DATABASE_ID to the configuration, then retry.",
            )

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
                    last_error = FriendlyCliError(
                        f"Notion 这次回了临时鉴权或限流错误：{detail or exc.reason}",
                        code="notion_retryable_http_error",
                        fix="等两秒再试；如果一直复现，就检查 token 和分享权限。",
                        doc_url=doc_url("readme"),
                        message_en=f"Notion returned a temporary auth or rate-limit error: {detail or exc.reason}",
                        fix_en="Wait two seconds and retry. If it keeps failing, check the token and sharing permissions.",
                    )
                    continue
                raise FriendlyCliError(
                    f"Notion 请求失败：{detail or exc.reason}",
                    code="notion_http_error",
                    fix="先检查 token、数据库分享权限和网络，再重试。",
                    doc_url=doc_url("readme"),
                    message_en=f"Notion request failed: {detail or exc.reason}",
                    fix_en="Check the token, database sharing permissions, and network connection, then retry.",
                ) from exc
            except error.URLError as exc:  # pragma: no cover - network path
                last_error = FriendlyCliError(
                    f"Notion 请求没发出去：{exc.reason}",
                    code="notion_network_error",
                    fix="先确认这台机器能连外网，再重试。",
                    doc_url=doc_url("readme"),
                    message_en=f"Notion request failed: {exc.reason}",
                    fix_en="Confirm this machine can reach the internet, then retry.",
                )
                if attempt == 0:
                    time.sleep(2)
                    continue
                raise last_error from exc
        if last_error is not None:
            raise last_error
        raise FriendlyCliError(
            "Notion 请求失败了，但没拿到更具体的错误。",
            code="notion_request_failed",
            fix="先稍后再试；如果还是失败，就检查 token 和数据库权限。",
            doc_url=doc_url("readme"),
            message_en="The Notion request failed without a more specific error.",
            fix_en="Retry later. If it still fails, check the token and database permissions.",
        )

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
