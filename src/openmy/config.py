"""
OpenMy 全局配置
================

所有模型 provider 相关的默认值集中在这里。
开源用户只需要改环境变量或这一个文件，不用深入具体模块代码。

修改步骤：
1. 设置默认 provider 所需的 API key
2. 按需调整下面的参数
3. 运行 openmy run <日期>
"""

from __future__ import annotations

import os
from typing import Any

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  通用
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 向后兼容：旧代码仍会直接 import GEMINI_MODEL
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_STT_PROVIDER = ""  # 故意留空：用户必须显式选择转写引擎
DEFAULT_LLM_PROVIDER = "gemini"
DEFAULT_STT_MODELS = {
    "gemini": GEMINI_MODEL,
    "faster-whisper": "small",
    "funasr": "paraformer-zh",
    "groq": "whisper-large-v3-turbo",
    "dashscope": "qwen3-asr-1.7b",
    "deepgram": "nova-3",
}
LOCAL_STT_PROVIDERS = {"faster-whisper", "funasr"}

DEFAULT_EXPORT_PROVIDER = ""
EXPORT_PROVIDERS = {"obsidian", "notion"}


def _read_env(*names: str) -> str:
    for name in names:
        if not name:
            continue
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _read_bool_env(*names: str, default: bool = False) -> bool:
    value = _read_env(*names).lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def get_stt_provider_name() -> str:
    """Return the configured STT provider, or empty string if not set."""
    return (_read_env("OPENMY_STT_PROVIDER") or DEFAULT_STT_PROVIDER).lower().strip()


def get_llm_provider_name() -> str:
    return (_read_env("OPENMY_LLM_PROVIDER") or DEFAULT_LLM_PROVIDER).lower()


def get_stt_model(provider_name: str | None = None) -> str:
    final_provider = (provider_name or get_stt_provider_name()).lower()
    fallback = DEFAULT_STT_MODELS.get(final_provider, GEMINI_MODEL)
    return _read_env("OPENMY_STT_MODEL", "GEMINI_MODEL") or fallback


def get_llm_model() -> str:
    return _read_env("OPENMY_LLM_MODEL", "GEMINI_MODEL") or GEMINI_MODEL


def get_user_canonical_name() -> str:
    return _read_env("OPENMY_USER_CANONICAL_NAME", "OPENMY_USER_NAME") or "user"


def get_user_preferred_name() -> str:
    return _read_env("OPENMY_USER_PREFERRED_NAME", "OPENMY_USER_CANONICAL_NAME", "OPENMY_USER_NAME") or "user"


def get_stage_llm_model(stage: str | None = None) -> str:
    stage_env_map = {
        "distill": "OPENMY_DISTILL_MODEL",
        "extract": "OPENMY_EXTRACT_MODEL",
        "roles": "OPENMY_ROLES_MODEL",
    }
    stage_env = stage_env_map.get((stage or "").lower(), "")
    return _read_env(stage_env, "OPENMY_LLM_MODEL", "GEMINI_MODEL") or GEMINI_MODEL


def get_stt_api_key(provider_name: str | None = None) -> str:
    final_provider = (provider_name or get_stt_provider_name()).lower()
    if final_provider == "gemini":
        return _read_env("OPENMY_STT_API_KEY", "GEMINI_API_KEY")
    if final_provider == "groq":
        return _read_env("OPENMY_STT_API_KEY", "GROQ_API_KEY")
    if final_provider == "dashscope":
        return _read_env("OPENMY_STT_API_KEY", "DASHSCOPE_API_KEY")
    if final_provider == "deepgram":
        return _read_env("OPENMY_STT_API_KEY", "DEEPGRAM_API_KEY")
    return _read_env("OPENMY_STT_API_KEY")


def stt_provider_requires_api_key(provider_name: str | None = None) -> bool:
    final_provider = (provider_name or get_stt_provider_name()).lower()
    return final_provider not in LOCAL_STT_PROVIDERS


def get_llm_api_key(stage: str | None = None) -> str:
    stage_env_map = {
        "distill": "OPENMY_DISTILL_API_KEY",
        "extract": "OPENMY_EXTRACT_API_KEY",
        "roles": "OPENMY_ROLES_API_KEY",
    }
    stage_env = stage_env_map.get((stage or "").lower(), "")
    if get_llm_provider_name() == "gemini":
        return _read_env(stage_env, "OPENMY_LLM_API_KEY", "GEMINI_API_KEY")
    return _read_env(stage_env, "OPENMY_LLM_API_KEY")


def has_stt_credentials(provider_name: str | None = None) -> bool:
    if not stt_provider_requires_api_key(provider_name):
        return True
    return bool(get_stt_api_key(provider_name))


def has_llm_credentials(stage: str | None = None) -> bool:
    return bool(get_llm_api_key(stage))


def get_export_provider_name() -> str:
    value = (_read_env("OPENMY_EXPORT_PROVIDER") or DEFAULT_EXPORT_PROVIDER).strip().lower()
    return value if value in EXPORT_PROVIDERS else ""


def get_export_config() -> dict[str, Any]:
    provider = get_export_provider_name()
    if provider == "obsidian":
        return {"vault_path": _read_env("OPENMY_OBSIDIAN_VAULT_PATH")}
    if provider == "notion":
        return {
            "api_key": _read_env("NOTION_API_KEY"),
            "database_id": _read_env("NOTION_DATABASE_ID"),
        }
    return {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  转写 (transcribe)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 音频转写超时（秒），音频文件大需要更长时间
TRANSCRIBE_TIMEOUT = 900


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  清洗 (clean) — 纯规则引擎，不调 API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 时间头丢失阈值：清洗后时间头少于原文的这个比例时，打警告
TIME_HEADER_LOSS_THRESHOLD = 0.5


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  角色识别（已冻结）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 自动角色识别当前默认冻结；保留数据结构兼容，后续需要时再重新启用
ROLE_RECOGNITION_ENABLED = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  提取 (extract)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 提取用的 temperature（越低越稳定，结构化输出建议 ≤0.2）
EXTRACT_TEMPERATURE = 0.2

# 提取的思考级别（先用中档，优先保证 quick-start 真实可跑通）
EXTRACT_THINKING_LEVEL = "medium"

# 提取阶段单次 Gemini 请求超时（秒）
EXTRACT_TIMEOUT = 45


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  蒸馏 (distill)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 蒸馏用的 temperature
DISTILL_TEMPERATURE = 0.2

# 蒸馏的思考级别
DISTILL_THINKING_LEVEL = "medium"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  音频管线 (audio pipeline)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 音频管线中单文件转写超时
AUDIO_PIPELINE_TIMEOUT = 1800
STT_VAD_ENABLED = False
STT_WORD_TIMESTAMPS_ENABLED = False
STT_ALIGN_ENABLED = False
STT_DIARIZATION_ENABLED = False
STT_ENRICH_MODE = "recommended"


def get_stt_vad_enabled() -> bool:
    return _read_bool_env("OPENMY_STT_VAD", default=STT_VAD_ENABLED)


def get_stt_word_timestamps_enabled() -> bool:
    return _read_bool_env("OPENMY_STT_WORD_TIMESTAMPS", default=STT_WORD_TIMESTAMPS_ENABLED)


def get_stt_align_enabled() -> bool:
    return _read_bool_env("OPENMY_STT_ALIGN", default=STT_ALIGN_ENABLED)


def get_stt_diarization_enabled() -> bool:
    return _read_bool_env("OPENMY_STT_DIARIZE", default=STT_DIARIZATION_ENABLED)


def get_stt_enrich_mode() -> str:
    value = (_read_env("OPENMY_STT_ENRICH_MODE") or STT_ENRICH_MODE).strip().lower()
    return value if value in {"off", "recommended", "force"} else STT_ENRICH_MODE


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  屏幕识别（可选，需后台运行屏幕采集服务）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 是否启用屏幕识别
SCREEN_RECOGNITION_ENABLED = True

# 屏幕识别服务 API 地址
SCREEN_RECOGNITION_API = "http://localhost:3030"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  聚合 (consolidate)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 项目名合并映射：值为 None 表示过滤掉（非项目），值为字符串表示合并到该项目
# 用户可按自己的场景修改，比如如果你学做菜，可以去掉 "餐饮": None
PROJECT_MERGE_MAP: dict[str, str | None] = {
    "前端": "前端开发",
    "售后": None,
    "餐饮": None,
    "生活": None,
    "生活/宠物": None,
    "音频处理": "OpenMy",
    "自动化录音系统": "OpenMy",
}
