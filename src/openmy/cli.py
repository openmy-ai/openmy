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
from rich.panel import Panel as _RichPanel

from openmy.commands import common as common_cmd
from openmy.commands import context as context_cmd
from openmy.commands import correct as correct_cmd
from openmy.commands import menu as menu_cmd
from openmy.commands import run as run_cmd
from openmy.commands import screen as screen_cmd
from openmy.commands import self_update as self_update_cmd
from openmy.utils.errors import FriendlyCliError
from openmy.utils.paths import DATA_ROOT, LEGACY_ROOT as _LEGACY_ROOT, PROJECT_ENV_PATH as _PROJECT_ENV_PATH, PROJECT_ROOT as _ROOT_DIR
from openmy.services.feedback import ensure_install_time

console = common_cmd.console
Console, Panel = _RichConsole, _RichPanel


def Markdown(*args, **kwargs):
    from rich.markdown import Markdown as _RichMarkdown

    return _RichMarkdown(*args, **kwargs)
PROJECT_ENV_PATH, ROOT_DIR, LEGACY_ROOT = _PROJECT_ENV_PATH, _ROOT_DIR, _LEGACY_ROOT
DATE_RE, DATE_MD_RE, AUDIO_TIME_RE, DATE_IN_FILENAME_RE, ROLE_COLORS = (
    common_cmd.DATE_RE,
    common_cmd.DATE_MD_RE,
    common_cmd.AUDIO_TIME_RE,
    common_cmd.DATE_IN_FILENAME_RE,
    common_cmd.ROLE_COLORS,
)
common_cmd.HELP_IN_ENGLISH = common_cmd._prefers_english_help()
HELP_IN_ENGLISH = common_cmd.HELP_IN_ENGLISH
(
    _prefers_english_help,
    _help_text,
    render_friendly_error,
    project_version,
    maybe_get_update_hint,
    clear_project_runtime_env,
    load_project_env,
    prepare_project_runtime_env,
    missing_stt_key_message,
    missing_stt_key_hint,
    missing_provider_key_message,
    add_stt_runtime_args,
    get_stt_provider_name,
    get_stt_api_key,
    get_llm_api_key,
    stt_provider_requires_api_key,
    _local_report_health_url,
    is_local_report_running,
    is_local_report_healthy,
    find_report_pids,
    kill_report_processes,
    wait_for_local_report,
    write_json,
    get_screen_client,
) = (
    common_cmd._prefers_english_help,
    common_cmd._help_text,
    common_cmd.render_friendly_error,
    common_cmd.project_version,
    common_cmd.maybe_get_update_hint,
    common_cmd.clear_project_runtime_env,
    common_cmd.load_project_env,
    common_cmd.prepare_project_runtime_env,
    common_cmd.missing_stt_key_message,
    common_cmd.missing_stt_key_hint,
    common_cmd.missing_provider_key_message,
    common_cmd.add_stt_runtime_args,
    common_cmd.get_stt_provider_name,
    common_cmd.get_stt_api_key,
    common_cmd.get_llm_api_key,
    common_cmd.stt_provider_requires_api_key,
    common_cmd._local_report_health_url,
    common_cmd.is_local_report_running,
    common_cmd.is_local_report_healthy,
    common_cmd.find_report_pids,
    common_cmd.kill_report_processes,
    common_cmd.wait_for_local_report,
    common_cmd.write_json,
    common_cmd.get_screen_client,
)
(
    _show_main_menu,
    _cmd_correct_typo,
    _load_context_snapshot,
    _normalize_match_text,
    _score_match,
    _resolve_item,
    _append_context_correction,
    _cmd_correct_scene_role,
    cmd_correct_list,
    transcribe_audio_files,
    cmd_run,
    cmd_quick_start,
) = (
    menu_cmd._show_main_menu,
    correct_cmd._cmd_correct_typo,
    correct_cmd._load_context_snapshot,
    correct_cmd._normalize_match_text,
    correct_cmd._score_match,
    correct_cmd._resolve_item,
    correct_cmd._append_context_correction,
    correct_cmd._cmd_correct_scene_role,
    correct_cmd.cmd_correct_list,
    run_cmd.transcribe_audio_files,
    run_cmd.cmd_run,
    run_cmd.cmd_quick_start,
)
_SHOW_CMD = None


def _get_show_cmd():
    global _SHOW_CMD
    if _SHOW_CMD is None:
        from openmy.commands import show as show_module

        _SHOW_CMD = show_module
        _sync_show_runtime_overrides(show_module)
    return _SHOW_CMD


def _sync_show_runtime_overrides(show_module=None) -> None:
    show_module = show_module or _SHOW_CMD
    if show_module is None:
        return
    show_module.console = console
    show_module.DATA_ROOT = DATA_ROOT
    show_module.LEGACY_ROOT = LEGACY_ROOT


def _show_call(name: str, *args, **kwargs):
    _sync_runtime_overrides()
    return getattr(_get_show_cmd(), name)(*args, **kwargs)


def _show_func(name: str):
    def wrapper(*args, **kwargs):
        return _show_call(name, *args, **kwargs)

    wrapper.__name__ = name
    return wrapper


_render_review = _show_func("_render_review")
find_all_dates = _show_func("find_all_dates")
ensure_day_dir = _show_func("ensure_day_dir")
get_date_status = _show_func("get_date_status")
resolve_day_paths = _show_func("resolve_day_paths")
read_scenes_payload = _show_func("read_scenes_payload")
build_segmented_scenes_payload = _show_func("build_segmented_scenes_payload")
cmd_status = _show_func("cmd_status")
cmd_view = _show_func("cmd_view")
cmd_clean = _show_func("cmd_clean")
cmd_roles = _show_func("cmd_roles")
cmd_distill = _show_func("cmd_distill")
cmd_briefing = _show_func("cmd_briefing")
cmd_extract = _show_func("cmd_extract")
cmd_query = _show_func("cmd_query")
cmd_weekly = _show_func("cmd_weekly")
cmd_monthly = _show_func("cmd_monthly")
cmd_watch = _show_func("cmd_watch")
cmd_feedback = _show_func("cmd_feedback")
read_json = _show_func("read_json")
strip_document_header = _show_func("strip_document_header")
stage_label = _show_func("stage_label")
role_bar = _show_func("role_bar")
parse_audio_time = _show_func("parse_audio_time")
infer_date_from_path = _show_func("infer_date_from_path")
infer_scene_role_profile = _show_func("infer_scene_role_profile")
rebuild_scene_stats = _show_func("rebuild_scene_stats")
build_frozen_scene_stats = _show_func("build_frozen_scene_stats")
freeze_scene_roles = _show_func("freeze_scene_roles")


def _upsert_project_env(key: str, value: str):
    common_cmd.PROJECT_ENV_PATH = PROJECT_ENV_PATH
    return common_cmd._upsert_project_env(key, value)


def _sync_runtime_overrides() -> None:
    _set_console_for_modules(console)
    common_cmd.DATA_ROOT = DATA_ROOT
    common_cmd.PROJECT_ENV_PATH = PROJECT_ENV_PATH
    common_cmd.ROOT_DIR = ROOT_DIR
    _sync_show_runtime_overrides()
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


cmd_screen, cmd_correct, cmd_context = (
    _sync_wrapper(screen_cmd.cmd_screen),
    _sync_wrapper(correct_cmd.cmd_correct),
    _sync_wrapper(context_cmd.cmd_context),
)

def _print_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _set_console_for_modules(new_console) -> None:
    global console
    console = new_console
    common_cmd.console = new_console
    _sync_show_runtime_overrides()
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

from openmy.commands.parser import build_parser

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
