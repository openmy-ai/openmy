from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from openmy.services.screen_recognition.capture import (
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    DEFAULT_EVENT_RETENTION_DAYS,
    DEFAULT_SCREENSHOT_RETENTION_HOURS,
)
from openmy.utils.io import safe_write_json


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_data_root() -> Path:
    return _project_root() / "data"


def settings_path(data_root: Path | None = None) -> Path:
    root = data_root or _default_data_root()
    return root / "runtime" / "screen_context_settings.json"


@dataclass
class ScreenContextSettings:
    enabled: bool = True
    participation_mode: str = "summary_only"
    capture_interval_seconds: int = DEFAULT_CAPTURE_INTERVAL_SECONDS
    screenshot_retention_hours: int = DEFAULT_SCREENSHOT_RETENTION_HOURS
    exclude_apps: list[str] = field(default_factory=list)
    exclude_domains: list[str] = field(default_factory=list)
    exclude_window_keywords: list[str] = field(default_factory=list)
    summary_only_apps: list[str] = field(default_factory=lambda: ["微信", "企业微信", "飞书", "钉钉", "支付宝"])
    retention_days: int = DEFAULT_EVENT_RETENTION_DAYS

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ScreenContextSettings":
        payload = payload if isinstance(payload, dict) else {}
        mode = str(payload.get("participation_mode", "summary_only") or "summary_only").strip().lower()
        if mode not in {"off", "summary_only", "full"}:
            mode = "summary_only"
        enabled = bool(payload.get("enabled", True))
        if mode == "off":
            enabled = False
        return cls(
            enabled=enabled,
            participation_mode=mode,
            capture_interval_seconds=int(
                payload.get("capture_interval_seconds", DEFAULT_CAPTURE_INTERVAL_SECONDS)
                or DEFAULT_CAPTURE_INTERVAL_SECONDS
            ),
            screenshot_retention_hours=int(
                payload.get("screenshot_retention_hours", DEFAULT_SCREENSHOT_RETENTION_HOURS)
                or DEFAULT_SCREENSHOT_RETENTION_HOURS
            ),
            exclude_apps=[str(item) for item in payload.get("exclude_apps", []) if item is not None],
            exclude_domains=[str(item) for item in payload.get("exclude_domains", []) if item is not None],
            exclude_window_keywords=[
                str(item) for item in payload.get("exclude_window_keywords", []) if item is not None
            ],
            summary_only_apps=[str(item) for item in payload.get("summary_only_apps", []) if item is not None]
            or ["微信", "企业微信", "飞书", "钉钉", "支付宝"],
            retention_days=int(payload.get("retention_days", DEFAULT_EVENT_RETENTION_DAYS) or DEFAULT_EVENT_RETENTION_DAYS),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_screen_context_settings(
    *,
    data_root: Path | None = None,
    env: dict[str, str] | None = None,
) -> ScreenContextSettings:
    loaded: dict[str, Any] = {}
    path = settings_path(data_root)
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}

    env_map = env if env is not None else os.environ
    if "OPENMY_SCREEN_CONTEXT_ENABLED" in env_map:
        loaded["enabled"] = env_map["OPENMY_SCREEN_CONTEXT_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
    elif env is not None and "SCREEN_RECOGNITION_ENABLED" in env_map:
        loaded["enabled"] = env_map["SCREEN_RECOGNITION_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}

    if "OPENMY_SCREEN_CONTEXT_MODE" in env_map:
        loaded["participation_mode"] = env_map["OPENMY_SCREEN_CONTEXT_MODE"]
    elif env is not None and "SCREEN_RECOGNITION_ENABLED" in env_map and env_map["SCREEN_RECOGNITION_ENABLED"].strip().lower() in {"0", "false", "no", "off"}:
        loaded["participation_mode"] = "off"

    if "OPENMY_SCREEN_CAPTURE_INTERVAL_SECONDS" in env_map:
        loaded["capture_interval_seconds"] = env_map["OPENMY_SCREEN_CAPTURE_INTERVAL_SECONDS"]
    if "OPENMY_SCREENSHOT_RETENTION_HOURS" in env_map:
        loaded["screenshot_retention_hours"] = env_map["OPENMY_SCREENSHOT_RETENTION_HOURS"]
    return ScreenContextSettings.from_dict(loaded)


def save_screen_context_settings(settings: ScreenContextSettings, *, data_root: Path | None = None) -> Path:
    path = settings_path(data_root)
    safe_write_json(path, settings.to_dict())
    return path


def screen_context_participation_enabled(settings: ScreenContextSettings) -> bool:
    return bool(settings.enabled) and settings.participation_mode in {"summary_only", "full"}
