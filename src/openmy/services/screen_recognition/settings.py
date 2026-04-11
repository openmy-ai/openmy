from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from openmy.config import SCREEN_RECOGNITION_API, SCREEN_RECOGNITION_ENABLED


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_data_root() -> Path:
    return _project_root() / "data"


def settings_path(data_root: Path | None = None) -> Path:
    root = data_root or _default_data_root()
    return root / "runtime" / "screen_context_settings.json"


@dataclass
class ScreenContextSettings:
    enabled: bool = bool(SCREEN_RECOGNITION_ENABLED)
    participation_mode: str = "summary_only"
    provider_base_url: str = SCREEN_RECOGNITION_API
    exclude_apps: list[str] = field(default_factory=list)
    exclude_domains: list[str] = field(default_factory=list)
    exclude_window_keywords: list[str] = field(default_factory=list)
    summary_only_apps: list[str] = field(default_factory=lambda: ["微信", "企业微信", "飞书", "钉钉", "支付宝"])
    retention_days: int = 14

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ScreenContextSettings":
        payload = payload if isinstance(payload, dict) else {}
        mode = str(payload.get("participation_mode", "summary_only") or "summary_only").strip().lower()
        if mode not in {"off", "summary_only", "full"}:
            mode = "summary_only"
        enabled = bool(payload.get("enabled", SCREEN_RECOGNITION_ENABLED))
        if mode == "off":
            enabled = False
        return cls(
            enabled=enabled,
            participation_mode=mode,
            provider_base_url=str(payload.get("provider_base_url", SCREEN_RECOGNITION_API) or SCREEN_RECOGNITION_API),
            exclude_apps=[str(item) for item in payload.get("exclude_apps", []) if item is not None],
            exclude_domains=[str(item) for item in payload.get("exclude_domains", []) if item is not None],
            exclude_window_keywords=[
                str(item) for item in payload.get("exclude_window_keywords", []) if item is not None
            ],
            summary_only_apps=[str(item) for item in payload.get("summary_only_apps", []) if item is not None]
            or ["微信", "企业微信", "飞书", "钉钉", "支付宝"],
            retention_days=int(payload.get("retention_days", 14) or 14),
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

    env_map = env or os.environ
    if "OPENMY_SCREEN_CONTEXT_ENABLED" in env_map:
        loaded["enabled"] = env_map["OPENMY_SCREEN_CONTEXT_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
    elif "SCREEN_RECOGNITION_ENABLED" in env_map:
        loaded["enabled"] = env_map["SCREEN_RECOGNITION_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}

    if "OPENMY_SCREEN_CONTEXT_MODE" in env_map:
        loaded["participation_mode"] = env_map["OPENMY_SCREEN_CONTEXT_MODE"]
    elif "SCREEN_RECOGNITION_ENABLED" in env_map and env_map["SCREEN_RECOGNITION_ENABLED"].strip().lower() in {"0", "false", "no", "off"}:
        loaded["participation_mode"] = "off"

    if "OPENMY_SCREEN_CONTEXT_API" in env_map:
        loaded["provider_base_url"] = env_map["OPENMY_SCREEN_CONTEXT_API"]
    elif "SCREEN_RECOGNITION_API" in env_map:
        loaded["provider_base_url"] = env_map["SCREEN_RECOGNITION_API"]
    return ScreenContextSettings.from_dict(loaded)


def save_screen_context_settings(settings: ScreenContextSettings, *, data_root: Path | None = None) -> Path:
    path = settings_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def screen_context_participation_enabled(settings: ScreenContextSettings) -> bool:
    return bool(settings.enabled) and settings.participation_mode in {"summary_only", "full"}
