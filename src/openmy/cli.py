#!/usr/bin/env python3
"""OpenMy — 个人上下文引擎 CLI."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from openmy.config import (
    GEMINI_MODEL,
    get_llm_api_key,
    get_stage_llm_model,
    get_stt_api_key,
    get_stt_align_enabled,
    get_stt_diarization_enabled,
    get_stt_enrich_mode,
    get_stt_model,
    get_stt_provider_name,
    has_llm_credentials,
    stt_provider_requires_api_key,
)
from openmy.utils.io import safe_write_json
from openmy.utils.paths import (
    DATA_ROOT,
    LEGACY_ROOT,
    PROJECT_ENV_PATH,
    PROJECT_ROOT as ROOT_DIR,
)
from openmy.services.onboarding.state import load_onboarding_state
from openmy.services.query.context_query import query_context, render_query_result
from openmy.services.query.search_index import get_day_status_from_index, list_index_dates


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


class FriendlyCliError(RuntimeError):
    """给最终用户看的中文错误。"""


def project_version() -> str:
    try:
        content = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    except Exception:
        return "0.x.x"
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    return match.group(1) if match else "0.x.x"


def _show_main_menu() -> None:
    onboarding = load_onboarding_state(DATA_ROOT)
    sections = [
        (
            "快速开始",
            [
                ("openmy quick-start", "首次使用，自动引导"),
                ("openmy run 2026-04-12", "处理某天的录音"),
            ],
        ),
        (
            "处理流程",
            [
                ("openmy status", "查看所有日期的处理状态"),
                ("openmy view 2026-04-12", "查看某天的概览"),
                ("openmy run", "全流程处理"),
            ],
        ),
        (
            "单步操作",
            [
                ("openmy clean", "清洗转写文本"),
                ("openmy roles", "场景切分 + 角色归因"),
                ("openmy distill", "蒸馏摘要"),
                ("openmy briefing", "生成日报"),
                ("openmy extract", "提取意图 / 事实"),
            ],
        ),
        (
            "上下文",
            [
                ("openmy context", "生成/查看活动上下文"),
                ("openmy query", "查询项目/人物/待办"),
                ("openmy weekly", "查看本周回顾"),
                ("openmy monthly", "查看本月回顾"),
            ],
        ),
        (
            "工具",
            [
                ("openmy correct", "纠正转写错误"),
                ("openmy watch", "监控录音文件夹"),
                ("openmy screen on/off", "开关屏幕识别"),
            ],
        ),
        (
            "Agent 接口",
            [
                ("openmy skill ...", "稳定 JSON 动作入口"),
            ],
        ),
    ]

    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="left", ratio=2)

    for title, rows in sections:
        grid.add_row(f"[bold cyan]{title}[/bold cyan]", "")
        for command, description in rows:
            grid.add_row(f"  [green]{command}[/green]", f"[white]{description}[/white]")
        grid.add_row("", "")

    footer = f"v{project_version()} · https://github.com/openmy-ai/openmy"
    grid.add_row(f"[dim]{footer}[/dim]", "")
    if onboarding and not onboarding.get("completed", False):
        recommended = onboarding.get("recommended_label") or onboarding.get("recommended_provider") or "先做环境检查"
        reason = onboarding.get("recommended_reason") or onboarding.get("next_step") or "先把第一次使用走通。"
        console.print(Panel(f"下一步建议：{recommended}\n{reason}", title="首次使用引导", border_style="yellow"))
    console.print(Panel(grid, title="OpenMy — 你的个人上下文引擎", border_style="bright_blue"))


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


def find_all_dates() -> list[str]:
    """扫描所有可用日期。"""
    dates: set[str] = set()
    dates.update(list_index_dates(DATA_ROOT))
    if DATA_ROOT.exists():
        for child in DATA_ROOT.iterdir():
            if child.is_dir() and DATE_RE.match(child.name):
                dates.add(child.name)
    for path in LEGACY_ROOT.glob("*.md"):
        if path.name.endswith(".raw.md"):
            continue
        match = DATE_MD_RE.match(path.name)
        if match:
            dates.add(match.group(1))
    return sorted(dates, reverse=True)


def ensure_day_dir(date_str: str) -> Path:
    day_dir = DATA_ROOT / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def strip_document_header(markdown: str) -> str:
    if "---" not in markdown:
        return markdown
    parts = markdown.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return markdown


def get_date_status(date_str: str) -> dict[str, Any]:
    """获取某一天的处理阶段。"""
    from openmy.config import ROLE_RECOGNITION_ENABLED

    indexed = get_day_status_from_index(DATA_ROOT, date_str)
    if indexed is not None:
        return indexed

    day_dir = DATA_ROOT / date_str
    legacy = LEGACY_ROOT / f"{date_str}.md"

    status: dict[str, Any] = {
        "date": date_str,
        "has_transcript": (day_dir / "transcript.md").exists() or legacy.exists(),
        "has_raw": (day_dir / "transcript.raw.md").exists() or (LEGACY_ROOT / f"{date_str}.raw.md").exists(),
        "has_scenes": (day_dir / "scenes.json").exists() or (LEGACY_ROOT / f"{date_str}.scenes.json").exists(),
        "has_briefing": (day_dir / "daily_briefing.json").exists(),
        "word_count": 0,
        "scene_count": 0,
        "role_distribution": {},
    }

    transcript = day_dir / "transcript.md"
    if not transcript.exists():
        transcript = legacy
    if transcript.exists():
        content = transcript.read_text(encoding="utf-8")
        status["word_count"] = len(re.sub(r"\s+", "", content))

    scenes_path = day_dir / "scenes.json"
    if not scenes_path.exists():
        scenes_path = LEGACY_ROOT / f"{date_str}.scenes.json"
    if scenes_path.exists():
        data = read_json(scenes_path, {})
        status["scene_count"] = len(data.get("scenes", []))
        if ROLE_RECOGNITION_ENABLED:
            status["role_distribution"] = data.get("stats", {}).get("role_distribution", {})

    return status


def resolve_day_paths(date_str: str) -> dict[str, Path]:
    day_dir = DATA_ROOT / date_str
    if day_dir.exists():
        return {
            "dir": day_dir,
            "transcript": day_dir / "transcript.md",
            "raw": day_dir / "transcript.raw.md",
            "scenes": day_dir / "scenes.json",
            "briefing": day_dir / "daily_briefing.json",
        }

    return {
        "dir": day_dir,
        "transcript": LEGACY_ROOT / f"{date_str}.md",
        "raw": LEGACY_ROOT / f"{date_str}.raw.md",
        "scenes": LEGACY_ROOT / f"{date_str}.scenes.json",
        "briefing": day_dir / "daily_briefing.json",
    }


def stage_label(status: dict[str, Any]) -> str:
    if status["has_briefing"]:
        return "[green]✅ 完成[/green]"
    if status["has_scenes"]:
        return "[yellow]📊 已归因[/yellow]"
    if status["has_transcript"]:
        return "[blue]📝 已转写[/blue]"
    if status["has_raw"]:
        return "[dim]🎙️ 已录入[/dim]"
    return "[dim]❌ 无数据[/dim]"


def role_bar(distribution: dict[str, int], width: int = 20) -> str:
    total = sum(distribution.values())
    if total == 0:
        return "[dim]—[/dim]"

    parts: list[str] = []
    for role, count in sorted(distribution.items(), key=lambda item: -item[1]):
        color = ROLE_COLORS.get(role, "white")
        bar_len = max(1, round(count / total * width))
        parts.append(f"[{color}]{'█' * bar_len}[/{color}]")
    return "".join(parts)


def get_screen_client():
    try:
        from openmy.adapters.screen_recognition.client import ScreenRecognitionClient

        client = ScreenRecognitionClient()
        return client if client.is_available() else None
    except Exception:
        return None


def read_scenes_payload(date_str: str) -> tuple[Path, dict[str, Any]]:
    paths = resolve_day_paths(date_str)
    return paths["scenes"], read_json(paths["scenes"], {})


def parse_audio_time(audio_path: Path) -> str:
    match = AUDIO_TIME_RE.match(audio_path.name)
    if not match:
        return "00:00"
    return f"{match.group(2)}:{match.group(3)}"


def infer_date_from_path(path: Path) -> str:
    """优先从父目录，再从文件名推断日期，支持 YYYY-MM-DD / YYYYMMDD。"""
    parent_name = path.parent.name
    if DATE_RE.match(parent_name):
        return parent_name

    match = DATE_IN_FILENAME_RE.search(path.name)
    if not match:
        return date.today().isoformat()
    if match.group("iso"):
        return match.group("iso")
    raw = match.group("compact")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


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
        raise FriendlyCliError("需要 Python 3.10 以上版本。可先运行 `brew install python@3.11`。")

    missing_bins = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing_bins:
        missing = "、".join(missing_bins)
        raise FriendlyCliError(f"缺少 {missing}。macOS 可先运行 `brew install ffmpeg`。")

    has_env_file = prepare_project_runtime_env()
    final_stt_provider = (stt_provider or get_stt_provider_name()).lower()
    stt_api_key = get_stt_api_key(final_stt_provider)
    if stt_provider_requires_api_key(final_stt_provider) and not stt_api_key:
        if has_env_file:
            raise FriendlyCliError(
                "已读取项目根目录 `.env`，但当前这条云端语音转写路线还缺 key。"
                "如果继续走云端，先确认你已经运行过 `openmy skill profile.set --stt-provider gemini --json`，"
                "再把对应 key 补进 `.env`；如果想先跑通，改走本地路线更省事。"
            )
        raise FriendlyCliError(
            "没找到项目根目录 `.env`，当前这条云端语音转写路线也没有可用 key。"
            "先复制 `.env.example` 成 `.env`，再补对应 key；如果想先跑通，直接改走 `--stt-provider funasr` 或 `--stt-provider faster-whisper`。"
        )


def add_stt_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--stt-provider",
        default=None,
        help="转写后端（如 gemini / faster-whisper / funasr）",
    )
    parser.add_argument(
        "--stt-model",
        default=None,
        help="转写模型名",
    )
    parser.add_argument("--stt-vad", action="store_true", help="启用转写后端自带 VAD")
    parser.add_argument(
        "--stt-word-timestamps",
        action="store_true",
        help="保留更细的词级时间信息（如果后端支持）",
    )
    parser.add_argument(
        "--stt-enrich-mode",
        default=get_stt_enrich_mode(),
        choices=["off", "recommended", "force"],
        help="WhisperX 精标策略：off=关闭，recommended=本地 STT 推荐路径，force=强制尝试",
    )
    parser.add_argument(
        "--stt-align",
        action="store_true",
        default=get_stt_align_enabled(),
        help="显式要求在转写后启用 WhisperX 精标层",
    )
    parser.add_argument(
        "--stt-diarize",
        action="store_true",
        default=get_stt_diarization_enabled(),
        help="在精标层尝试附加说话人分离（如果环境支持）",
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
        raise FriendlyCliError("本地网页没能正常启动，请稍后再试。")
    webbrowser.open(url)


def write_json(path: Path, payload: Any) -> None:
    safe_write_json(path, payload)


def infer_scene_role_profile(addressed_to: str) -> tuple[str, str]:
    """根据人工确认的对象名推导场景类别和展示标签。"""
    normalized = str(addressed_to or "").strip()
    lowered = normalized.lower()
    if not normalized:
        return ("uncertain", "不确定")
    if lowered in {"ai", "ai助手", "gpt", "chatgpt", "gemini", "claude", "codex"}:
        return ("ai", "跟AI说")
    if normalized in {"商家", "客服", "老板", "服务员"}:
        return ("merchant", "跟商家")
    if normalized in {"宠物", "小狗", "小猫"}:
        return ("pet", "跟宠物")
    if normalized in {"自己", "自言自语"}:
        return ("self", "自言自语")
    if normalized in {"未识别", "不确定"}:
        return ("uncertain", "不确定")
    return ("interpersonal", "跟人聊")


def rebuild_scene_stats(data: dict[str, Any]) -> dict[str, Any]:
    """根据 scenes 重新计算 role_distribution 和 needs_review_count。"""
    scenes = data.get("scenes", []) if isinstance(data.get("scenes", []), list) else []
    distribution: dict[str, int] = {}
    needs_review_count = 0
    for scene in scenes:
        role = scene.get("role", {}) if isinstance(scene.get("role", {}), dict) else {}
        addressed_to = str(role.get("addressed_to", "")).strip()
        label = addressed_to or str(role.get("scene_type_label", "")).strip() or "未识别"
        distribution[label] = distribution.get(label, 0) + 1
        if bool(role.get("needs_review")):
            needs_review_count += 1
    return {
        "total_scenes": len(scenes),
        "role_distribution": distribution,
        "needs_review_count": needs_review_count,
    }


def build_frozen_scene_stats(total_scenes: int) -> dict[str, Any]:
    return {
        "total_scenes": total_scenes,
        "role_distribution": {},
        "needs_review_count": 0,
        "role_recognition_status": "frozen",
    }


def freeze_scene_roles(data: dict[str, Any]) -> dict[str, Any]:
    scenes = data.get("scenes", []) if isinstance(data.get("scenes", []), list) else []
    frozen_role = {
        "category": "uncertain",
        "entity_id": "",
        "relation_label": "",
        "confidence": 0.0,
        "evidence_chain": [],
        "scene_type": "uncertain",
        "scene_type_label": "不确定",
        "addressed_to": "",
        "about": "",
        "source": "frozen",
        "source_label": "已冻结",
        "evidence": "角色识别已冻结",
        "needs_review": False,
    }
    for scene in scenes:
        role = scene.get("role", {}) if isinstance(scene.get("role", {}), dict) else {}
        if str(role.get("source", "")).strip() == "human_confirmed":
            continue
        scene["role"] = dict(frozen_role)
    data["stats"] = build_frozen_scene_stats(len(scenes))
    return data


def build_segmented_scenes_payload(markdown: str) -> dict[str, Any]:
    from openmy.services.segmentation.segmenter import build_scenes_payload, segment

    payload = build_scenes_payload(segment(markdown))
    return freeze_scene_roles(payload)


def upsert_correction(wrong: str, right: str, context: str = "") -> Path:
    from openmy.services.cleaning.cleaner import CORRECTIONS_FILE

    payload = {"_comment": "OpenMy 纠错词典", "corrections": []}
    if CORRECTIONS_FILE.exists():
        payload = read_json(CORRECTIONS_FILE, payload)
        payload.setdefault("_comment", "OpenMy 纠错词典")
        payload.setdefault("corrections", [])

    now = datetime.now().isoformat()
    today = date.today().isoformat()
    corrections = payload["corrections"]
    for item in corrections:
        if item.get("wrong") == wrong and item.get("right") == right:
            item["count"] = int(item.get("count", 0)) + 1
            item["context"] = context or item.get("context", "")
            item["last_updated"] = now
            write_json(CORRECTIONS_FILE, payload)
            return CORRECTIONS_FILE

    corrections.append(
        {
            "wrong": wrong,
            "right": right,
            "context": context,
            "count": 1,
            "first_seen": today,
            "last_updated": now,
        }
    )
    write_json(CORRECTIONS_FILE, payload)
    return CORRECTIONS_FILE


def _cmd_correct_typo(date_str: str, wrong: str, right: str) -> int:
    """纠正转写错词。"""
    paths = resolve_day_paths(date_str)
    transcript_path = paths["transcript"]
    if not transcript_path.exists():
        console.print(f"[red]❌ 找不到 {date_str} 的 transcript.md[/red]")
        return 1

    from openmy.services.cleaning.cleaner import sync_correction_to_vocab

    content = transcript_path.read_text(encoding="utf-8")
    replaced_count = content.count(wrong)
    transcript_path.write_text(content.replace(wrong, right), encoding="utf-8")

    corrections_path = upsert_correction(wrong, right)
    sync_correction_to_vocab(wrong, right)

    console.print(f"[green]✅ 纠错完成[/green]: {wrong} → {right}，替换 {replaced_count} 处")
    console.print(f"[dim]词典: {corrections_path}[/dim]")
    return 0


def _load_context_snapshot():
    from openmy.services.context.active_context import ActiveContext

    ctx_path = DATA_ROOT / "active_context.json"
    if not ctx_path.exists():
        console.print("[red]❌ 还没有活动上下文快照，请先运行 `python3 -m openmy context`[/red]")
        return None
    return ActiveContext.load(ctx_path)


def _normalize_match_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip().lower()


def _score_match(query: str, *candidates: str) -> int:
    normalized_query = _normalize_match_text(query)
    if not normalized_query:
        return -1

    best = -1
    for candidate in candidates:
        normalized_candidate = _normalize_match_text(candidate)
        if not normalized_candidate:
            continue
        if normalized_query == normalized_candidate:
            return 1000 + len(normalized_candidate)
        if normalized_query in normalized_candidate:
            best = max(best, 500 - max(0, len(normalized_candidate) - len(normalized_query)))
        elif normalized_candidate in normalized_query:
            best = max(best, 100 - max(0, len(normalized_query) - len(normalized_candidate)))
    return best


def _resolve_item(items: list[Any], query: str, candidate_getter) -> Any | None:
    best_item = None
    best_score = -1
    for item in items:
        score = _score_match(query, *candidate_getter(item))
        if score > best_score:
            best_score = score
            best_item = item
    if best_score < 0:
        return None
    return best_item


def _append_context_correction(
    op: str,
    target_type: str,
    target_id: str,
    payload: dict[str, Any] | None = None,
    reason: str = "",
) -> int:
    from openmy.services.context.corrections import append_correction, create_correction_event

    event = create_correction_event(
        actor="user",
        op=op,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        reason=reason,
    )
    append_correction(DATA_ROOT, event)
    return 0


def _cmd_correct_scene_role(date_str: str, scene_query: str, addressed_to: str) -> int:
    """人工修正某个场景的角色归因。"""
    scenes_path, data = read_scenes_payload(date_str)
    if not scenes_path.exists():
        console.print(f"[red]❌ 找不到 {date_str}/scenes.json，先运行 openmy roles {date_str}[/red]")
        return 1

    scenes = data.get("scenes", []) if isinstance(data.get("scenes", []), list) else []
    target = None
    for scene in scenes:
        if _score_match(
            scene_query,
            str(scene.get("scene_id", "")),
            str(scene.get("time_start", "")),
            str(scene.get("time_end", "")),
        ) >= 0:
            target = scene
            break

    if target is None:
        console.print(f"[red]❌ 没找到场景：{scene_query}[/red]")
        return 1

    scene_id = str(target.get("scene_id", "")).strip() or scene_query
    old_role = target.get("role", {}) if isinstance(target.get("role", {}), dict) else {}
    old_addressed_to = str(old_role.get("addressed_to", "")).strip() or "未识别"
    scene_type, scene_type_label = infer_scene_role_profile(addressed_to)

    updated_role = dict(old_role)
    updated_role.update(
        {
            "category": scene_type,
            "entity_id": addressed_to,
            "relation_label": addressed_to,
            "scene_type": scene_type,
            "scene_type_label": scene_type_label,
            "addressed_to": addressed_to,
            "confidence": 1.0,
            "evidence_chain": [f"人工修正为 {addressed_to}"],
            "source": "human_confirmed",
            "source_label": "你确认的",
            "evidence": f"人工修正为 {addressed_to}",
            "needs_review": False,
        }
    )
    target["role"] = updated_role
    data["stats"] = rebuild_scene_stats(data)
    write_json(scenes_path, data)

    from openmy.services.context.corrections import append_correction, create_correction_event

    event = create_correction_event(
        actor="user",
        op="confirm_scene_role",
        target_type="scene",
        target_id=f"{date_str}:{scene_id}",
        payload={
            "date": date_str,
            "scene_id": scene_id,
            "from": old_addressed_to,
            "to": addressed_to,
            "time_start": str(target.get("time_start", "")),
        },
    )
    append_correction(DATA_ROOT, event)

    console.print(
        f"[green]✅ 已修正场景角色[/green]: {date_str} {scene_id} "
        f"{old_addressed_to} → {addressed_to}"
    )
    console.print(
        "[dim]如需同步到日报，请重新运行 "
        f"`python3 -m openmy briefing {date_str}` 或完整 "
        f"`python3 -m openmy run {date_str} --skip-transcribe`。[/dim]"
    )
    return 0


def cmd_correct_list(_args: argparse.Namespace) -> int:
    """查看 correction 历史。"""
    from openmy.services.context.corrections import load_corrections

    corrections = load_corrections(DATA_ROOT)
    if not corrections:
        console.print("[dim]还没有任何修正记录[/dim]")
        return 0

    table = Table(title="📝 修正历史", box=box.ROUNDED)
    table.add_column("时间")
    table.add_column("操作")
    table.add_column("对象")
    table.add_column("原因")
    for event in corrections:
        if event.op == "merge_project":
            target = f"{event.payload.get('target_title', event.target_id)} → {event.payload.get('merge_into_title', event.payload.get('merge_into', ''))}"
        else:
            target = str(event.payload.get("target_title", event.target_id))
        table.add_row(event.created_at[:16], event.op, target, event.reason or "—")
    console.print(table)
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    """列出所有日期及处理状态。"""
    dates = find_all_dates()
    if not dates:
        console.print("[dim]没有找到任何数据[/dim]")
        return 0

    table = Table(title="📅 OpenMy 数据总览", box=box.ROUNDED, show_lines=True)
    table.add_column("日期", style="bold")
    table.add_column("状态", justify="center")
    table.add_column("字数", justify="right")
    table.add_column("场景", justify="right")
    table.add_column("角色分布", min_width=20)

    for date_str in dates:
        status = get_date_status(date_str)
        table.add_row(
            date_str,
            stage_label(status),
            f"{status['word_count']:,}" if status["word_count"] else "—",
            str(status["scene_count"]) if status["scene_count"] else "—",
            role_bar(status["role_distribution"]),
        )

    console.print(table)
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    """终端查看某天概览。"""
    date_str = args.date
    status = get_date_status(date_str)
    if not status["has_transcript"]:
        console.print(f"[red]❌ {date_str} 没有数据[/red]")
        return 1

    paths = resolve_day_paths(date_str)
    if paths["briefing"].exists():
        briefing = read_json(paths["briefing"], {})
        console.print(
            Panel(
                briefing.get("summary", "无摘要"),
                title=f"📋 {date_str} 日报",
                border_style="magenta",
                padding=(1, 2),
            )
        )
        console.print()

    if paths["scenes"].exists():
        data = read_json(paths["scenes"], {})
        scenes = data.get("scenes", [])
        for scene in scenes:
            time_start = scene.get("time_start", "")
            role = scene.get("role", {})
            role_label = role.get("addressed_to", "") or role.get("scene_type_label", "未识别")
            color = ROLE_COLORS.get(role_label, "white")
            summary = scene.get("summary", "")
            preview = scene.get("preview") or scene.get("text", "")[:100]

            content_parts = []
            if summary:
                content_parts.append(summary)
            content_parts.append(f"[dim]{preview}[/dim]")

            console.print(
                Panel(
                    "\n".join(content_parts),
                    title=f"🕐 {time_start}  [{color}]{role_label}[/{color}]",
                    title_align="left",
                    border_style=color,
                    padding=(0, 1),
                )
            )

        dist = data.get("stats", {}).get("role_distribution", {})
        if dist:
            console.print()
            console.print("[bold]📊 角色分布[/bold]")
            total = sum(dist.values())
            max_bar = 30
            for role_name, count in sorted(dist.items(), key=lambda item: -item[1]):
                color = ROLE_COLORS.get(role_name, "white")
                bar_len = max(1, round(count / total * max_bar))
                pct = count / total * 100
                console.print(f"  [{color}]{'█' * bar_len}[/{color}] {role_name} {count}段 ({pct:.0f}%)")
    else:
        content = paths["transcript"].read_text(encoding="utf-8")
        console.print(Panel(Markdown(content[:2000]), title=f"📝 {date_str} 转写文本"))

    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """清洗转写文本。"""
    date_str = args.date
    paths = resolve_day_paths(date_str)
    raw_path = paths["raw"]
    if not raw_path.exists():
        console.print(f"[red]❌ 找不到 {date_str} 的原始转写[/red]")
        return 1

    from openmy.services.cleaning.cleaner import clean_text

    raw_text = raw_path.read_text(encoding="utf-8")
    with console.status("[bold green]🧹 清洗中..."):
        cleaned = clean_text(raw_text)

    output_path = ensure_day_dir(date_str) / "transcript.md"
    output_path.write_text(cleaned, encoding="utf-8")

    before = len(re.sub(r"\s+", "", raw_text))
    after = len(re.sub(r"\s+", "", cleaned))
    console.print(f"[green]✅ 清洗完成[/green]: {before:,} → {after:,} 字 (去除 {before - after:,} 字)")
    console.print(f"[dim]{output_path}[/dim]")
    return 0


def cmd_roles(args: argparse.Namespace) -> int:
    """兼容旧命令名：当前只切场景，不再自动角色归因。"""
    date_str = args.date
    paths = resolve_day_paths(date_str)
    transcript_path = paths["transcript"]
    if not transcript_path.exists():
        console.print(f"[red]❌ 找不到 {date_str} 的清洗后文本，先运行 openmy clean {date_str}[/red]")
        return 1

    markdown = strip_document_header(transcript_path.read_text(encoding="utf-8"))

    with console.status("[bold cyan]🔪 场景切分中..."):
        result = build_segmented_scenes_payload(markdown)

    output_path = ensure_day_dir(date_str) / "scenes.json"
    write_json(output_path, result)

    stats = result["stats"]
    console.print(f"[green]✅ 场景切分完成[/green]: {stats['total_scenes']} 个场景")
    console.print("[dim]ℹ️ 自动角色识别已冻结，当前只生成场景，不做对象识别[/dim]")
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    """蒸馏摘要。"""
    date_str = args.date
    api_key = get_llm_api_key("distill")
    if not api_key:
        console.print(
            "[red]❌ 缺少 LLM provider key[/red]：请在当前项目根目录 `.env` 填 "
            "`GEMINI_API_KEY` 或 `OPENMY_LLM_API_KEY`。"
        )
        return 1

    scenes_path, data = read_scenes_payload(date_str)
    if not scenes_path.exists():
        console.print(f"[red]❌ 找不到 {date_str}/scenes.json，先运行 openmy roles {date_str}[/red]")
        return 1

    from openmy.services.distillation.distiller import summarize_scene
    model = get_stage_llm_model("distill") or GEMINI_MODEL

    pending = [scene for scene in data.get("scenes", []) if not scene.get("summary")]
    if not pending:
        console.print(f"[green]✅ {date_str} 所有场景已有摘要，跳过[/green]")
        return 0

    console.print(f"[cyan]🧪 蒸馏 {len(pending)} 个场景...[/cyan]")
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("蒸馏中...", total=len(pending))
        for scene in data.get("scenes", []):
            if scene.get("summary"):
                continue
            text = scene.get("text", "").strip()
            scene["summary"] = summarize_scene(text, api_key, GEMINI_MODEL) if text else ""
            progress.advance(task)

    write_json(scenes_path, data)
    console.print(f"[green]✅ 蒸馏完成[/green]: {len(pending)} 个摘要已写入")
    return 0


def cmd_briefing(args: argparse.Namespace) -> int:
    """生成日报。"""
    date_str = args.date
    paths = resolve_day_paths(date_str)

    from openmy.services.briefing.generator import generate_briefing, save_briefing

    screen_client = get_screen_client()
    with console.status("[bold magenta]📋 生成日报中..."):
        briefing = generate_briefing(paths["scenes"], date_str, screen_client)
        output_path = ensure_day_dir(date_str) / "daily_briefing.json"
        save_briefing(briefing, output_path)

    console.print(f"[green]✅ 日报已生成[/green]: {output_path}")
    console.print(
        Panel(
            briefing.summary or f"{date_str} 的记录",
            title=f"📋 {date_str} 日报摘要",
            border_style="magenta",
            padding=(1, 2),
        )
    )
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """从 transcript 提取 intents / facts 结构。"""
    from openmy.services.extraction.extractor import run_extraction

    data = run_extraction(
        args.input_file,
        date=args.date,
        model=args.model,
        vault_path=args.vault_path,
        api_key=args.api_key,
        dry_run=args.dry_run,
    )
    if data is None:
        return 1

    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        console.print("[green]✅ 提取完成[/green]")
    return 0


def cmd_correct(args: argparse.Namespace) -> int:
    from openmy.commands.correct import cmd_correct as _cmd_correct

    return _cmd_correct(args)


def cmd_context(args: argparse.Namespace) -> int:
    from openmy.commands.context import cmd_context as _cmd_context

    return _cmd_context(args)


def cmd_query(args: argparse.Namespace) -> int:
    result = query_context(
        DATA_ROOT,
        kind=args.kind,
        query=args.query or "",
        limit=args.limit,
        include_evidence=args.include_evidence,
    )
    if result.get("error"):
        if getattr(args, "json", False):
            _print_json(result)
        else:
            console.print(f"[red]❌ {result['error']}[/red]")
        return 1

    if getattr(args, "json", False):
        _print_json(result)
    else:
        console.print(Panel(render_query_result(result), title=f"🔎 {args.kind}", border_style="cyan"))
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """旧 agent 入口：兼容映射到稳定 skill 契约。"""
    if args.recent:
        action = "context.get"
        skill_args = argparse.Namespace(
            action=action,
            date=None,
            audio=None,
            skip_transcribe=False,
            correct_args=None,
            op=None,
            arg=None,
            status="done",
            level=0,
            compact=False,
            json=True,
        )
    elif args.day:
        action = "day.get"
        skill_args = argparse.Namespace(
            action=action,
            date=args.day,
            audio=None,
            skip_transcribe=False,
            correct_args=None,
            op=None,
            arg=None,
            status="done",
            level=1,
            compact=False,
            json=True,
        )
    elif args.reject_decision:
        action = "correction.apply"
        skill_args = argparse.Namespace(
            action=action,
            date=None,
            audio=None,
            skip_transcribe=False,
            correct_args=None,
            op="reject-decision",
            arg=[args.reject_decision],
            status="done",
            level=1,
            compact=False,
            json=True,
        )
    elif args.query:
        action = "context.query"
        skill_args = argparse.Namespace(
            action=action,
            date=None,
            audio=None,
            skip_transcribe=False,
            correct_args=None,
            op=None,
            arg=None,
            status="done",
            level=1,
            compact=False,
            json=True,
            kind=args.query_kind,
            query=args.query,
            limit=args.limit,
            include_evidence=args.include_evidence,
        )
    elif args.ingest:
        action = "day.run"
        skill_args = argparse.Namespace(
            action=action,
            date=args.ingest,
            audio=args.audio,
            skip_transcribe=args.skip_transcribe,
            correct_args=None,
            op=None,
            arg=None,
            status="done",
            level=1,
            compact=False,
            json=True,
            kind=None,
            query="",
            limit=5,
            include_evidence=False,
            stt_provider=args.stt_provider,
            stt_model=args.stt_model,
            stt_vad=args.stt_vad,
            stt_word_timestamps=args.stt_word_timestamps,
            stt_enrich_mode=args.stt_enrich_mode,
            stt_align=args.stt_align,
            stt_diarize=args.stt_diarize,
            payload_json=None,
            payload_file=None,
            name=None,
            language=None,
            timezone=None,
        )
    else:
        _print_json(
            {
                "ok": False,
                "action": "agent",
                "version": "v1",
                "error_code": "missing_action",
                "message": "agent 入口需要指定动作。",
                "hint": "请使用 --recent / --day / --ingest / --reject-decision / --query 之一。",
            }
        )
        return 1

    from openmy.skill_dispatch import dispatch_skill_action

    payload, exit_code = dispatch_skill_action(action, skill_args)
    _print_json(payload)
    return exit_code


def _print_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _run_with_silent_console(func, *args, **kwargs):
    global console

    original_console = console
    console = Console(file=io.StringIO(), force_terminal=False, color_system=None)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        console = original_console


def cmd_skill(args: argparse.Namespace) -> int:
    """稳定 JSON 动作入口。"""
    from openmy.skill_dispatch import dispatch_skill_action
    payload, exit_code = dispatch_skill_action(args.action, args)
    _print_json(payload)
    return exit_code


def transcribe_audio_files(date_str: str, audio_files: list[str]) -> int:
    from openmy.commands.run import transcribe_audio_files as _transcribe_audio_files

    return _transcribe_audio_files(date_str, audio_files)


def cmd_run(args: argparse.Namespace, **kwargs: Any) -> int:
    from openmy.commands.run import cmd_run as _cmd_run

    return _cmd_run(args, **kwargs)


def cmd_quick_start(args: argparse.Namespace) -> int:
    from openmy.commands.run import cmd_quick_start as _cmd_quick_start

    return _cmd_quick_start(args)


def _render_review(title: str, payload: dict[str, Any], field_pairs: list[tuple[str, str]]) -> None:
    lines: list[str] = []
    summary = str(payload.get("summary", "") or "").strip()
    if summary:
        lines.append(summary)
        lines.append("")
    for field_name, label in field_pairs:
        value = payload.get(field_name)
        if isinstance(value, list) and value:
            lines.append(f"[bold]{label}[/bold]")
            lines.extend([f"- {item}" for item in value[:6]])
            lines.append("")
        elif isinstance(value, str) and value.strip():
            lines.append(f"[bold]{label}[/bold]")
            lines.append(value.strip())
            lines.append("")
    console.print(Panel(Markdown("\n".join(lines).strip() or "暂无内容"), title=title, border_style="cyan"))


def cmd_weekly(args: argparse.Namespace) -> int:
    from openmy.services.aggregation.weekly import current_week_str, generate_weekly_review

    week = getattr(args, "week", None) or current_week_str()
    review = generate_weekly_review(DATA_ROOT, week)
    _render_review(
        f"📅 本周回顾 · {review['week']}",
        review,
        [("projects", "主要项目"), ("wins", "推进了什么"), ("open_items", "还没收完"), ("next_week_focus", "下周先盯")],
    )
    return 0


def cmd_monthly(args: argparse.Namespace) -> int:
    from openmy.services.aggregation.monthly import generate_monthly_review
    from openmy.services.aggregation.weekly import current_month_str

    month = getattr(args, "month", None) or current_month_str()
    review = generate_monthly_review(DATA_ROOT, month)
    _render_review(
        f"🗓️ 本月回顾 · {review['month']}",
        review,
        [("projects", "主要项目"), ("key_decisions", "关键决定"), ("open_items", "还没收完"), ("direction", "接下来")],
    )
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from openmy.services.watcher import watch

    watch(getattr(args, "directory", None))
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    from pathlib import Path

    from openmy.services.screen_recognition.capture import (
        is_capture_supported,
        read_status,
        run_capture_loop,
        start_capture_daemon,
        stop_capture_daemon,
    )
    from openmy.services.screen_recognition.settings import (
        load_screen_context_settings,
        save_screen_context_settings,
    )

    action = str(getattr(args, "action", "") or "").strip().lower()
    settings = load_screen_context_settings(data_root=DATA_ROOT)

    if action == "on":
        settings.enabled = True
        if settings.participation_mode == "off":
            settings.participation_mode = "summary_only"
        save_screen_context_settings(settings, data_root=DATA_ROOT)
        _upsert_project_env("SCREEN_RECOGNITION_ENABLED", "true")
        if not is_capture_supported():
            raise FriendlyCliError("当前机器不支持内置屏幕识别，只支持 macOS + 系统自带截屏")
        status = start_capture_daemon(
            data_root=DATA_ROOT,
            interval_seconds=settings.capture_interval_seconds,
            retention_hours=settings.screenshot_retention_hours,
        )
        console.print(f"[green]✅ 屏幕识别已开启（后台进程 {status.pid}）[/green]")
        return 0

    if action == "off":
        settings.enabled = False
        settings.participation_mode = "off"
        save_screen_context_settings(settings, data_root=DATA_ROOT)
        _upsert_project_env("SCREEN_RECOGNITION_ENABLED", "false")
        stop_capture_daemon(data_root=DATA_ROOT)
        console.print("[green]✅ 屏幕识别已关闭[/green]")
        return 0

    if action == "status":
        status = read_status(DATA_ROOT)
        running = "运行中" if status.running else "未运行"
        console.print(f"[cyan]ℹ️ 屏幕识别状态：{running}[/cyan]")
        return 0

    if action == "daemon":
        loop_data_root = Path(getattr(args, "data_root", DATA_ROOT) or DATA_ROOT)
        run_capture_loop(
            data_root=loop_data_root,
            interval_seconds=max(1, int(getattr(args, "interval", settings.capture_interval_seconds) or 1)),
            retention_hours=max(1, int(getattr(args, "retention_hours", settings.screenshot_retention_hours) or 1)),
        )
        return 0

    raise FriendlyCliError("screen 只支持 on / off / status")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openmy",
        description="🎙️ OpenMy — 个人上下文引擎",
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    sub.add_parser("status", help="列出所有日期及处理状态")

    p_view = sub.add_parser("view", help="终端查看某天的概览")
    p_view.add_argument("date", help="日期 YYYY-MM-DD")

    p_clean = sub.add_parser("clean", help="清洗转写文本")
    p_clean.add_argument("date", help="日期 YYYY-MM-DD")

    p_roles = sub.add_parser("roles", help="切场景 + 角色归因")
    p_roles.add_argument("date", help="日期 YYYY-MM-DD")

    p_distill = sub.add_parser("distill", help="蒸馏摘要（需要项目 `.env` 里的 LLM key）")
    p_distill.add_argument("date", help="日期 YYYY-MM-DD")

    p_brief = sub.add_parser("briefing", help="生成日报")
    p_brief.add_argument("date", help="日期 YYYY-MM-DD")

    p_extract = sub.add_parser("extract", help="从转写中提取 intents / facts")
    p_extract.add_argument("input_file", help="清洗后的 Markdown 文件路径")
    p_extract.add_argument("--date", help="日期 YYYY-MM-DD，默认从文件名推断")
    p_extract.add_argument("--model", default=None, help="LLM 模型（默认取项目 `.env` 或内置默认值）")
    p_extract.add_argument("--vault-path", help="Obsidian Vault 路径")
    p_extract.add_argument("--api-key", help="LLM API key")
    p_extract.add_argument("--dry-run", action="store_true", help="只打印提取结果，不写入文件")

    p_run = sub.add_parser("run", help="全流程处理")
    p_run.add_argument("date", help="日期 YYYY-MM-DD")
    p_run.add_argument("--audio", nargs="+", help="音频文件路径")
    p_run.add_argument("--skip-transcribe", action="store_true", help="跳过转写（使用已有数据）")
    p_run.add_argument("--skip-aggregate", action="store_true", help="跳过周/月聚合")
    add_stt_runtime_args(p_run)

    p_quick = sub.add_parser("quick-start", help="第一次使用：自动处理音频并打开本地日报")
    p_quick.add_argument("audio_path", nargs="?", help="音频文件路径；传 --demo 时可不填")
    p_quick.add_argument("--demo", action="store_true", help="使用内置示例音频跑一遍主链")
    p_quick.add_argument("--skip-aggregate", action="store_true", help="跳过周/月聚合")
    add_stt_runtime_args(p_quick)

    p_correct = sub.add_parser("correct", help="纠正转写或活动上下文")
    p_correct.add_argument("correct_args", nargs="*", help="纠错参数")
    p_correct.add_argument(
        "--status",
        default="done",
        choices=["done", "abandoned"],
        help="close-loop 的关闭状态",
    )

    p_context = sub.add_parser("context", help="生成/查看活动上下文")
    p_context.add_argument("--compact", action="store_true", help="输出 Markdown 压缩版")
    p_context.add_argument("--level", type=int, default=1, choices=[0, 1], help="输出层级 (0=极简, 1=完整)")

    p_weekly = sub.add_parser("weekly", help="查看本周回顾")
    p_weekly.add_argument("--week", help="指定周，例如 2026-W15")

    p_monthly = sub.add_parser("monthly", help="查看本月回顾")
    p_monthly.add_argument("--month", help="指定月，例如 2026-04")

    p_watch = sub.add_parser("watch", help="监控录音文件夹")
    p_watch.add_argument("directory", nargs="?", help="监控目录；不传就用已配置的录音固定目录")

    p_screen = sub.add_parser("screen", help="开关屏幕识别")
    p_screen.add_argument("action", choices=["on", "off", "status"], help="on=开启，off=关闭，status=查看状态")

    p_screen_loop = sub.add_parser("_screen-capture-loop", help=argparse.SUPPRESS)
    p_screen_loop.add_argument("action", nargs="?", default="daemon", help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--interval", type=int, default=5, help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--retention-hours", type=int, default=24, help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--data-root", default=str(DATA_ROOT), help=argparse.SUPPRESS)

    p_query = sub.add_parser("query", help="基于结构化上下文查询项目/人物/待办/证据")
    p_query.add_argument("--kind", required=True, choices=["project", "person", "open", "closed", "evidence"])
    p_query.add_argument("--query", default="", help="查询关键词（project / person / evidence 必填）")
    p_query.add_argument("--limit", type=int, default=5, help="最多返回多少条命中")
    p_query.add_argument("--include-evidence", action="store_true", help="返回证据来源")
    p_query.add_argument("--json", action="store_true", help="输出 JSON")

    p_agent = sub.add_parser("agent", help="给 Agent 调用的统一入口")
    agent_mode = p_agent.add_mutually_exclusive_group(required=True)
    agent_mode.add_argument("--recent", action="store_true", help="读取最近整体状态")
    agent_mode.add_argument("--day", help="查看某天结果 YYYY-MM-DD")
    agent_mode.add_argument("--ingest", help="处理某天输入 YYYY-MM-DD")
    agent_mode.add_argument("--reject-decision", dest="reject_decision", help="排除一条不重要的决策")
    agent_mode.add_argument("--query", help="按结构化结果查询项目/人物/待办/证据")
    p_agent.add_argument("--query-kind", default="project", choices=["project", "person", "open", "closed", "evidence"])
    p_agent.add_argument("--limit", type=int, default=5, help="给 --query 使用")
    p_agent.add_argument("--include-evidence", action="store_true", help="给 --query 使用：带上证据来源")
    p_agent.add_argument("--audio", nargs="+", help="给 --ingest 使用的音频文件路径")
    p_agent.add_argument("--skip-transcribe", action="store_true", help="给 --ingest 使用：复用已有数据")
    p_agent.add_argument("--skip-aggregate", action="store_true", help="给 --ingest 使用：跳过周/月聚合")
    add_stt_runtime_args(p_agent)

    p_skill = sub.add_parser("skill", help="稳定 JSON 动作入口")
    p_skill.add_argument(
        "action",
        help="稳定动作名",
    )
    p_skill.add_argument("--date", help="给 day.get / day.run 使用的日期 YYYY-MM-DD")
    p_skill.add_argument("--audio", nargs="+", help="给 day.run 使用的音频文件路径")
    p_skill.add_argument("--skip-transcribe", action="store_true", help="给 day.run 使用：复用已有数据")
    p_skill.add_argument("--skip-aggregate", action="store_true", help="给 day.run 使用：跳过周/月聚合")
    add_stt_runtime_args(p_skill)
    p_skill.add_argument("--correct-args", nargs="*", help="给 correction.apply 透传的参数")
    p_skill.add_argument("--op", help="给 correction.apply 使用的动作名，如 close-loop")
    p_skill.add_argument("--arg", action="append", help="给 correction.apply 使用的动作参数，可重复")
    p_skill.add_argument(
        "--status",
        default="done",
        choices=["done", "abandoned"],
        help="给 correction.apply 使用的 close-loop 状态",
    )
    p_skill.add_argument("--kind", choices=["project", "person", "open", "closed", "evidence"], help="给 context.query 使用")
    p_skill.add_argument("--query", default="", help="给 context.query 使用的查询词")
    p_skill.add_argument("--limit", type=int, default=5, help="给 context.query 使用的最大命中数")
    p_skill.add_argument("--include-evidence", action="store_true", help="给 context.query 返回证据来源")
    p_skill.add_argument("--level", type=int, default=1, choices=[0, 1], help="给 context.get 使用的层级")
    p_skill.add_argument("--compact", action="store_true", help="给 context.get 输出压缩 Markdown")
    p_skill.add_argument("--name", help="给 profile.set 使用的名字")
    p_skill.add_argument("--language", help="给 profile.set 使用的语言")
    p_skill.add_argument("--timezone", help="给 profile.set 使用的时区")
    p_skill.add_argument("--audio-source", help="给 profile.set 使用的录音固定目录")
    p_skill.add_argument("--week", help="给 aggregate 使用的周，例如 2026-W15")
    p_skill.add_argument("--month", help="给 aggregate 使用的月，例如 2026-04")
    p_skill.add_argument("--payload-json", help="给 submit 类动作使用的 JSON 字符串")
    p_skill.add_argument("--payload-file", help="给 submit 类动作使用的 JSON 文件路径")
    p_skill.add_argument("--json", action="store_true", help="兼容参数；skill 默认输出 JSON")

    return parser


def main_with_args(args: argparse.Namespace, parser: argparse.ArgumentParser | None = None) -> int:
    parser = parser or build_parser()
    prepare_project_runtime_env()
    if not args.command:
        _show_main_menu()
        return 0

    commands = {
        "agent": cmd_agent,
        "briefing": cmd_briefing,
        "clean": cmd_clean,
        "context": cmd_context,
        "correct": cmd_correct,
        "distill": cmd_distill,
        "extract": cmd_extract,
        "query": cmd_query,
        "quick-start": cmd_quick_start,
        "roles": cmd_roles,
        "run": cmd_run,
        "screen": cmd_screen,
        "_screen-capture-loop": cmd_screen,
        "skill": cmd_skill,
        "status": cmd_status,
        "view": cmd_view,
        "watch": cmd_watch,
        "weekly": cmd_weekly,
        "monthly": cmd_monthly,
    }

    handler = commands.get(args.command)
    if not handler:
        console.print(f"[yellow]命令 '{args.command}' 尚未实现[/yellow]")
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]已中断[/yellow]")
        return 130
    except Exception:
        console.print_exception(show_locals=False)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return main_with_args(args, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
