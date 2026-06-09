"""时间裁定：区分过去事实和未来承诺的中文语义分析。"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from openmy.domain.intent import DONE_STATUSES, DueDate, Fact, Intent

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

PAST_MARKERS = (
    "昨天", "昨晚", "前天", "刚才", "刚刚", "已经", "想过", "考虑过", "看过",
    "聊了", "聊完", "去了", "吃完", "做完", "改完", "写完", "发了", "见了",
    "处理完", "搞定了",
)
FUTURE_MARKERS = (
    "明天", "后天", "下次", "待会", "一会", "稍后", "之后", "打算", "准备",
    "记得", "提醒", "还没", "需要", "要", "得",
)
ONGOING_MARKERS = (
    "正在", "在做", "在改", "还在", "继续", "推进中", "处理中", "没改完", "没做完",
)
COMPLETED_TASK_HINTS = (
    "README", "OpenMy", "文档", "配置", "代码", "提取器", "prompt", "日报",
    "状态", "测试", "接口", "脚本", "发布", "同步", "回电话", "联系",
    "修", "改", "写", "补", "提交", "更新",
)
LIFE_EVENT_HINTS = (
    "按摩", "火锅", "吃饭", "散步", "买菜", "咖啡", "回家", "睡觉", "约饭",
    "洗澡", "看电影",
)


def parse_reference_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_chinese_number(token: str) -> int | None:
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


def extract_relative_day_offset(raw_text: str) -> int | None:
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


def extract_time_parts(raw_text: str) -> tuple[int, int] | None:
    colon_match = TIME_COLON_RE.search(raw_text)
    if colon_match:
        return int(colon_match.group("hour")), int(colon_match.group("minute"))

    point_match = TIME_POINT_RE.search(raw_text)
    if not point_match:
        return None

    hour = parse_chinese_number(point_match.group("hour"))
    minute_token = point_match.group("minute")
    minute = parse_chinese_number(minute_token) if minute_token else 0
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


def resolve_relative_due(raw_text: str, reference_date: str | None) -> tuple[str, str] | None:
    base_date = parse_reference_date(reference_date)
    offset = extract_relative_day_offset(raw_text)
    if base_date is None or offset is None:
        return None

    target_date = base_date + timedelta(days=offset)
    time_parts = extract_time_parts(raw_text)
    if time_parts is None:
        return target_date.isoformat(), "day"

    hour, minute = time_parts
    target_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hour, minute=minute)
    return target_dt.strftime("%Y-%m-%dT%H:%M:%S"), "time"


def normalize_due_date(due: DueDate, reference_date: str | None) -> DueDate:
    resolved = resolve_relative_due(due.raw_text, reference_date)
    if not resolved:
        return due
    iso_date, granularity = resolved
    return DueDate(raw_text=due.raw_text, iso_date=iso_date, granularity=granularity)


def _match_markers(text: str, markers: tuple[str, ...]) -> list[str]:
    return [marker for marker in markers if marker and marker in text]


def _temporal_text(intent: Intent) -> str:
    return " ".join(
        part
        for part in (
            intent.evidence_quote.strip(),
            intent.what.strip(),
            intent.due.raw_text.strip(),
        )
        if part
    )


def _looks_like_completed_task(intent: Intent, text: str) -> bool:
    if intent.status in DONE_STATUSES:
        return True
    if any(marker in text for marker in LIFE_EVENT_HINTS):
        return False
    if intent.project_hint.strip() or intent.topic.strip():
        return True
    return any(marker in text for marker in COMPLETED_TASK_HINTS)


def _demoted_fact_type(intent: Intent) -> str:
    topic = (intent.project_hint.strip() or intent.topic.strip())
    if topic and topic not in {"生活", "日常", "个人", "杂项"}:
        return "project_update"
    if intent.kind == "decision":
        return "idea"
    return "observation"


def intent_to_fact(intent: Intent) -> Fact:
    content = intent.evidence_quote.strip() or intent.what.strip()
    return Fact(
        fact_type=_demoted_fact_type(intent),
        content=content,
        topic=intent.project_hint.strip() or intent.topic.strip(),
        confidence_label=intent.confidence_label,
        confidence_score=intent.confidence_score,
        source_scene_id=intent.source_scene_id,
    )


def _temporal_basis_label(prefix: str, values: list[str]) -> list[str]:
    return [f"{prefix}:{value}" for value in values]


def resolve_temporal_verdict(intent: Intent) -> tuple[str, str, list[str]]:
    text = _temporal_text(intent)
    past_hits = _match_markers(text, PAST_MARKERS)
    future_hits = _match_markers(text, FUTURE_MARKERS)
    ongoing_hits = _match_markers(text, ONGOING_MARKERS)
    strong_future_hits = [marker for marker in future_hits if marker not in {"还没", "要", "得"}]

    if intent.kind == "open_question":
        return "future", "keep_intent", ["question_kind"]

    if ongoing_hits and (intent.due.raw_text.strip() or strong_future_hits):
        return "future", "keep_intent", _temporal_basis_label("future", future_hits) + _temporal_basis_label("ongoing", ongoing_hits)

    if ongoing_hits:
        return "ongoing", "keep_intent", _temporal_basis_label("ongoing", ongoing_hits)

    if past_hits and not future_hits:
        basis = _temporal_basis_label("past", past_hits)
        if _looks_like_completed_task(intent, text):
            return "past", "force_done", basis
        return "past", "demote_to_fact", basis

    if future_hits and not past_hits:
        return "future", "keep_intent", _temporal_basis_label("future", future_hits)

    if past_hits and future_hits:
        basis = _temporal_basis_label("mixed_past", past_hits) + _temporal_basis_label("mixed_future", future_hits)
        if intent.due.raw_text.strip() or future_hits:
            return "future", "keep_intent", basis + ["mixed_future_bias"]
        return "unclear", "demote_to_fact", basis

    if intent.due.raw_text.strip():
        return "future", "keep_intent", ["due_signal"]

    if intent.kind in {"action_item", "commitment"}:
        return "future", "keep_intent", ["model_intent_default"]

    return "unclear", "keep_intent", ["model_default"]


def adjudicate_temporality(intents: list[Intent], facts: list[Fact]) -> tuple[list[Intent], list[Fact]]:
    kept_intents: list[Intent] = []
    merged_facts: list[Fact] = list(facts)
    seen_facts = {fact.content.strip() for fact in merged_facts if fact.content.strip()}

    for intent in intents:
        state, action, basis = resolve_temporal_verdict(intent)
        intent.temporal_state = state
        intent.temporal_basis = basis

        if action == "demote_to_fact":
            fact = intent_to_fact(intent)
            content = fact.content.strip()
            if content and content not in seen_facts:
                seen_facts.add(content)
                merged_facts.append(fact)
            continue

        if action == "force_done":
            intent.status = "done"
        elif state == "ongoing" and intent.status not in DONE_STATUSES:
            intent.status = "active"

        if state == "unclear":
            intent.needs_review = True
            if intent.confidence_label == "high":
                intent.confidence_label = "medium"
                intent.confidence_score = min(intent.confidence_score or 0.9, 0.7)

        kept_intents.append(intent)

    return kept_intents, merged_facts
