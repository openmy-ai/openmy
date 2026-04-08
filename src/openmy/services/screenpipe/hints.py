from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from openmy.domain.models import SceneBlock, ScreenSession


APP_ROLE_HINTS: dict[str, list[str]] = {
    "ai": [
        "Claude",
        "Cursor",
        "ChatGPT",
        "Antigravity",
        "Windsurf",
        "Copilot",
        "Terminal",
        "iTerm",
        "Warp",
        "VS Code",
        "Visual Studio Code",
        "Xcode",
    ],
    "interpersonal": [
        "WeChat",
        "微信",
        "飞书",
        "Lark",
        "Messages",
        "Telegram",
        "WhatsApp",
        "LINE",
        "Signal",
        "Slack",
        "Discord",
        "FaceTime",
    ],
    "merchant": [
        "淘宝",
        "美团",
        "饿了么",
        "拼多多",
        "京东",
        "闲鱼",
        "Shopee",
        "支付宝",
        "Alipay",
    ],
}


def get_role_hint(app_name: str, window_name: str = "") -> tuple[str, float]:
    """返回 (role_hint, boost_value)。"""
    combined = f"{app_name} {window_name}".lower()
    for role, apps in APP_ROLE_HINTS.items():
        for app in apps:
            if app.lower() in combined:
                return (role, 0.1)
    return ("", 0.0)


def _extract_domain(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc or ""


def sessionize(events, gap_seconds: int = 15) -> list[ScreenSession]:
    """按 app_name+window_name 聚合 screen events，间隔超过 gap_seconds 则切分。"""
    if not events:
        return []

    sorted_events = sorted(events, key=lambda event: event.timestamp)
    sessions: list[ScreenSession] = []
    current = None

    def _parse_ts(ts_str: str) -> float:
        """尽力解析 ISO 时间戳为 epoch 秒，失败返回 0。"""
        try:
            from datetime import datetime, timezone
            # 处理带时区偏移的 ISO 格式
            clean = ts_str.replace("+08:00", "+0800").replace("+00:00", "+0000")
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
                try:
                    return datetime.strptime(clean, fmt).timestamp()
                except ValueError:
                    continue
            return 0.0
        except Exception:
            return 0.0

    for event in sorted_events:
        key = f"{event.app_name}|{event.window_name}"
        # 检查是否应该合并到当前 session：同 key 且时间间隔 <= gap_seconds
        if current and current["key"] == key:
            elapsed = _parse_ts(event.timestamp) - _parse_ts(current["end_time"])
            if 0 <= elapsed <= gap_seconds:
                current["end_time"] = event.timestamp
                if event.frame_id:
                    current["frame_ids"].append(event.frame_id)
                if event.url and not current["url_domain"]:
                    current["url_domain"] = _extract_domain(event.url)
                continue

        if current:
            hint, _ = get_role_hint(current["app_name"], current["window_name"])
            sessions.append(
                ScreenSession(
                    app_name=current["app_name"],
                    window_name=current["window_name"],
                    url_domain=current["url_domain"],
                    start_time=current["start_time"],
                    end_time=current["end_time"],
                    frame_ids=current["frame_ids"][:5],
                    role_hint=hint,
                )
            )

        current = {
            "key": key,
            "app_name": event.app_name,
            "window_name": event.window_name,
            "url_domain": _extract_domain(event.url),
            "start_time": event.timestamp,
            "end_time": event.timestamp,
            "frame_ids": [event.frame_id] if event.frame_id else [],
        }

    if current:
        hint, _ = get_role_hint(current["app_name"], current["window_name"])
        sessions.append(
            ScreenSession(
                app_name=current["app_name"],
                window_name=current["window_name"],
                url_domain=current["url_domain"],
                start_time=current["start_time"],
                end_time=current["end_time"],
                frame_ids=current["frame_ids"][:5],
                role_hint=hint,
            )
        )

    return sessions


def apply_hints(scene: SceneBlock, sessions: list[ScreenSession]) -> SceneBlock:
    """把 screen sessions 的 role_hint 融入场景角色判定。"""
    scene.screen_sessions = sessions
    if not sessions:
        return scene

    hints = [session.role_hint for session in sessions if session.role_hint]
    if not hints:
        return scene

    dominant_hint, _count = Counter(hints).most_common(1)[0]
    role = scene.role
    primary_session = next((session for session in sessions if session.role_hint), sessions[0])

    if role.confidence >= 0.9:
        return scene

    if role.scene_type == dominant_hint:
        role.confidence = min(0.95, role.confidence + 0.1)
        role.evidence_chain.append(f"屏幕验证：{primary_session.app_name} 窗口佐证")
        return scene

    if role.scene_type == "uncertain":
        from openmy.services.roles.resolver import ROLE_LABELS

        role.category = dominant_hint
        role.scene_type = dominant_hint
        role.scene_type_label = ROLE_LABELS.get(dominant_hint, "不确定")
        role.confidence = 0.45
        role.source = "screen_hint"
        role.source_label = "屏幕推断"
        role.evidence = f"当时在用 {primary_session.app_name}"
        role.evidence_chain = [f"当时在用 {primary_session.app_name}"]
        role.needs_review = True
        return scene

    if role.scene_type != dominant_hint and role.confidence < 0.7:
        role.needs_review = True
        role.evidence_chain.append(
            f"⚠️ 屏幕显示 {primary_session.app_name}，但语音判为 {role.scene_type_label}"
        )

    return scene


def enrich_with_hints(scenes: list[SceneBlock], client, date_str: str | None = None) -> list[SceneBlock]:
    """为所有场景查询 Screenpipe 并应用 hints。"""
    if not client or not client.is_available():
        return scenes

    for scene in scenes:
        if not scene.time_start or not date_str:
            continue

        try:
            start_iso = f"{date_str}T{scene.time_start}:00+08:00"
            end_time = scene.time_end or scene.time_start
            end_iso = f"{date_str}T{end_time}:59+08:00"
        except Exception:
            continue

        events = client.search_ocr(start_time=start_iso, end_time=end_iso)
        sessions = sessionize(events)
        apply_hints(scene, sessions)

    return scenes
