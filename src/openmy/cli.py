#!/usr/bin/env python3
"""OpenMy — 个人上下文引擎 CLI."""

from __future__ import annotations

import argparse
import io
import json
import shutil  # noqa: F401
import subprocess  # noqa: F401
import sys
import webbrowser  # noqa: F401
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from rich.console import Console as _RichConsole
from rich.markdown import Markdown as _RichMarkdown
from rich.panel import Panel as _RichPanel


from openmy.commands import common as common_cmd
from openmy.commands import context as context_cmd
from openmy.commands import correct as correct_cmd
from openmy.commands import menu as menu_cmd
from openmy.commands import run as run_cmd
from openmy.commands import screen as screen_cmd
from openmy.commands import show as show_cmd
from openmy.commands import self_update as self_update_cmd
from openmy.utils.errors import FriendlyCliError
from openmy.utils.paths import DATA_ROOT, LEGACY_ROOT as _LEGACY_ROOT, PROJECT_ENV_PATH as _PROJECT_ENV_PATH, PROJECT_ROOT as _ROOT_DIR
from openmy.services.feedback import ensure_install_time

console = common_cmd.console
for _name, _value in {
    "Console": _RichConsole,
    "Markdown": _RichMarkdown,
    "Panel": _RichPanel,
    "PROJECT_ENV_PATH": _PROJECT_ENV_PATH,
    "ROOT_DIR": _ROOT_DIR,
    "LEGACY_ROOT": _LEGACY_ROOT,
}.items():
    globals()[_name] = _value
for _name in ("DATE_RE", "DATE_MD_RE", "AUDIO_TIME_RE", "DATE_IN_FILENAME_RE", "ROLE_COLORS"):
    globals()[_name] = getattr(common_cmd, _name)
common_cmd.HELP_IN_ENGLISH = common_cmd._prefers_english_help()
HELP_IN_ENGLISH = common_cmd.HELP_IN_ENGLISH
for _name in (
    "_prefers_english_help",
    "_help_text",
    "render_friendly_error",
    "project_version",
    "maybe_get_update_hint",
    "clear_project_runtime_env",
    "load_project_env",
    "prepare_project_runtime_env",
    "missing_stt_key_message",
    "missing_stt_key_hint",
    "missing_provider_key_message",
    "add_stt_runtime_args",
    "get_stt_provider_name",
    "get_stt_api_key",
    "get_llm_api_key",
    "stt_provider_requires_api_key",
    "_local_report_health_url",
    "is_local_report_running",
    "is_local_report_healthy",
    "find_report_pids",
    "kill_report_processes",
    "wait_for_local_report",
    "write_json",
    "get_screen_client",
):
    globals()[_name] = getattr(common_cmd, _name)
for _name, _module in {
    "_show_main_menu": menu_cmd,
    "_render_review": show_cmd,
    "_cmd_correct_typo": correct_cmd,
    "_load_context_snapshot": correct_cmd,
    "_normalize_match_text": correct_cmd,
    "_score_match": correct_cmd,
    "_resolve_item": correct_cmd,
    "_append_context_correction": correct_cmd,
    "_cmd_correct_scene_role": correct_cmd,
    "cmd_correct_list": correct_cmd,
    "transcribe_audio_files": run_cmd,
    "cmd_run": run_cmd,
    "cmd_quick_start": run_cmd,
}.items():
    globals()[_name] = getattr(_module, _name)

def _upsert_project_env(key: str, value: str):
    common_cmd.PROJECT_ENV_PATH = PROJECT_ENV_PATH
    return common_cmd._upsert_project_env(key, value)


def _sync_runtime_overrides() -> None:
    _set_console_for_modules(console)
    common_cmd.DATA_ROOT = DATA_ROOT
    common_cmd.PROJECT_ENV_PATH = PROJECT_ENV_PATH
    common_cmd.ROOT_DIR = ROOT_DIR
    show_cmd.DATA_ROOT = DATA_ROOT
    show_cmd.LEGACY_ROOT = LEGACY_ROOT
    common_cmd.get_stt_provider_name = get_stt_provider_name
    common_cmd.get_stt_api_key = get_stt_api_key
    common_cmd.get_llm_api_key = get_llm_api_key
    common_cmd.load_project_env = load_project_env
    common_cmd.prepare_project_runtime_env = prepare_project_runtime_env
    common_cmd.shutil = shutil
    common_cmd.subprocess = subprocess
    common_cmd.webbrowser = webbrowser
    common_cmd.is_local_report_running = is_local_report_running
    common_cmd.is_local_report_healthy = is_local_report_healthy
    common_cmd.kill_report_processes = kill_report_processes
    common_cmd.wait_for_local_report = wait_for_local_report


def ensure_runtime_dependencies(*, stt_provider: str | None = None) -> None:
    _sync_runtime_overrides()
    return common_cmd.ensure_runtime_dependencies(stt_provider=stt_provider)


def launch_local_report(host: str = "127.0.0.1", port: int = 8420) -> None:
    _sync_runtime_overrides()
    return common_cmd.launch_local_report(host=host, port=port)

def _sync_wrapper(func):
    return lambda *args, **kwargs: (_sync_runtime_overrides(), func(*args, **kwargs))[1]


for _name in (
    "find_all_dates",
    "ensure_day_dir",
    "get_date_status",
    "resolve_day_paths",
    "read_scenes_payload",
    "build_segmented_scenes_payload",
    "cmd_status",
    "cmd_view",
    "cmd_clean",
    "cmd_roles",
    "cmd_distill",
    "cmd_briefing",
    "cmd_extract",
    "cmd_query",
    "cmd_weekly",
    "cmd_monthly",
    "cmd_watch",
    "cmd_feedback",
):
    globals()[_name] = _sync_wrapper(getattr(show_cmd, _name))
for _name in ("read_json", "strip_document_header", "stage_label", "role_bar", "parse_audio_time", "infer_date_from_path", "infer_scene_role_profile", "rebuild_scene_stats", "build_frozen_scene_stats", "freeze_scene_roles"):
    globals()[_name] = getattr(show_cmd, _name)
cmd_screen = _sync_wrapper(screen_cmd.cmd_screen)
cmd_correct = _sync_wrapper(correct_cmd.cmd_correct)
cmd_context = _sync_wrapper(context_cmd.cmd_context)

def _print_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _set_console_for_modules(new_console) -> None:
    global console
    console = new_console
    common_cmd.console = new_console
    show_cmd.console = new_console
    menu_cmd.console = new_console
    screen_cmd.console = new_console
    screen_cmd._upsert_project_env = _upsert_project_env
    correct_cmd.console = new_console


def _run_with_silent_console(func, *args, **kwargs):
    original_console = console
    silent_console = common_cmd.Console(file=io.StringIO(), force_terminal=False, color_system=None)
    _set_console_for_modules(silent_console)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        _set_console_for_modules(original_console)


def cmd_skill(args: argparse.Namespace) -> int:
    """稳定 JSON 动作入口。"""
    from openmy.skill_dispatch import dispatch_skill_action

    payload, exit_code = dispatch_skill_action(args.action, args)
    _print_json(payload)
    return exit_code


def cmd_agent(args: argparse.Namespace) -> int:
    action = None
    if getattr(args, "recent", False):
        action = "context.get"
    elif getattr(args, "day", None):
        action = "day.get"
    elif getattr(args, "ingest", None):
        action = "day.run"
    elif getattr(args, "reject_decision", None):
        action = "correction.apply"
    elif getattr(args, "query", None) is not None:
        action = "context.query"

    if action is None:
        console.print("[red]❌ agent 入口需要指定动作[/red]")
        return 1

    from openmy.skill_dispatch import dispatch_skill_action

    skill_args = argparse.Namespace(**vars(args))
    setattr(skill_args, "compact", getattr(skill_args, "compact", False))
    setattr(skill_args, "level", getattr(skill_args, "level", 1))
    setattr(skill_args, "status", getattr(skill_args, "status", "done"))
    setattr(skill_args, "include_evidence", getattr(skill_args, "include_evidence", False))
    if action == "day.get":
        setattr(skill_args, "date", getattr(args, "day", None))
        payload, exit_code = dispatch_skill_action(action, skill_args)
    elif action == "day.run":
        setattr(skill_args, "date", getattr(args, "ingest", None))
        final_stt_provider = getattr(args, "stt_provider", None) or common_cmd.get_stt_provider_name()
        common_cmd.prepare_project_runtime_env()
        try:
            if not getattr(args, "skip_transcribe", False):
                common_cmd.ensure_runtime_dependencies(stt_provider=final_stt_provider)
        except FriendlyCliError as exc:
            payload = {
                "ok": False,
                "action": action,
                "version": "v1",
                "error": exc.code or "dependency_check_failed",
                "message": exc.message,
                "human_summary": exc.message,
                "next_actions": [exc.fix] if getattr(exc, "fix", "") else [],
                "artifacts": {},
                "data": {},
            }
            _print_json(payload)
            return 1
        payload, exit_code = dispatch_skill_action(action, skill_args)
    elif action == "correction.apply":
        setattr(skill_args, "op", "reject-decision")
        setattr(skill_args, "arg", [getattr(args, "reject_decision", "")])
        payload, exit_code = dispatch_skill_action(action, skill_args)
    elif action == "context.query":
        setattr(skill_args, "kind", getattr(args, "query_kind", "project"))
        setattr(skill_args, "query", getattr(args, "query", ""))
        payload, exit_code = dispatch_skill_action(action, skill_args)
    else:
        payload, exit_code = dispatch_skill_action(action, skill_args)

    _print_json(payload)
    return exit_code


cmd_self_update = self_update_cmd.cmd_self_update

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openmy",
        description=_help_text("🎙️ OpenMy — 个人上下文引擎", "🎙️ OpenMy — personal context engine"),
    )
    sub = parser.add_subparsers(dest="command", help=_help_text("可用命令", "Available commands"))

    sub.add_parser("status", help=_help_text("列出所有日期及处理状态", "List all processed dates and their status."))

    p_view = sub.add_parser("view", help=_help_text("终端查看某天的概览", "View one day's summary in the terminal."))
    p_view.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_clean = sub.add_parser("clean", help=_help_text("清洗转写文本", "Clean one day's transcript text."))
    p_clean.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_roles = sub.add_parser("roles", help=_help_text("切场景 + 角色归因", "Split scenes and resolve who was speaking to whom."))
    p_roles.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_distill = sub.add_parser("distill", help=_help_text("蒸馏摘要（需要项目 `.env` 里的 LLM key）", "Create scene summaries. Requires an LLM key in the project .env file."))
    p_distill.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_brief = sub.add_parser("briefing", help=_help_text("生成日报", "Generate the daily briefing."))
    p_brief.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_extract = sub.add_parser("extract", help=_help_text("从转写中提取 intents / facts", "Extract intents and facts from a cleaned transcript."))
    p_extract.add_argument("input_file", help=_help_text("清洗后的 Markdown 文件路径", "Path to the cleaned Markdown transcript."))
    p_extract.add_argument("--date", help=_help_text("日期 YYYY-MM-DD，默认从文件名推断", "Date in YYYY-MM-DD format. Defaults to the date inferred from the filename."))
    p_extract.add_argument("--model", default=None, help=_help_text("LLM 模型（默认取项目 `.env` 或内置默认值）", "LLM model name. Defaults to the model configured in the project .env file or the built-in default."))
    p_extract.add_argument("--vault-path", help=_help_text("Obsidian Vault 路径", "Path to the Obsidian vault."))
    p_extract.add_argument("--api-key", help=_help_text("LLM API key", "LLM API key."))
    p_extract.add_argument("--dry-run", action="store_true", help=_help_text("只打印提取结果，不写入文件", "Print the extraction result without writing files."))

    p_run = sub.add_parser("run", help=_help_text("全流程处理", "Run the full daily pipeline."))
    p_run.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))
    p_run.add_argument("--audio", nargs="+", help=_help_text("音频文件路径", "Audio file paths."))
    p_run.add_argument("--skip-transcribe", action="store_true", help=_help_text("跳过转写（使用已有数据）", "Skip transcription and reuse existing data."))
    p_run.add_argument("--skip-aggregate", action="store_true", help=_help_text("跳过周/月聚合", "Skip weekly and monthly aggregation."))
    add_stt_runtime_args(p_run)

    p_quick = sub.add_parser("quick-start", help=_help_text("第一次使用：自动处理音频并打开本地日报", "First-run guided flow: process audio and open the local report."))
    p_quick.add_argument("audio_path", nargs="?", help=_help_text("音频文件路径；传 --demo 时可不填", "Audio file path. Optional when you pass --demo."))
    p_quick.add_argument("--demo", action="store_true", help=_help_text("使用内置示例音频跑一遍主链", "Run the bundled demo flow."))
    p_quick.add_argument("--skip-aggregate", action="store_true", help=_help_text("跳过周/月聚合", "Skip weekly and monthly aggregation."))
    add_stt_runtime_args(p_quick)

    p_correct = sub.add_parser("correct", help=_help_text("纠正转写或活动上下文", "Correct transcripts or active context data."))
    p_correct.add_argument("correct_args", nargs="*", help=_help_text("纠错参数", "Correction arguments."))
    p_correct.add_argument("--status", default="done", choices=["done", "abandoned"], help=_help_text("close-loop 的关闭状态", "Status to use when closing a loop."))

    p_context = sub.add_parser("context", help=_help_text("生成/查看活动上下文", "Generate or inspect active context."))
    p_context.add_argument("--compact", action="store_true", help=_help_text("输出 Markdown 压缩版", "Render the compact Markdown view."))
    p_context.add_argument("--level", type=int, default=1, choices=[0, 1], help=_help_text("输出层级 (0=极简, 1=完整)", "Output level: 0 for minimal, 1 for full detail."))

    p_weekly = sub.add_parser("weekly", help=_help_text("查看本周回顾", "Show the weekly review."))
    p_weekly.add_argument("--week", help=_help_text("指定周，例如 2026-W15", "Specific ISO week, for example 2026-W15."))

    p_monthly = sub.add_parser("monthly", help=_help_text("查看本月回顾", "Show the monthly review."))
    p_monthly.add_argument("--month", help=_help_text("指定月，例如 2026-04", "Specific month, for example 2026-04."))

    p_watch = sub.add_parser("watch", help=_help_text("监控录音文件夹", "Watch an audio folder for new recordings."))
    p_watch.add_argument("directory", nargs="?", help=_help_text("监控目录；不传就用已配置的录音固定目录", "Directory to watch. Defaults to the configured audio source folder."))

    p_feedback = sub.add_parser("feedback", help=_help_text("管理本地反馈记录", "Manage local feedback tracking."))
    p_feedback.add_argument("--show", action="store_true", help=_help_text("查看当前本地反馈记录", "Show the current local feedback record."))
    p_feedback.add_argument("--opt-in", action="store_true", help=_help_text("开启本地反馈记录", "Enable local feedback tracking."))
    p_feedback.add_argument("--opt-out", action="store_true", help=_help_text("关闭本地反馈记录", "Disable local feedback tracking."))
    p_feedback.add_argument("--delete", action="store_true", help=_help_text("删除本地反馈记录", "Delete local feedback records."))

    p_screen = sub.add_parser("screen", help=_help_text("开关屏幕识别", "Turn screen recognition on or off."))
    p_screen.add_argument("action", choices=["on", "off", "status"], help=_help_text("on=开启，off=关闭，status=查看状态", "Use on to enable, off to disable, and status to inspect the current state."))

    sub.add_parser("self-update", help=_help_text("升级当前 OpenMy 安装", "Upgrade the current OpenMy installation."))

    p_screen_loop = sub.add_parser("_screen-capture-loop", help=argparse.SUPPRESS)
    p_screen_loop.add_argument("action", nargs="?", default="daemon", help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--interval", type=int, default=5, help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--retention-hours", type=int, default=24, help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--data-root", default=str(DATA_ROOT), help=argparse.SUPPRESS)

    p_query = sub.add_parser("query", help=_help_text("基于结构化上下文查询项目/人物/待办/证据", "Query projects, people, open loops, or evidence from structured context."))
    p_query.add_argument("--kind", required=True, choices=["project", "person", "open", "closed", "evidence", "decision"])
    p_query.add_argument("--query", default="", help=_help_text("查询关键词（project / person / evidence 必填）", "Search keyword. Required for project, person, and evidence queries."))
    p_query.add_argument("--limit", type=int, default=5, help=_help_text("最多返回多少条命中", "Maximum number of matches to return."))
    p_query.add_argument("--include-evidence", action="store_true", help=_help_text("返回证据来源", "Include evidence references in the output."))
    p_query.add_argument("--json", action="store_true", help=_help_text("输出 JSON", "Output JSON."))

    p_agent = sub.add_parser("agent", help=_help_text("给 Agent 调用的统一入口", "Compatibility entrypoint for agents."))
    agent_mode = p_agent.add_mutually_exclusive_group(required=True)
    agent_mode.add_argument("--recent", action="store_true", help=_help_text("读取最近整体状态", "Read the recent overall status."))
    agent_mode.add_argument("--day", help=_help_text("查看某天结果 YYYY-MM-DD", "Read one processed day in YYYY-MM-DD format."))
    agent_mode.add_argument("--ingest", help=_help_text("处理某天输入 YYYY-MM-DD", "Process one day's input in YYYY-MM-DD format."))
    agent_mode.add_argument("--reject-decision", dest="reject_decision", help=_help_text("排除一条不重要的决策", "Reject one decision that should not be kept."))
    agent_mode.add_argument("--query", help=_help_text("按结构化结果查询项目/人物/待办/证据", "Query projects, people, open loops, or evidence from structured context."))
    p_agent.add_argument("--query-kind", default="project", choices=["project", "person", "open", "closed", "evidence", "decision"])
    p_agent.add_argument("--limit", type=int, default=5, help=_help_text("给 --query 使用", "Maximum results for --query."))
    p_agent.add_argument("--include-evidence", action="store_true", help=_help_text("给 --query 使用：带上证据来源", "Include evidence references for --query."))
    p_agent.add_argument("--audio", nargs="+", help=_help_text("给 --ingest 使用的音频文件路径", "Audio file paths for --ingest."))
    p_agent.add_argument("--skip-transcribe", action="store_true", help=_help_text("给 --ingest 使用：复用已有数据", "Reuse existing data for --ingest instead of transcribing again."))
    p_agent.add_argument("--skip-aggregate", action="store_true", help=_help_text("给 --ingest 使用：跳过周/月聚合", "Skip weekly and monthly aggregation for --ingest."))
    add_stt_runtime_args(p_agent)

    p_skill = sub.add_parser("skill", help=_help_text("稳定 JSON 动作入口", "Stable JSON action entrypoint."))
    p_skill.add_argument("action", help=_help_text("稳定动作名", "Stable action name."))
    p_skill.add_argument("--date", help=_help_text("给 day.get / day.run 使用的日期 YYYY-MM-DD", "Date for day.get or day.run in YYYY-MM-DD format."))
    p_skill.add_argument("--audio", nargs="+", help=_help_text("给 day.run 使用的音频文件路径", "Audio file paths for day.run."))
    p_skill.add_argument("--skip-transcribe", action="store_true", help=_help_text("给 day.run 使用：复用已有数据", "Reuse existing data for day.run instead of transcribing again."))
    p_skill.add_argument("--skip-aggregate", action="store_true", help=_help_text("给 day.run 使用：跳过周/月聚合", "Skip weekly and monthly aggregation for day.run."))
    add_stt_runtime_args(p_skill)
    p_skill.add_argument("--correct-args", nargs="*", help=_help_text("给 correction.apply 透传的参数", "Raw correction arguments for correction.apply."))
    p_skill.add_argument("--op", help=_help_text("给 correction.apply 使用的动作名，如 close-loop", "Operation name for correction.apply, for example close-loop."))
    p_skill.add_argument("--arg", action="append", help=_help_text("给 correction.apply 使用的动作参数，可重复", "Repeated operation arguments for correction.apply."))
    p_skill.add_argument("--status", default="done", choices=["done", "abandoned"], help=_help_text("给 correction.apply 使用的 close-loop 状态", "Loop-closing status for correction.apply."))
    p_skill.add_argument("--kind", choices=["project", "person", "open", "closed", "evidence", "decision"], help=_help_text("给 context.query 使用", "Query kind for context.query."))
    p_skill.add_argument("--query", default="", help=_help_text("给 context.query 使用的查询词", "Search query for context.query."))
    p_skill.add_argument("--limit", type=int, default=5, help=_help_text("给 context.query 使用的最大命中数", "Maximum number of matches for context.query."))
    p_skill.add_argument("--include-evidence", action="store_true", help=_help_text("给 context.query 返回证据来源", "Include evidence references for context.query."))
    p_skill.add_argument("--level", type=int, default=1, choices=[0, 1], help=_help_text("给 context.get 使用的层级", "Output level for context.get."))
    p_skill.add_argument("--compact", action="store_true", help=_help_text("给 context.get 输出压缩 Markdown", "Render compact Markdown for context.get."))
    p_skill.add_argument("--name", help=_help_text("给 profile.set 使用的名字", "Name for profile.set."))
    p_skill.add_argument("--language", help=_help_text("给 profile.set 使用的语言", "Language for profile.set."))
    p_skill.add_argument("--timezone", help=_help_text("给 profile.set 使用的时区", "Timezone for profile.set."))
    p_skill.add_argument("--audio-source", help=_help_text("给 profile.set 使用的录音固定目录", "Fixed audio source directory for profile.set."))
    p_skill.add_argument("--export-provider", choices=["obsidian", "notion"], help=_help_text("给 profile.set 使用的导出目标", "Export target for profile.set."))
    p_skill.add_argument("--export-path", help=_help_text("给 profile.set 使用的 Obsidian 目录", "Obsidian vault path for profile.set."))
    p_skill.add_argument("--export-key", help=_help_text("给 profile.set 使用的 Notion key", "Notion API key for profile.set."))
    p_skill.add_argument("--export-db", help=_help_text("给 profile.set 使用的 Notion 数据库编号", "Notion database ID for profile.set."))
    p_skill.add_argument("--screen-recognition", choices=["on", "off"], help=_help_text("给 profile.set 使用的屏幕识别开关", "Screen recognition toggle for profile.set."))
    p_skill.add_argument("--week", help=_help_text("给 aggregate 使用的周，例如 2026-W15", "ISO week for aggregate, for example 2026-W15."))
    p_skill.add_argument("--month", help=_help_text("给 aggregate 使用的月，例如 2026-04", "Month for aggregate, for example 2026-04."))
    p_skill.add_argument("--payload-json", help=_help_text("给 submit 类动作使用的 JSON 字符串", "JSON string payload for submit actions."))
    p_skill.add_argument("--payload-file", help=_help_text("给 submit 类动作使用的 JSON 文件路径", "JSON file payload for submit actions."))
    p_skill.add_argument("--json", action="store_true", help=_help_text("兼容参数；skill 默认输出 JSON", "Compatibility flag. Skill commands already output JSON by default."))

    return parser


def main_with_args(args: argparse.Namespace, parser: argparse.ArgumentParser | None = None) -> int:
    parser = parser or build_parser()
    prepare_project_runtime_env()
    ensure_install_time()
    if not args.command:
        latest_version = maybe_get_update_hint()
        if latest_version:
            console.print(f"[dim]有新版本 {latest_version} 可用。想升级就运行 openmy self-update。[/dim]")
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
        "feedback": cmd_feedback,
        "query": cmd_query,
        "quick-start": cmd_quick_start,
        "roles": cmd_roles,
        "run": cmd_run,
        "screen": cmd_screen,
        "self-update": cmd_self_update,
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
        if args.command not in {"skill", "agent", "_screen-capture-loop", "self-update"}:
            latest_version = maybe_get_update_hint()
            if latest_version:
                console.print(f"[dim]有新版本 {latest_version} 可用。想升级就运行 openmy self-update。[/dim]")
        return handler(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]已中断[/yellow]")
        return 130
    except FriendlyCliError as exc:
        render_friendly_error(exc)
        return 1
    except Exception:
        console.print_exception(show_locals=False)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return main_with_args(args, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
