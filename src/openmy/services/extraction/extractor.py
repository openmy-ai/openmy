#!/usr/bin/env python3
"""
extract.py — 从每日上下文转写中提取结构化摘要

新输出主结构：
  - daily_summary
  - events
  - intents
  - facts
  - role_hints

同时保留旧字段兼容层：
  - legacy_todos
  - todos
  - decisions
  - insights
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openmy.domain.intent import DueDate, Fact, Intent

try:
    from google import genai
except ImportError:  # pragma: no cover - 本地缺依赖时给测试留钩子
    class _GenAIStub:
        Client = None

    genai = _GenAIStub()


from openmy.config import GEMINI_MODEL, EXTRACT_TEMPERATURE, EXTRACT_THINKING_LEVEL
CN_NUMBER_MAP = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
TIME_COLON_RE = re.compile(r"(?P<hour>\d{1,2})[:：](?P<minute>\d{2})")
TIME_POINT_RE = re.compile(
    r"(?P<hour>[零〇一二两三四五六七八九十\d]{1,3})(?:点|时)(?:(?P<minute>[零〇一二两三四五六七八九十\d]{1,2})分?)?(?P<half>半)?"
)

EXTRACT_PROMPT = """你是 OpenMy 的结构化提取器，要把一天的口述转写拆成“未来约束”和“已经发生/已经知道”的两类信息。

规则：
1. intent 只收真正会影响后续行动的内容：
   - action_item：明确要做的事
   - commitment：明确答应要做的事
   - open_question：明确还没定、需要后续判断的问题
   - decision：已经做出的关键决定
2. fact 只收已经发生、已经观察到、已经想明白的内容：
   - observation / idea / preference / relation / project_update
3. 不要把下面这些升格成 intent：
   - 吃什么、买了什么、小额消费、随口吐槽、生活碎片
   - 没有未来约束力的感慨
   - 只是聊过，但没有形成后续动作或正式决定
4. who 是一个对象，不是散文本。可选 kind：
   user / agent / other_person / shared / unclear
5. confidence_label 只用 high / medium / low。
6. 输出必须是纯 JSON，不能带 markdown 代码块。

输出 schema：
{
  "daily_summary": "三句以内的人话总结",
  "events": [{"time": "HH:MM", "project": "项目名", "summary": "一句话"}],
  "intents": [
    {
      "intent_id": "intent_xxx",
      "kind": "action_item|commitment|open_question|decision",
      "what": "内容",
      "status": "open|active|done",
      "who": {"kind": "user|agent|other_person|shared|unclear", "label": "执行者"},
      "confidence_label": "high|medium|low",
      "confidence_score": 0.0,
      "needs_review": false,
      "evidence_quote": "原话片段",
      "source_scene_id": "scene_xxx",
      "topic": "主题",
      "speech_act": "self_instruction|delegation|question|decision",
      "due": {"raw_text": "", "iso_date": "", "granularity": "none|day|time"},
      "project_hint": "项目名",
      "source_recording_id": ""
    }
  ],
  "facts": [
    {
      "fact_type": "observation|idea|preference|relation|project_update",
      "content": "内容",
      "topic": "主题",
      "confidence_label": "high|medium|low",
      "confidence_score": 0.0,
      "source_scene_id": "scene_xxx"
    }
  ],
  "role_hints": [
    {"time": "HH:MM", "role": "伴侣|家人|朋友|商家|AI|宠物|自己|未确定", "basis": "explicit|inferred", "confidence": 0.0, "evidence": "一句话依据"}
  ]
}
"""


def _parse_reference_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_chinese_number(token: str) -> int | None:
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token == "十":
        return 10
    if "十" in token:
        left, right = token.split("十", 1)
        tens = 1 if not left else CN_NUMBER_MAP.get(left)
        ones = 0 if not right else CN_NUMBER_MAP.get(right)
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    if len(token) == 1:
        return CN_NUMBER_MAP.get(token)
    return None


def _extract_relative_day_offset(raw_text: str) -> int | None:
    if not raw_text:
        return None
    if "大后天" in raw_text:
        return 3
    if "后天" in raw_text or "后日" in raw_text:
        return 2
    if "明天" in raw_text or "明日" in raw_text:
        return 1
    if any(keyword in raw_text for keyword in ("今天", "今日", "今晚", "今早", "今晨", "今下午", "今上午")):
        return 0
    return None


def _extract_time_parts(raw_text: str) -> tuple[int, int] | None:
    colon_match = TIME_COLON_RE.search(raw_text)
    if colon_match:
        return int(colon_match.group("hour")), int(colon_match.group("minute"))

    point_match = TIME_POINT_RE.search(raw_text)
    if not point_match:
        return None

    hour = _parse_chinese_number(point_match.group("hour"))
    minute_token = point_match.group("minute")
    minute = _parse_chinese_number(minute_token) if minute_token else 0
    if point_match.group("half"):
        minute = 30
    if hour is None or minute is None:
        return None

    if any(keyword in raw_text for keyword in ("下午", "晚上", "傍晚", "今晚")) and 1 <= hour < 12:
        hour += 12
    elif "中午" in raw_text and 1 <= hour < 11:
        hour += 12
    elif any(keyword in raw_text for keyword in ("凌晨",)) and hour == 12:
        hour = 0

    return hour, minute


def _resolve_relative_due(raw_text: str, reference_date: str | None) -> tuple[str, str] | None:
    base_date = _parse_reference_date(reference_date)
    offset = _extract_relative_day_offset(raw_text)
    if base_date is None or offset is None:
        return None

    target_date = base_date + timedelta(days=offset)
    time_parts = _extract_time_parts(raw_text)
    if time_parts is None:
        return target_date.isoformat(), "day"

    hour, minute = time_parts
    target_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hour, minute=minute)
    return target_dt.strftime("%Y-%m-%dT%H:%M:%S"), "time"


def _normalize_due_date(due: DueDate, reference_date: str | None) -> DueDate:
    resolved = _resolve_relative_due(due.raw_text, reference_date)
    if not resolved:
        return due
    iso_date, granularity = resolved
    return DueDate(raw_text=due.raw_text, iso_date=iso_date, granularity=granularity)


def _build_extract_prompt(text: str, reference_date: str | None) -> str:
    if reference_date:
        date_hint = (
            f"\n\n时间基准：\n"
            f"- 今天这批录音对应的基准日期是 {reference_date}（Asia/Shanghai）。\n"
            f"- 像“今天 / 明天 / 后天 / 今晚 / 明天下午三点”这类相对时间，必须相对于这个基准日期解释。\n"
            f"- 如果无法可靠换算成公历时间，`due.iso_date` 留空，不要编造历史日期或随便猜一个旧日期。"
        )
    else:
        date_hint = ""
    return f"{EXTRACT_PROMPT}{date_hint}\n\n以下是今天的录音转写：\n\n{text}"


def _strip_code_fences(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_response_text(response: Any) -> str:
    text = getattr(response, "text", "") or ""
    if text:
        return text

    candidates = getattr(response, "candidates", None) or []
    try:
        return str(candidates[0].content.parts[0].text or "")
    except Exception:
        return ""


def _intent_priority(intent: Intent) -> str:
    if intent.confidence_label == "high":
        return "high"
    if intent.confidence_label == "low":
        return "low"
    return "medium"


def _intent_project(intent: Intent) -> str:
    return intent.project_hint.strip() or intent.topic.strip()


def _should_surface_as_legacy_todo(intent: Intent) -> bool:
    if intent.kind not in {"action_item", "commitment"}:
        return False
    if intent.status in {"done", "closed", "abandoned", "cancelled", "rejected"}:
        return False
    if intent.confidence_label == "low" or intent.confidence_score < 0.5:
        return False
    return intent.who.kind in {"user", "shared", "unclear"}


def _legacy_todos_from_intents(intents: list[Intent]) -> list[dict[str, Any]]:
    todos: list[dict[str, Any]] = []
    seen: set[str] = set()

    for intent in intents:
        if not _should_surface_as_legacy_todo(intent):
            continue
        task = intent.what.strip()
        if not task or task in seen:
            continue
        seen.add(task)
        todos.append(
            {
                "task": task,
                "priority": _intent_priority(intent),
                "project": _intent_project(intent),
            }
        )
    return todos


def _decisions_from_intents(intents: list[Intent]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for intent in intents:
        if intent.kind != "decision":
            continue
        what = intent.what.strip()
        if not what or what in seen:
            continue
        seen.add(what)
        decisions.append(
            {
                "project": _intent_project(intent),
                "what": what,
                "why": intent.evidence_quote.strip(),
            }
        )
    return decisions


def _insights_from_facts(facts: list[Fact]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    seen: set[str] = set()

    for fact in facts:
        content = fact.content.strip()
        if not content or content in seen:
            continue
        seen.add(content)
        insights.append(
            {
                "topic": fact.topic.strip() or fact.fact_type.strip() or "事实",
                "content": content,
            }
        )
    return insights


def normalize_extraction_payload(data: dict[str, Any], reference_date: str | None = None) -> dict[str, Any]:
    payload = dict(data if isinstance(data, dict) else {})

    events = []
    for raw in payload.get("events", []):
        if not isinstance(raw, dict):
            continue
        events.append(
            {
                "time": str(raw.get("time", "") or ""),
                "project": str(raw.get("project", "") or ""),
                "summary": str(raw.get("summary", "") or ""),
            }
        )

    intents = [
        Intent.from_dict(raw)
        for raw in payload.get("intents", [])
        if isinstance(raw, dict)
    ]
    intents = [
        Intent(
            intent_id=intent.intent_id,
            kind=intent.kind,
            what=intent.what,
            status=intent.status,
            who=intent.who,
            confidence_label=intent.confidence_label,
            confidence_score=intent.confidence_score,
            needs_review=intent.needs_review,
            evidence_quote=intent.evidence_quote,
            source_scene_id=intent.source_scene_id,
            topic=intent.topic,
            speech_act=intent.speech_act,
            due=_normalize_due_date(intent.due, reference_date),
            project_hint=intent.project_hint,
            source_recording_id=intent.source_recording_id,
        )
        for intent in intents
    ]
    facts = [
        Fact.from_dict(raw)
        for raw in payload.get("facts", [])
        if isinstance(raw, dict)
    ]

    payload["daily_summary"] = str(payload.get("daily_summary", "") or "")
    payload["events"] = events
    payload["intents"] = [intent.to_dict() for intent in intents]
    payload["facts"] = [fact.to_dict() for fact in facts]
    payload["role_hints"] = [
        item for item in payload.get("role_hints", []) if isinstance(item, dict)
    ]
    return payload


def build_legacy_compatible_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = normalize_extraction_payload(data)
    intents = [Intent.from_dict(item) for item in payload.get("intents", [])]
    facts = [Fact.from_dict(item) for item in payload.get("facts", [])]

    compat = dict(payload)
    if intents:
        legacy_todos = _legacy_todos_from_intents(intents)
        compat["legacy_todos"] = legacy_todos
        compat["todos"] = legacy_todos
        compat["decisions"] = _decisions_from_intents(intents)
    else:
        legacy_todos = [
            item for item in data.get("legacy_todos", data.get("todos", [])) if isinstance(item, dict)
        ]
        compat["legacy_todos"] = legacy_todos
        compat["todos"] = [item for item in data.get("todos", legacy_todos) if isinstance(item, dict)]
        compat["decisions"] = [item for item in data.get("decisions", []) if isinstance(item, dict)]

    if facts:
        compat["insights"] = _insights_from_facts(facts)
    else:
        compat["insights"] = [item for item in data.get("insights", []) if isinstance(item, dict)]

    return compat


# ── 提取输出的 JSON Schema（传给 Gemini API 做结构化约束）──────────
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "daily_summary": {"type": "string", "description": "三句以内的人话总结"},
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": {"type": "string"},
                    "project": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["time", "project", "summary"],
            },
        },
        "intents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "intent_id": {"type": "string"},
                    "kind": {"type": "string", "enum": ["action_item", "commitment", "open_question", "decision"]},
                    "what": {"type": "string"},
                    "status": {"type": "string", "enum": ["open", "active", "done"]},
                    "who": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["user", "agent", "other_person", "shared", "unclear"]},
                            "label": {"type": "string"},
                        },
                        "required": ["kind", "label"],
                    },
                    "confidence_label": {"type": "string", "enum": ["high", "medium", "low"]},
                    "confidence_score": {"type": "number"},
                    "needs_review": {"type": "boolean"},
                    "evidence_quote": {"type": "string"},
                    "source_scene_id": {"type": "string"},
                    "topic": {"type": "string"},
                    "speech_act": {"type": "string", "enum": ["self_instruction", "delegation", "question", "decision"]},
                    "due": {
                        "type": "object",
                        "properties": {
                            "raw_text": {"type": "string"},
                            "iso_date": {"type": "string"},
                            "granularity": {"type": "string", "enum": ["none", "day", "time"]},
                        },
                        "required": ["raw_text", "iso_date", "granularity"],
                    },
                    "project_hint": {"type": "string"},
                    "source_recording_id": {"type": "string"},
                },
                "required": ["intent_id", "kind", "what", "status", "who", "confidence_label", "confidence_score",
                             "needs_review", "evidence_quote", "source_scene_id", "topic", "speech_act", "due",
                             "project_hint", "source_recording_id"],
            },
        },
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact_type": {"type": "string", "enum": ["observation", "idea", "preference", "relation", "project_update"]},
                    "content": {"type": "string"},
                    "topic": {"type": "string"},
                    "confidence_label": {"type": "string", "enum": ["high", "medium", "low"]},
                    "confidence_score": {"type": "number"},
                    "source_scene_id": {"type": "string"},
                },
                "required": ["fact_type", "content", "topic", "confidence_label", "confidence_score", "source_scene_id"],
            },
        },
        "role_hints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": {"type": "string"},
                    "role": {"type": "string"},
                    "basis": {"type": "string", "enum": ["explicit", "inferred"]},
                    "confidence": {"type": "number"},
                    "evidence": {"type": "string"},
                },
                "required": ["time", "role", "basis", "confidence", "evidence"],
            },
        },
    },
    "required": ["daily_summary", "events", "intents", "facts", "role_hints"],
}


def call_gemini(text: str, api_key: str, model: str = GEMINI_MODEL, reference_date: str | None = None) -> dict | None:
    """调 Gemini API 提取结构化数据。"""
    if getattr(genai, "Client", None) is None:
        print("Gemini SDK 不可用：缺少 google-genai", file=sys.stderr)
        return None

    client = genai.Client(api_key=api_key)
    prompt = _build_extract_prompt(text, reference_date)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "temperature": EXTRACT_TEMPERATURE,
                "response_mime_type": "application/json",
                "response_json_schema": EXTRACTION_SCHEMA,
                "thinking_config": {"thinking_level": EXTRACT_THINKING_LEVEL},
            },
        )
    except Exception as exc:
        print(f"Gemini 请求失败: {exc}", file=sys.stderr)
        return None

    raw_text = _strip_code_fences(_extract_response_text(response))
    if not raw_text:
        print("解析 Gemini 响应失败: 空响应", file=sys.stderr)
        return None

    try:
        return normalize_extraction_payload(json.loads(raw_text), reference_date=reference_date)
    except json.JSONDecodeError as exc:
        print(f"解析 Gemini 响应失败: {exc}", file=sys.stderr)
        print(raw_text[:500], file=sys.stderr)
        return None


def save_meta_json(data: dict, date: str, output_dir: str):
    """保存结构化数据为 .meta.json，同时补旧字段兼容层。"""
    meta_path = Path(output_dir) / f"{date}.meta.json"
    compat_payload = build_legacy_compatible_payload(data)
    meta_path.write_text(
        json.dumps(compat_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✓ 结构化数据: {meta_path}", file=sys.stderr)


def distribute_to_vault(data: dict, date: str, vault_path: str):
    """分发提取结果到 Obsidian Vault。"""
    compat_payload = build_legacy_compatible_payload(data)
    vault = Path(vault_path)

    event_dir = vault / "系统" / "事件流" / date
    event_dir.mkdir(parents=True, exist_ok=True)
    event_file = event_dir / "context.jsonl"

    events = compat_payload.get("events", [])
    with open(event_file, "a", encoding="utf-8") as fh:
        for event in events:
            entry = {
                "time": f"{date}T{event.get('time', '00:00')}:00+08:00",
                "actor": "context",
                "project": event.get("project", ""),
                "type": "口述记录",
                "summary": event.get("summary", ""),
            }
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if events:
        print(f"✓ 事件流: {len(events)} 条 → {event_file}", file=sys.stderr)

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

    for todo in compat_payload.get("todos", []):
        prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(todo.get("priority", "medium"), "🟡")
        proj = f"[{todo['project']}] " if todo.get("project") else ""
        inbox_appends.append(f"- [ ] {prio} {proj}{todo.get('task', '')} _{date}_")

    for insight in compat_payload.get("insights", []):
        inbox_appends.append(f"- 💡 **{insight.get('topic', '')}**: {insight.get('content', '')} _{date}_")

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

        with open(decision_file, "a", encoding="utf-8") as fh:
            for item in decisions:
                proj = f"【{item['project']}】" if item.get("project") else ""
                entry = f"- **{date}** {proj}{item.get('what', '')} （{item.get('why', '')}）\n"
                fh.write(entry)
        print(f"✓ 决策复盘同步: {len(decisions)} 条", file=sys.stderr)

    todos = compat_payload.get("todos", [])
    if todos:
        print("\n📋 提取到的待办事项：", file=sys.stderr)
        for item in todos:
            prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(item.get("priority", "medium"), "🟡")
            proj = f"[{item['project']}] " if item.get("project") else ""
            print(f"  {prio} {proj}{item.get('task', '')}", file=sys.stderr)


def run_extraction(
    input_file: str | Path,
    *,
    date: str | None = None,
    model: str = GEMINI_MODEL,
    vault_path: str | None = None,
    api_key: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"文件不存在: {input_path}", file=sys.stderr)
        return None

    final_date = date
    if not final_date:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", input_path.stem)
        final_date = match.group(1) if match else datetime.now().strftime("%Y-%m-%d")

    final_api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not final_api_key:
        print("错误: 请设置 GEMINI_API_KEY 环境变量或使用 --api-key 参数", file=sys.stderr)
        return None

    text = input_path.read_text(encoding="utf-8")
    if "---" in text:
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()
        elif len(parts) == 2:
            text = parts[1].strip()

    print(f"📖 读取 {input_path.name}: {len(text)} 字", file=sys.stderr)
    print(f"🤖 调用 Gemini ({model}) 提取结构化摘要...", file=sys.stderr)

    data = call_gemini(text, final_api_key, model, final_date)
    if not data:
        print("❌ 提取失败", file=sys.stderr)
        return None

    normalized_payload = normalize_extraction_payload(data)
    print("✓ 提取完成", file=sys.stderr)

    if dry_run:
        return normalized_payload

    compat_payload = build_legacy_compatible_payload(normalized_payload)
    save_meta_json(compat_payload, final_date, str(input_path.parent))
    if vault_path:
        distribute_to_vault(compat_payload, final_date, vault_path)

    print(f"\n📝 每日摘要: {compat_payload.get('daily_summary', '无')}", file=sys.stderr)
    print(
        f"📊 提取: {len(compat_payload.get('events', []))} 事件 | "
        f"{len(compat_payload.get('intents', []))} 意图 | "
        f"{len(compat_payload.get('facts', []))} 事实 | "
        f"{len(compat_payload.get('todos', []))} 兼容待办",
        file=sys.stderr,
    )
    return compat_payload


def main():
    parser = argparse.ArgumentParser(description="从每日上下文转写中提取结构化摘要")
    parser.add_argument("input_file", help="清洗后的 Markdown 文件 (YYYY-MM-DD.md)")
    parser.add_argument("--date", help="日期 (YYYY-MM-DD)，默认从文件名推断")
    parser.add_argument("--model", default=GEMINI_MODEL, help=f"Gemini 模型 (默认: {GEMINI_MODEL})")
    parser.add_argument("--vault-path", help="Obsidian Vault 路径，指定后自动分发到 Vault")
    parser.add_argument("--api-key", help="Gemini API key (或设置 GEMINI_API_KEY 环境变量)")
    parser.add_argument("--dry-run", action="store_true", help="只打印提取结果，不写入文件")
    args = parser.parse_args()

    data = run_extraction(
        args.input_file,
        date=args.date,
        model=args.model,
        vault_path=args.vault_path,
        api_key=args.api_key,
        dry_run=args.dry_run,
    )
    if data is None:
        raise SystemExit(1)
    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
