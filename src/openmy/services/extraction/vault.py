"""Obsidian Vault 分发：将提取结果写入 Vault 目录结构。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from openmy.utils.time import iso_at


def distribute_to_vault(data: dict, date: str, vault_path: str):
    from openmy.services.extraction.extractor import build_legacy_compatible_payload

    compat_payload = build_legacy_compatible_payload(data)
    vault = Path(vault_path)

    event_dir = vault / "系统" / "事件流" / date
    event_dir.mkdir(parents=True, exist_ok=True)
    event_file = event_dir / "context.jsonl"

    events = compat_payload.get("events", [])
    existing_event_lines = set(event_file.read_text(encoding="utf-8").splitlines()) if event_file.exists() else set()
    new_event_lines: list[str] = []
    for event in events:
        entry = {
            "time": iso_at(date, str(event.get("time", "00:00") or "00:00")),
            "actor": "context",
            "project": event.get("project", ""),
            "type": "口述记录",
            "summary": event.get("summary", ""),
        }
        line = json.dumps(entry, ensure_ascii=False)
        if line in existing_event_lines:
            continue
        existing_event_lines.add(line)
        new_event_lines.append(line)
    if new_event_lines:
        with open(event_file, "a", encoding="utf-8") as fh:
            fh.write("\n".join(new_event_lines) + "\n")
        print(f"✓ 事件流: {len(new_event_lines)} 条 → {event_file}", file=sys.stderr)

    summary = compat_payload.get("daily_summary", "")
    if summary:
        log_dir = vault / "日志"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{date}-上下文.md"
        content = f"# {date} 上下文摘要\n\n{summary}\n"

        decisions = compat_payload.get("decisions", [])
        if decisions:
            content += "\n## 决策\n\n"
            for item in decisions:
                proj = f"【{item['project']}】" if item.get("project") else ""
                content += f"- {proj}{item.get('what', '')}"
                if item.get("why"):
                    content += f"（{item['why']}）"
                content += "\n"

        todos = compat_payload.get("todos", [])
        if todos:
            content += "\n## 待办\n\n"
            for item in todos:
                prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    item.get("priority", "medium"),
                    "🟡",
                )
                proj = f"【{item['project']}】" if item.get("project") else ""
                content += f"- {prio} {proj}{item.get('task', '')}\n"

        insights = compat_payload.get("insights", [])
        if insights:
            content += "\n## 洞察\n\n"
            for item in insights:
                content += f"- **{item.get('topic', '')}**: {item.get('content', '')}\n"

        log_file.write_text(content, encoding="utf-8")
        print(f"✓ 日志摘要: {log_file}", file=sys.stderr)

    inbox_file = vault / "收件箱" / "灵感速记.md"
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    inbox_appends: list[str] = []
    existing_inbox_lines = set(inbox_file.read_text(encoding="utf-8").splitlines()) if inbox_file.exists() else set()

    for todo in compat_payload.get("todos", []):
        prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(todo.get("priority", "medium"), "🟡")
        proj = f"[{todo['project']}] " if todo.get("project") else ""
        line = f"- [ ] {prio} {proj}{todo.get('task', '')} _{date}_"
        if line not in existing_inbox_lines:
            existing_inbox_lines.add(line)
            inbox_appends.append(line)

    for insight in compat_payload.get("insights", []):
        line = f"- 💡 **{insight.get('topic', '')}**: {insight.get('content', '')} _{date}_"
        if line not in existing_inbox_lines:
            existing_inbox_lines.add(line)
            inbox_appends.append(line)

    if inbox_appends:
        with open(inbox_file, "a", encoding="utf-8") as fh:
            fh.write("\n" + "\n".join(inbox_appends) + "\n")
        print(f"✓ 收件箱同步: {len(inbox_appends)} 条 → {inbox_file}", file=sys.stderr)

    decisions = compat_payload.get("decisions", [])
    if decisions:
        decision_file = vault / "日志" / "决策复盘库.md"
        decision_file.parent.mkdir(parents=True, exist_ok=True)
        if not decision_file.exists():
            decision_file.write_text("# 决策复盘库\n\n", encoding="utf-8")
        existing_decision_lines = set(decision_file.read_text(encoding="utf-8").splitlines())
        new_decision_lines: list[str] = []

        for item in decisions:
            proj = f"【{item['project']}】" if item.get("project") else ""
            line = f"- **{date}** {proj}{item.get('what', '')} （{item.get('why', '')}）"
            if line not in existing_decision_lines:
                existing_decision_lines.add(line)
                new_decision_lines.append(line)
        if new_decision_lines:
            with open(decision_file, "a", encoding="utf-8") as fh:
                fh.write("\n".join(new_decision_lines) + "\n")
            print(f"✓ 决策复盘同步: {len(new_decision_lines)} 条", file=sys.stderr)

    todos = compat_payload.get("todos", [])
    if todos:
        print("\n📋 提取到的待办事项：", file=sys.stderr)
        for item in todos:
            prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(item.get("priority", "medium"), "🟡")
            proj = f"[{item['project']}] " if item.get("project") else ""
            print(f"  {prio} {proj}{item.get('task', '')}", file=sys.stderr)
