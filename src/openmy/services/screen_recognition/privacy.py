from __future__ import annotations

import re

from openmy.domain.models import ScreenSession
from openmy.services.screen_recognition.settings import ScreenContextSettings


SECRET_PATTERNS = [
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"验证码", re.IGNORECASE),
    re.compile(r"\.env", re.IGNORECASE),
    re.compile(r"sk-[a-z0-9_-]{8,}", re.IGNORECASE),
]
PHONE_PATTERN = re.compile(r"1\d{10}")
ADDRESS_PATTERN = re.compile(r"(地址|收货地址|路|街道|小区)")
PAYMENT_PATTERN = re.compile(r"(支付|付款|银行卡|订单支付|wallet|bank)", re.IGNORECASE)
CHAT_PATTERN = re.compile(r"(聊天|message|messages|微信|飞书|企业微信|钉钉|mail|邮箱)", re.IGNORECASE)


def _matches_any(patterns, text: str) -> bool:
    return any(pattern.search(text or "") for pattern in patterns)


def _contains_sensitive_content(session: ScreenSession) -> tuple[bool, str]:
    combined = " ".join([session.app_name, session.window_name, session.url_domain, session.text]).strip()
    if _matches_any(SECRET_PATTERNS, combined):
        return True, "敏感凭据或密码页面"
    if PAYMENT_PATTERN.search(combined):
        return True, "敏感支付页面"
    if PHONE_PATTERN.search(combined) and ADDRESS_PATTERN.search(combined):
        return True, "包含地址和手机号"
    if CHAT_PATTERN.search(combined) and (PHONE_PATTERN.search(combined) or "身份证" in combined or "验证码" in combined):
        return True, "隐私聊天内容"
    return False, ""


def _is_excluded(session: ScreenSession, settings: ScreenContextSettings) -> bool:
    app_name = session.app_name.lower()
    window_name = session.window_name.lower()
    domain = session.url_domain.lower()
    if any(item.lower() in app_name for item in settings.exclude_apps):
        return True
    if any(item.lower() in domain for item in settings.exclude_domains):
        return True
    if any(item.lower() in window_name for item in settings.exclude_window_keywords):
        return True
    return False


def apply_privacy_filters(
    sessions: list[ScreenSession],
    settings: ScreenContextSettings | None = None,
) -> list[ScreenSession]:
    current_settings = settings or ScreenContextSettings()
    filtered: list[ScreenSession] = []
    for session in sessions:
        if _is_excluded(session, current_settings):
            continue
        sensitive, reason = _contains_sensitive_content(session)
        app_forced_summary = any(item.lower() in session.app_name.lower() for item in current_settings.summary_only_apps)
        session.sensitive = sensitive or app_forced_summary
        if session.sensitive:
            session.summary_only = True
            session.privacy_reason = reason or "敏感应用按摘要模式处理"
            session.text = ""
        filtered.append(session)
    return filtered
