from __future__ import annotations

import argparse
import json
import locale
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from rich.console import Console

from openmy.config import (
    get_llm_api_key as _get_llm_api_key,
    get_stt_api_key,
    get_stt_align_enabled,
    get_stt_diarization_enabled,
    get_stt_enrich_mode,
    get_stt_provider_name,
    stt_provider_requires_api_key,
)
from openmy.utils.io import safe_write_json
from openmy.utils.errors import FriendlyCliError, doc_url
from openmy.utils.paths import DATA_ROOT, PROJECT_ENV_PATH, PROJECT_ROOT as ROOT_DIR

console = Console()

ROLE_COLORS = {
    "AI助手": "cyan",
    "商家": "yellow",
    "伴侣": "magenta",
    "宠物": "green",
    "自己": "blue",
    "朋友": "bright_blue",
    "未识别": "dim",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
AUDIO_TIME_RE = re.compile(r".*?(\d{8})_(\d{2})(\d{2})(\d{2}).*")
DATE_IN_FILENAME_RE = re.compile(r"(?P<iso>\d{4}-\d{2}-\d{2})|(?P<compact>\d{8})")
HELP_IN_ENGLISH = False


def _prefers_english_help() -> bool:
    saw_non_chinese = False
    for env_name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = str(os.getenv(env_name, "") or "").strip().lower()
        if not value:
            continue
        if value.startswith("zh"):
            return False
        saw_non_chinese = True
    if saw_non_chinese:
        return True
    current_locale = locale.getlocale()[0]
    if current_locale:
        return not str(current_locale).lower().startswith("zh")
    return False

HELP_IN_ENGLISH = _prefers_english_help()
get_llm_api_key = _get_llm_api_key


def _help_text(zh: str, en: str) -> str:
    return en if HELP_IN_ENGLISH else zh

def render_friendly_error(exc: FriendlyCliError) -> None:
    console.print(f"[red]❌ {exc.message}[/red]")
    if getattr(exc, "fix", ""):
        console.print(f"[yellow]怎么修：{exc.fix}[/yellow]")
    if getattr(exc, "doc_url", ""):
        console.print(f"[dim]文档：{exc.doc_url}[/dim]")

def project_version() -> str:
    try:
        content = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    except Exception:
        return "0.x.x"
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    return match.group(1) if match else "0.x.x"

def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", str(version)))

def _update_check_cache_path() -> Path:
    return DATA_ROOT / ".update-check.json"

def _load_cached_update_hint(now_ts: float) -> str | None:
    cache_path = _update_check_cache_path()
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    checked_at = float(payload.get("checked_at", 0) or 0)
    if now_ts - checked_at > 6 * 3600:
        return None
    latest = str(payload.get("latest_version", "") or "").strip()
    if latest and _version_key(latest) > _version_key(project_version()):
        return latest
    return ""

def _store_update_hint(now_ts: float, latest_version: str) -> None:
    cache_path = _update_check_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    safe_write_json(
        cache_path,
        {
            "checked_at": now_ts,
            "latest_version": latest_version,
            "current_version": project_version(),
        },
    )

def maybe_get_update_hint() -> str | None:
    if not sys.stdout.isatty():
        return None
    if os.getenv("OPENMY_SKIP_UPDATE_CHECK", "").strip() == "1":
        return None

    now_ts = time.time()
    cached = _load_cached_update_hint(now_ts)
    if cached is not None:
        return cached or None

    latest_version = ""
    request = urllib_request.Request("https://pypi.org/pypi/openmy/json", method="GET")
    try:
        with urllib_request.urlopen(request, timeout=0.6) as response:
            payload = json.loads(response.read().decode("utf-8"))
            latest_version = str(payload.get("info", {}).get("version", "") or "").strip()
    except Exception:
        _store_update_hint(now_ts, "")
        return None

    _store_update_hint(now_ts, latest_version)
    if latest_version and _version_key(latest_version) > _version_key(project_version()):
        return latest_version
    return None

def _upsert_project_env(key: str, value: str) -> Path:
    lines: list[str] = []
    if PROJECT_ENV_PATH.exists():
        lines = PROJECT_ENV_PATH.read_text(encoding="utf-8").splitlines()

    replaced = False
    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        existing_key = stripped.split("=", 1)[0].strip()
        if existing_key != key:
            continue
        lines[index] = f"{key}={value}"
        replaced = True
        break

    if not replaced:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{key}={value}")

    PROJECT_ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return PROJECT_ENV_PATH

def clear_project_runtime_env() -> None:
    """CLI 只认当前项目 .env，先清掉 shell 注入的 OpenMy/Gemini 配置。"""
    for key in list(os.environ):
        if key.startswith("OPENMY_") or key in {"GEMINI_API_KEY", "GEMINI_MODEL"}:
            os.environ.pop(key, None)

def load_project_env(env_path: Path | None = None, *, override: bool = False) -> bool:
    """从项目根目录读取 .env。"""
    final_path = env_path or PROJECT_ENV_PATH
    if not final_path.exists():
        return False

    for raw_line in final_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and (override or key not in os.environ):
            os.environ[key] = value
    return True

def prepare_project_runtime_env(env_path: Path | None = None) -> bool:
    """重置 CLI 运行时 provider 配置，只加载当前项目 .env。"""
    clear_project_runtime_env()
    return load_project_env(env_path, override=True)

def missing_stt_key_message() -> str:
    return "缺少语音转写 KEY。"

def missing_stt_key_hint() -> str:
    return (
        "如果你要走云端转写，先运行 `openmy skill profile.set --stt-provider gemini --json`，"
        "再把对应 key 补进这个项目的 `.env`。"
    )

def missing_provider_key_message(has_env_file: bool) -> str:
    prefix = "已读取项目根目录 `.env`，但" if has_env_file else "没找到项目根目录 `.env`，而且"
    return (
        f"{prefix}缺少可用的转写或整理 key。"
        "如果你要走云端转写，先用 `openmy skill profile.set --stt-provider gemini --json` 定路线，"
        "再把对应 key 写进这个项目的 `.env`。"
    )

def ensure_runtime_dependencies(*, stt_provider: str | None = None) -> None:
    """给 quick-start 做最小依赖自检。"""
    if sys.version_info < (3, 10):
        raise FriendlyCliError(
            "需要 Python 3.10 以上版本。",
            code="python_version_too_low",
            fix="先运行 `brew install python@3.11`，再重试。",
            doc_url=doc_url("一分钟跑起来"),
            message_en="Python 3.10 or newer is required.",
            fix_en="Run brew install python@3.11, then retry.",
        )

    has_env_file = prepare_project_runtime_env()
    final_stt_provider = (stt_provider or get_stt_provider_name()).lower()
    stt_api_key = get_stt_api_key(final_stt_provider)
    if stt_provider_requires_api_key(final_stt_provider) and not stt_api_key:
        if has_env_file:
            raise FriendlyCliError(
                "已读取项目根目录 `.env`，但当前这条云端语音转写路线还缺 key。"
                "如果继续走云端，先确认你已经运行过 `openmy skill profile.set --stt-provider gemini --json`，"
                "再把对应 key 补进 `.env`；如果想先跑通，改走本地路线更省事。",
                code="stt_cloud_key_missing",
                fix="先补 `.env（环境文件）` 里的 key，或者改走本地转写路线。",
                doc_url=doc_url("语音转写"),
                message_en="The selected cloud speech-to-text route is missing its API key.",
                fix_en="Add the key to the project .env file, or switch to a local speech-to-text route.",
            )
        raise FriendlyCliError(
            "没找到项目根目录 `.env`，当前这条云端语音转写路线也没有可用 key。"
            "先复制 `.env.example` 成 `.env`，再补对应 key；如果想先跑通，直接改走 `--stt-provider funasr` 或 `--stt-provider faster-whisper`。",
            code="project_env_missing",
            fix="先复制 `.env.example（示例环境文件）` 成 `.env（环境文件）`，再补 key。",
            doc_url=doc_url("一分钟跑起来"),
            message_en="The project .env file is missing and this cloud speech-to-text route has no API key.",
            fix_en="Copy .env.example to .env and add the matching API key.",
        )

    missing_bins = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing_bins:
        missing = "、".join(missing_bins)
        raise FriendlyCliError(
            f"缺少 {missing}。",
            code="ffmpeg_missing",
            fix="macOS（苹果系统）先运行 `brew install ffmpeg`，再重试。",
            doc_url=doc_url("一分钟跑起来"),
            message_en=f"Missing required binary tools: {missing}.",
            fix_en="On macOS, run brew install ffmpeg, then retry.",
        )

def add_stt_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--stt-provider",
        default=None,
        help=_help_text(
            "转写后端（如 gemini / faster-whisper / funasr）",
            "Speech-to-text backend, for example gemini, faster-whisper, or funasr.",
        ),
    )
    parser.add_argument(
        "--stt-model",
        default=None,
        help=_help_text("转写模型名", "Speech-to-text model name."),
    )
    parser.add_argument(
        "--stt-vad",
        action="store_true",
        help=_help_text("启用转写后端自带 VAD", "Enable the backend's built-in voice activity detection."),
    )
    parser.add_argument(
        "--stt-word-timestamps",
        action="store_true",
        help=_help_text(
            "保留更细的词级时间信息（如果后端支持）",
            "Keep word-level timestamps when the backend supports them.",
        ),
    )
    parser.add_argument(
        "--stt-enrich-mode",
        default=get_stt_enrich_mode(),
        choices=["off", "recommended", "force"],
        help=_help_text(
            "WhisperX 精标策略：off=关闭，recommended=本地 STT 推荐路径，force=强制尝试",
            "WhisperX alignment mode: off disables it, recommended follows the local STT recommendation, and force always tries it.",
        ),
    )
    parser.add_argument(
        "--stt-align",
        action="store_true",
        default=get_stt_align_enabled(),
        help=_help_text(
            "显式要求在转写后启用 WhisperX 精标层",
            "Explicitly enable the WhisperX alignment step after transcription.",
        ),
    )
    parser.add_argument(
        "--stt-diarize",
        action="store_true",
        default=get_stt_diarization_enabled(),
        help=_help_text(
            "在精标层尝试附加说话人分离（如果环境支持）",
            "Try speaker diarization during alignment when the environment supports it.",
        ),
    )

def _local_report_health_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/api/onboarding"

def is_local_report_running(host: str = "127.0.0.1", port: int = 8420) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False

def is_local_report_healthy(host: str = "127.0.0.1", port: int = 8420) -> bool:
    health_request = urllib_request.Request(_local_report_health_url(host, port), method="GET")
    try:
        with urllib_request.urlopen(health_request, timeout=1.0) as response:
            return int(getattr(response, "status", 0) or 0) == 200
    except (urllib_error.URLError, TimeoutError, OSError):
        return False

def find_report_pids(port: int = 8420) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        raw = line.strip()
        if raw.isdigit():
            pids.append(int(raw))
    return pids

def kill_report_processes(port: int = 8420) -> bool:
    killed = False
    for pid in find_report_pids(port):
        try:
            os.kill(pid, 15)
            killed = True
        except OSError:
            continue
    if killed:
        time.sleep(0.4)
    if is_local_report_running(port=port):
        for pid in find_report_pids(port):
            try:
                os.kill(pid, 9)
            except OSError:
                continue
        time.sleep(0.4)
    return killed

def wait_for_local_report(host: str = "127.0.0.1", port: int = 8420, timeout_seconds: float = 8.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_local_report_healthy(host=host, port=port):
            return True
        time.sleep(0.2)
    return False

def launch_local_report(host: str = "127.0.0.1", port: int = 8420) -> None:
    """启动本地网页并打开浏览器；服务已在运行时只打开页面。"""
    url = f"http://{host}:{port}"
    if is_local_report_running(host=host, port=port) and not is_local_report_healthy(host=host, port=port):
        kill_report_processes(port=port)
    if not is_local_report_running(host=host, port=port):
        server_entry = ROOT_DIR / "app" / "server.py"
        subprocess.Popen(
            [sys.executable, str(server_entry)],
            cwd=ROOT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    if not wait_for_local_report(host=host, port=port):
        raise FriendlyCliError(
            "本地网页没能正常启动。",
            code="local_report_start_failed",
            fix="先确认 8420 端口没被别的进程占住，再重试。",
            doc_url=doc_url("readme"),
            message_en="The local web report failed to start.",
            fix_en="Make sure port 8420 is free, then retry.",
        )
    webbrowser.open(url)

def write_json(path: Path, payload: Any) -> None:
    safe_write_json(path, payload)

def get_screen_client():
    try:
        from openmy.adapters.screen_recognition.client import ScreenRecognitionClient

        client = ScreenRecognitionClient()
        return client if client.is_available() else None
    except Exception:
        return None
