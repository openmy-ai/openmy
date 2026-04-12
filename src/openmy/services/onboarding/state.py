from __future__ import annotations

from pathlib import Path
from typing import Any

from openmy.utils.io import safe_write_json

PRIORITY = ["funasr", "faster-whisper", "dashscope", "gemini", "groq", "deepgram"]
LABELS = {
    "funasr": "本地中文优先",
    "faster-whisper": "本地通用优先",
    "dashscope": "云端中文优先",
    "gemini": "云端省事优先",
    "groq": "云端速度优先",
    "deepgram": "云端英文优先",
}
DESCRIPTIONS = {
    "funasr": "中文录音优先，而且不用密钥。",
    "faster-whisper": "本地就能跑，先成功最稳。",
    "dashscope": "中文精度更强，但要先填一次密钥。",
    "gemini": "少折腾，适合先跑通云端路线。",
    "groq": "速度快，但也要先填一次密钥。",
    "deepgram": "更偏英文场景，也要先填一次密钥。",
}

CHOICE_GROUPS = {
    "local": ["funasr", "faster-whisper"],
    "cloud": ["dashscope", "gemini", "groq", "deepgram"],
}


def onboarding_state_path(data_root: Path) -> Path:
    return Path(data_root) / "onboarding_state.json"


def _pick_recommended_provider(stt_providers: list[dict[str, Any]], current_stt: str) -> str:
    ready_map = {item.get("name", ""): bool(item.get("ready")) for item in stt_providers}
    if current_stt and ready_map.get(current_stt):
        return current_stt
    for name in PRIORITY:
        if ready_map.get(name):
            return name
    return ""


def _provider_view(name: str, stt_providers: list[dict[str, Any]], recommended: str) -> dict[str, Any]:
    match = next((item for item in stt_providers if item.get("name") == name), {})
    return {
        "name": name,
        "label": LABELS.get(name, name),
        "description": DESCRIPTIONS.get(name, ""),
        "type": match.get("type", ""),
        "ready": bool(match.get("ready")),
        "is_active": bool(match.get("is_active")),
        "is_recommended": name == recommended,
        "needs_api_key": bool(match.get("needs_api_key")),
    }


def _build_choice_groups(stt_providers: list[dict[str, Any]], recommended: str) -> dict[str, list[dict[str, Any]]]:
    return {group: [_provider_view(name, stt_providers, recommended) for name in names] for group, names in CHOICE_GROUPS.items()}


def _build_headline(stage: str, recommended: str) -> str:
    label = LABELS.get(recommended, "先做环境检查")
    if stage == "choose_provider":
        return f"先别自己挑，先按推荐路线走：{label}"
    if stage == "complete_profile":
        return f"转写路子已经定了：{label}，现在补一下个人资料就能继续。"
    if stage == "init_vocab":
        return f"转写路子已经定了：{label}，现在补一下词库就能继续。"
    return f"现在可以直接开始第一次转写：{label}"


def _build_primary_action(stage: str, recommended: str) -> str:
    provider = recommended or "faster-whisper"
    if stage == "choose_provider":
        return f"先运行 openmy skill profile.set --stt-provider {provider} --json，先把推荐路线定下来。"
    if stage == "complete_profile":
        return "先补个人资料，再开始第一次转写。"
    if stage == "init_vocab":
        return "先补词库，再开始第一次转写。"
    return f"现在就可以直接试：openmy quick-start --stt-provider {provider} <你的音频路径>"


def build_onboarding_state(
    *,
    data_root: Path,
    stt_providers: list[dict[str, Any]],
    current_stt: str,
    profile_exists: bool,
    vocab_exists: bool,
) -> dict[str, Any]:
    recommended = _pick_recommended_provider(stt_providers, current_stt)
    if not current_stt:
        stage = "choose_provider"
        next_step = "先选转写引擎，再开始第一次转写。"
    elif not profile_exists:
        stage = "complete_profile"
        next_step = "先补个人资料，再开始第一次转写。"
    elif not vocab_exists:
        stage = "init_vocab"
        next_step = "先补词库，再开始第一次转写。"
    else:
        stage = "ready"
        next_step = "可以直接开始第一次转写。"

    payload = {
        "stage": stage,
        "completed": stage == "ready",
        "recommended_provider": recommended,
        "recommended_label": LABELS.get(recommended, ""),
        "recommended_reason": DESCRIPTIONS.get(recommended, ""),
        "headline": _build_headline(stage, recommended),
        "primary_action": _build_primary_action(stage, recommended),
        "choices": _build_choice_groups(stt_providers, recommended),
        "current_provider": current_stt,
        "next_step": next_step,
        "state_path": str(onboarding_state_path(data_root)),
    }
    return payload


def load_onboarding_state(data_root: Path) -> dict[str, Any]:
    path = onboarding_state_path(Path(data_root))
    if not path.exists():
        return {}
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_onboarding_state(data_root: Path, payload: dict[str, Any]) -> Path:
    path = onboarding_state_path(Path(data_root))
    safe_write_json(path, payload, trailing_newline=True)
    return path
