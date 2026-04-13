from __future__ import annotations

import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from openmy.utils.io import safe_write_json


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def feedback_root(root: Path | None = None) -> Path:
    return root or (Path.home() / ".openmy")


def settings_path(root: Path | None = None) -> Path:
    return feedback_root(root) / "settings.json"


def telemetry_path(root: Path | None = None) -> Path:
    return feedback_root(root) / "telemetry.json"


def load_settings(root: Path | None = None) -> dict[str, Any]:
    path = settings_path(root)
    if not path.exists():
        return {
            "feedback_opt_in": None,
            "opted_in_at": "",
            "first_install_time": "",
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "feedback_opt_in": None,
            "opted_in_at": "",
            "first_install_time": "",
        }


def save_settings(payload: dict[str, Any], root: Path | None = None) -> Path:
    path = settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_write_json(path, payload)
    return path


def load_telemetry(root: Path | None = None) -> dict[str, Any]:
    path = telemetry_path(root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_telemetry(payload: dict[str, Any], root: Path | None = None) -> Path:
    path = telemetry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_write_json(path, payload)
    return path


def ensure_install_time(root: Path | None = None) -> None:
    settings = load_settings(root)
    if not settings.get("feedback_opt_in"):
        return
    if settings.get("first_install_time"):
        return
    settings["first_install_time"] = settings.get("opted_in_at") or _now_iso()
    save_settings(settings, root)


def set_feedback_opt_in(enabled: bool, root: Path | None = None) -> tuple[Path, Path]:
    now = _now_iso()
    settings = load_settings(root)
    settings["feedback_opt_in"] = enabled
    if enabled and not settings.get("opted_in_at"):
        settings["opted_in_at"] = now
    if enabled and not settings.get("first_install_time"):
        settings["first_install_time"] = settings.get("opted_in_at") or now
    settings_file = save_settings(settings, root)

    telemetry = load_telemetry(root)
    telemetry.setdefault("os", platform.system())
    if enabled:
        telemetry.setdefault("first_install_time", settings.get("first_install_time") or now)
    telemetry_file = save_telemetry(telemetry, root)
    return settings_file, telemetry_file


def delete_feedback_data(root: Path | None = None) -> None:
    settings_path(root).unlink(missing_ok=True)
    telemetry_path(root).unlink(missing_ok=True)


def record_processing_success(provider_name: str, root: Path | None = None, when: str | None = None) -> dict[str, Any] | None:
    settings = load_settings(root)
    if not settings.get("feedback_opt_in"):
        return None

    now = when or _now_iso()
    install_time = settings.get("first_install_time") or settings.get("opted_in_at") or now
    telemetry = load_telemetry(root)
    telemetry["os"] = platform.system()
    telemetry["stt_provider"] = provider_name
    telemetry["first_install_time"] = telemetry.get("first_install_time") or install_time
    telemetry["first_successful_processing_time"] = telemetry.get("first_successful_processing_time") or now

    try:
        install_dt = datetime.fromisoformat(str(telemetry["first_install_time"]))
        success_dt = datetime.fromisoformat(str(telemetry["first_successful_processing_time"]))
        telemetry["tthw_seconds"] = max(0, int((success_dt - install_dt).total_seconds()))
    except Exception:
        telemetry["tthw_seconds"] = 0

    save_telemetry(telemetry, root)
    return telemetry


def ask_feedback_opt_in(
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> bool | None:
    answer = input_fn("是否愿意只在本地记录一次首次使用反馈？输入 y 或 n：").strip().lower()
    if answer in {"y", "yes"}:
        output_fn("好，我只记本地数据，不上传。")
        return True
    if answer in {"n", "no"}:
        output_fn("好，那我就不记。")
        return False
    output_fn("我没听懂，这次先不改。")
    return None
