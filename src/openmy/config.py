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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  通用
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 向后兼容：旧代码仍会直接 import GEMINI_MODEL
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_STT_PROVIDER = "gemini"
DEFAULT_LLM_PROVIDER = "gemini"


def _read_env(*names: str) -> str:
    for name in names:
        if not name:
            continue
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def get_stt_provider_name() -> str:
    return (_read_env("OPENMY_STT_PROVIDER") or DEFAULT_STT_PROVIDER).lower()


def get_llm_provider_name() -> str:
    return (_read_env("OPENMY_LLM_PROVIDER") or DEFAULT_LLM_PROVIDER).lower()


def get_stt_model() -> str:
    return _read_env("OPENMY_STT_MODEL", "GEMINI_MODEL") or GEMINI_MODEL


def get_llm_model() -> str:
    return _read_env("OPENMY_LLM_MODEL", "GEMINI_MODEL") or GEMINI_MODEL


def get_stage_llm_model(stage: str | None = None) -> str:
    stage_env_map = {
        "distill": "OPENMY_DISTILL_MODEL",
        "extract": "OPENMY_EXTRACT_MODEL",
        "roles": "OPENMY_ROLES_MODEL",
    }
    stage_env = stage_env_map.get((stage or "").lower(), "")
    return _read_env(stage_env, "OPENMY_LLM_MODEL", "GEMINI_MODEL") or GEMINI_MODEL


def get_stt_api_key() -> str:
    if get_stt_provider_name() == "gemini":
        return _read_env("OPENMY_STT_API_KEY", "GEMINI_API_KEY")
    return _read_env("OPENMY_STT_API_KEY")


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


def has_stt_credentials() -> bool:
    return bool(get_stt_api_key())


def has_llm_credentials(stage: str | None = None) -> bool:
    return bool(get_llm_api_key(stage))


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
