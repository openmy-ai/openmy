from __future__ import annotations

import re
from collections import Counter

from openmy.domain.models import ScreenCompletionCandidate, ScreenContext, ScreenSession
from openmy.services.screen_recognition.settings import ScreenContextSettings


DEVELOPMENT_TOKENS = {
    "cursor", "terminal", "iterm", "warp", "vscode", "vs code", "github", "gitlab", "codex", "claude", "openmy",
}
COMMUNICATION_TOKENS = {"微信", "wechat", "飞书", "lark", "slack", "telegram", "whatsapp", "企业微信", "钉钉"}
MERCHANT_TOKENS = {"淘宝", "taobao", "拼多多", "京东", "退款", "售后", "美团", "饿了么", "闲鱼"}
PAYMENT_TOKENS = {"支付宝", "alipay", "支付", "付款", "银行卡", "wallet", "bank"}
LOGISTICS_TOKENS = {"物流", "快递", "订单", "配送", "收货"}
CREATOR_TOKENS = {"小红书", "公众号", "创作者", "bilibili", "抖音"}
CLOUD_TOKENS = {"阿里云", "aliyun", "腾讯云", "cloud.tencent", "console.cloud", "密钥"}
LEARNING_TOKENS = {"微信读书", "notion", "obsidian", "教程", "文档"}

PROJECT_HINTS = {
    "openmy": "OpenMy",
    "obsidian": "Obsidian",
    "notion": "Notion",
    "xiaohongshu": "小红书",
}

COMPLETION_PATTERNS = {
    "submitted": ["提交成功", "submitted", "已提交"],
    "published": ["发布成功", "published", "已发布"],
    "saved": ["保存成功", "saved", "已保存"],
    "sent": ["已发送", "sent successfully", "发送成功"],
    "ordered": ["已下单", "order placed", "下单成功"],
    "paid": ["付款成功", "支付成功", "payment successful"],
    "merged": ["pull request merged", "merged successfully", "已合并"],
    "exported": ["导出成功", "已导出", "exported"],
    "uploaded": ["上传成功", "已上传", "uploaded"],
    "closed": ["任务已关闭", "closed issue", "已关闭"],
}


def _combined_text(*parts: str) -> str:
    return " ".join(str(part or "") for part in parts).strip().lower()


def infer_activity_tags(app_name: str, window_name: str = "", url_domain: str = "", text: str = "") -> list[str]:
    combined = _combined_text(app_name, window_name, url_domain, text)
    tags: set[str] = set()

    if any(token in combined for token in DEVELOPMENT_TOKENS):
        tags.add("development")
    if any(token in combined for token in COMMUNICATION_TOKENS):
        tags.add("communication")
    if any(token in combined for token in MERCHANT_TOKENS):
        tags.update({"merchant", "shopping"})
    if any(token in combined for token in PAYMENT_TOKENS):
        tags.add("payment")
    if any(token in combined for token in LOGISTICS_TOKENS):
        tags.add("logistics")
    if any(token in combined for token in CREATOR_TOKENS):
        tags.add("creator")
    if any(token in combined for token in CLOUD_TOKENS):
        tags.add("cloud")
    if any(token in combined for token in LEARNING_TOKENS):
        tags.add("learning")
    if not tags:
        tags.add("browsing")
    return sorted(tags)


def infer_project_hint_from_text(*parts: str) -> str:
    combined = _combined_text(*parts)
    for token, label in PROJECT_HINTS.items():
        if token in combined:
            return label
    return ""


def detect_completion_candidates(session: ScreenSession) -> list[ScreenCompletionCandidate]:
    combined = _combined_text(session.app_name, session.window_name, session.url_domain, session.text, session.summary)
    candidates: list[ScreenCompletionCandidate] = []
    for kind, patterns in COMPLETION_PATTERNS.items():
        if any(pattern.lower() in combined for pattern in patterns):
            label = patterns[0]
            candidates.append(
                ScreenCompletionCandidate(
                    kind=kind,
                    label=label,
                    confidence=0.9,
                    evidence=session.text or session.window_name or session.summary,
                    source_session_id=session.session_id,
                )
            )
    return candidates


def summarize_screen_session(session: ScreenSession) -> str:
    project = infer_project_hint_from_text(session.window_name, session.text, session.summary, session.url_domain)
    target = project or session.window_name or session.url_domain or session.app_name
    tags = session.tags or infer_activity_tags(session.app_name, session.window_name, session.url_domain, session.text)

    if "development" in tags:
        return f"当时正在 {session.app_name} 修改 {target}".strip()
    if "communication" in tags:
        return f"当时在 {session.app_name} 和人沟通 {target}".strip()
    if "merchant" in tags or "shopping" in tags:
        return f"当时在 {session.app_name} 处理 {target}".strip()
    if "payment" in tags:
        return f"当时在 {session.app_name} 处理支付或订单".strip()
    if "creator" in tags:
        return f"当时在 {session.app_name} 查看创作后台或数据".strip()
    if "cloud" in tags:
        return f"当时在 {session.app_name} 操作云控制台".strip()
    if session.summary_only:
        return f"当时在 {session.app_name} 处理敏感页面".strip()
    if session.text:
        snippet = re.sub(r"\s+", " ", session.text).strip()[:40]
        return f"当时在 {session.app_name} 处理 {snippet}".strip()
    return f"当时在 {session.app_name} 处理 {target}".strip()


def build_screen_context(
    sessions: list[ScreenSession],
    settings: ScreenContextSettings | None = None,
) -> ScreenContext:
    if not sessions:
        return ScreenContext()

    current_settings = settings or ScreenContextSettings()
    tags = sorted({tag for session in sessions for tag in (session.tags or [])})
    app_counter = Counter(session.app_name for session in sessions if session.app_name)
    window_counter = Counter(session.window_name for session in sessions if session.window_name)
    domain_counter = Counter(session.url_domain for session in sessions if session.url_domain)
    summaries = [session.summary or summarize_screen_session(session) for session in sessions]
    completion_candidates = [
        candidate
        for session in sessions
        for candidate in session.completion_candidates
    ]

    return ScreenContext(
        enabled=current_settings.enabled,
        participation_mode=current_settings.participation_mode,
        aligned=bool(sessions),
        summary="；".join(item for item in summaries[:2] if item),
        primary_app=app_counter.most_common(1)[0][0] if app_counter else "",
        primary_window=window_counter.most_common(1)[0][0] if window_counter else "",
        primary_domain=domain_counter.most_common(1)[0][0] if domain_counter else "",
        tags=tags,
        sensitive=any(session.sensitive for session in sessions),
        summary_only=any(session.summary_only for session in sessions),
        has_task_signal=any(tag in tags for tag in {"development", "merchant", "payment", "creator", "cloud"}),
        evidence_conflict=False,
        completion_candidates=completion_candidates,
        evidences=sessions,
    )
