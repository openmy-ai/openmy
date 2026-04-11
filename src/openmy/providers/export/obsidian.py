from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openmy.providers.export.base import ExportProvider


class ObsidianExportProvider(ExportProvider):
    name = "obsidian"

    def __init__(self, *, config: dict[str, Any]):
        super().__init__(config=config)
        self.vault_path = Path(str(config.get("vault_path", "") or "")).expanduser() if config.get("vault_path") else None

    def _require_vault(self) -> Path:
        if not self.vault_path:
            raise RuntimeError("Obsidian export missing vault_path.")
        self.vault_path.mkdir(parents=True, exist_ok=True)
        return self.vault_path

    def _render_frontmatter(self, date: str) -> str:
        return "\n".join([
            "---",
            f"date: {date}",
            "tags:",
            "  - openmy",
            "  - daily-briefing",
            "source: openmy",
            "---",
            "",
        ])

    def _render_briefing_markdown(self, date: str, briefing: dict[str, Any]) -> str:
        parts = [
            f"# OpenMy 日报 {date}",
            "",
            str(briefing.get("summary", "") or "无摘要").strip(),
            "",
        ]
        key_events = [str(item).strip() for item in briefing.get("key_events", []) if str(item).strip()]
        if key_events:
            parts.extend(["## 关键事件", ""])
            parts.extend([f"- {item}" for item in key_events])
            parts.append("")

        decisions = [str(item).strip() for item in briefing.get("decisions", []) if str(item).strip()]
        if decisions:
            parts.extend(["## 决策", ""])
            parts.extend([f"- {item}" for item in decisions])
            parts.append("")

        todos = [str(item).strip() for item in briefing.get("todos_open", []) if str(item).strip()]
        if todos:
            parts.extend(["## 待办", ""])
            parts.extend([f"- {item}" for item in todos])
            parts.append("")

        insights = [str(item).strip() for item in briefing.get("insights", []) if str(item).strip()]
        if insights:
            parts.extend(["## 洞察", ""])
            parts.extend([f"- {item}" for item in insights])
            parts.append("")

        return "\n".join(parts).rstrip() + "\n"

    def export_daily_briefing(self, date: str, briefing: dict[str, Any]) -> dict[str, Any]:
        vault = self._require_vault()
        target = vault / f"{date}-OpenMy日报.md"
        body = self._render_briefing_markdown(date, briefing)
        if target.exists():
            stamp = datetime.now().astimezone().isoformat(timespec="seconds")
            with target.open("a", encoding="utf-8") as handle:
                handle.write(f"\n---\n\n## OpenMy 再次导入 {stamp}\n\n")
                handle.write(body)
            mode = "append"
        else:
            target.write_text(self._render_frontmatter(date) + body, encoding="utf-8")
            mode = "create"
        return {"path": str(target), "mode": mode}

    def export_context_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        vault = self._require_vault()
        target = vault / "OpenMy-近况快照.md"
        status_line = str(snapshot.get("status_line", "") or "").strip()
        content = "\n".join([
            "---",
            "source: openmy",
            "tags:",
            "  - openmy",
            "  - context-snapshot",
            "---",
            "",
            "# OpenMy 近况快照",
            "",
            status_line or "暂无状态摘要",
            "",
        ])
        target.write_text(content, encoding="utf-8")
        return {"path": str(target), "mode": "overwrite"}
