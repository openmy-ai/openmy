#!/usr/bin/env python3
"""
OpenMy — 本地网页服务（OpenMy package 版）

默认只绑定本机：
  python3 app/server.py
  python3 app/server.py --host 127.0.0.1 --port 8420
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

BOOTSTRAP_ROOT = Path(__file__).resolve().parent.parent
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))
SRC_DIR = BOOTSTRAP_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.context_api import (
    handle_close_loop,
    handle_merge_project,
    handle_reject_decision,
    handle_reject_loop,
    handle_reject_project,
    refresh_active_context_snapshot,
)
from app.http_handlers import BrainHandler
from app.job_runner import JobRunner
from app.payloads import (
    get_all_dates,
    get_briefing,
    get_context_decisions_payload,
    get_context_loops_payload,
    get_context_payload,
    get_context_projects_payload,
    get_corrections,
    get_date_briefing_payload,
    get_date_detail,
    get_date_meta_payload,
    get_onboarding_payload,
    get_stats,
    handle_correction,
    load_active_context_snapshot,
    search_content,
)
from app.pipeline_api import (
    build_pipeline_command,
    get_pipeline_job_payload,
    get_pipeline_jobs_payload,
    handle_create_pipeline_job,
    run_pipeline_job_command,
)
from openmy.services.cleaning.cleaner import sync_correction_to_vocab
from openmy.services.segmentation.segmenter import parse_time_segments
from openmy.utils.paths import DATA_ROOT, LEGACY_ROOT, PROJECT_ROOT as ROOT_DIR

try:
    from openmy.adapters.screen_recognition.client import ScreenRecognitionClient

    _screen_context_client = ScreenRecognitionClient()
    _screen_context_available = _screen_context_client.is_available()
except Exception:
    _screen_context_client = None
    _screen_context_available = False

CORRECTIONS_FILE = ROOT_DIR / "src" / "openmy" / "resources" / "corrections.json"
PORT = 8420
DEFAULT_HOST = "127.0.0.1"
TIME_HEADER_RE = re.compile(r"^##\s+(\d{1,2}:\d{2})", re.MULTILINE)
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
DATE_MD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
JOB_RUNNER = JobRunner()


def list_dates() -> list[str]:
    dates: set[str] = set()
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
    return sort_dates_for_display(list(dates))


def parse_date_value(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def sort_dates_for_display(dates: list[str], today: str | None = None) -> list[str]:
    ordered_dates = sorted(set(dates), reverse=True)
    if not ordered_dates:
        return []

    today_value = parse_date_value(today) if today else datetime.now().date()
    if today and today_value is None:
        return ordered_dates

    non_future_dates = []
    future_dates = []
    for value in ordered_dates:
        parsed = parse_date_value(value)
        if parsed and parsed <= today_value:
            non_future_dates.append(value)
        else:
            future_dates.append(value)
    return non_future_dates + future_dates


def choose_default_date(dates: list[str], today: str | None = None) -> str | None:
    ordered_dates = sort_dates_for_display(dates, today=today)
    return ordered_dates[0] if ordered_dates else None


def resolve_day_paths(date: str) -> dict[str, Path]:
    day_dir = DATA_ROOT / date
    dated_meta_path = day_dir / f"{date}.meta.json"
    legacy_meta_path = day_dir / "meta.json"
    paths = {
        "transcript": day_dir / "transcript.md",
        "raw": day_dir / "transcript.raw.md",
        "meta": dated_meta_path if dated_meta_path.exists() or not legacy_meta_path.exists() else legacy_meta_path,
        "scenes": day_dir / "scenes.json",
    }
    if paths["transcript"].exists():
        return paths

    return {
        "transcript": LEGACY_ROOT / f"{date}.md",
        "raw": LEGACY_ROOT / f"{date}.raw.md",
        "meta": LEGACY_ROOT / f"{date}.meta.json",
        "scenes": LEGACY_ROOT / f"{date}.scenes.json",
    }


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def _resolve_item(items: list, query: str, candidate_getter):
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


def build_server(host: str = DEFAULT_HOST, port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), BrainHandler)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="OpenMy 本地网页服务")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址，默认仅本机可见")
    parser.add_argument("--port", type=int, default=PORT, help="监听端口")
    args = parser.parse_args(argv)

    print("🧠 OpenMy v3（OpenMy package 版）")
    print(f"📂 数据目录: {DATA_ROOT}")
    stats = get_stats()
    print(f"📊 {stats['total_dates']} 天 | {stats['total_segments']} 段 | {stats['total_words']} 字")
    if stats["role_distribution"]:
        print(f"🏷️ 角色分布: {json.dumps(stats['role_distribution'], ensure_ascii=False)}")
    if _screen_context_available:
        print("🖥️ 屏幕上下文已连接")
    else:
        print("🖥️ 屏幕上下文未检测到（系统会退化为纯语音模式）")
    print(f"🌐 http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止\n")

    server = build_server(host=args.host, port=args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
