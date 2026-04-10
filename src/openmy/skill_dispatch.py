from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable


SKILL_CONTRACT_VERSION = "v1"


class SkillDispatchError(RuntimeError):
    def __init__(
        self,
        *,
        action: str,
        error_code: str,
        message: str,
        hint: str = "",
        exit_code: int = 1,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.action = action
        self.error_code = error_code
        self.message = message
        self.hint = hint
        self.exit_code = exit_code
        self.data = data or {}


def _cli():
    from openmy import cli as cli_module

    return cli_module


def _read_json(path: Path, default: Any) -> Any:
    return _cli().read_json(path, default)


def _day_run_status_path(date_str: str) -> Path:
    return _cli().ensure_day_dir(date_str) / "run_status.json"


def build_success_payload(
    *,
    action: str,
    data: dict[str, Any] | None = None,
    human_summary: str,
    artifacts: dict[str, Any] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "action": action,
        "version": SKILL_CONTRACT_VERSION,
        "data": data or {},
        "human_summary": human_summary,
        "artifacts": artifacts or {},
        "next_actions": next_actions or [],
    }


def build_error_payload(
    *,
    action: str,
    error_code: str,
    message: str,
    hint: str = "",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "ok": False,
        "action": action,
        "version": SKILL_CONTRACT_VERSION,
        "error_code": error_code,
        "message": message,
    }
    if hint:
        payload["hint"] = hint
    if data:
        payload["data"] = data
    return payload


def build_correction_tokens(args: argparse.Namespace) -> list[str]:
    if getattr(args, "correct_args", None):
        return list(args.correct_args)

    op = str(getattr(args, "op", "") or "").strip()
    extra_args = [str(item).strip() for item in (getattr(args, "arg", None) or []) if str(item).strip()]
    if not op:
        return []
    return [op, *extra_args]


def _run_existing_command(command: str, args: argparse.Namespace) -> int:
    cli = _cli()

    if command == "day.run":
        return int(
            cli._run_with_silent_console(
                cli.cmd_run,
                argparse.Namespace(
                    date=args.date,
                    audio=args.audio,
                    skip_transcribe=args.skip_transcribe,
                ),
            )
        )

    if command == "correction.apply":
        return int(
            cli._run_with_silent_console(
                cli.cmd_correct,
                argparse.Namespace(
                    correct_args=build_correction_tokens(args),
                    status=args.status,
                ),
            )
        )

    raise ValueError(f"unsupported bridge command: {command}")


def _require_date(action: str, date_str: str | None) -> str:
    final_date = str(date_str or "").strip()
    if not final_date:
        raise SkillDispatchError(
            action=action,
            error_code="missing_date",
            message="缺少日期参数。",
            hint="请传入 --date YYYY-MM-DD。",
        )
    return final_date


def _format_day_summary(date_str: str, status: dict[str, Any]) -> str:
    if status.get("has_briefing"):
        return f"{date_str} 已有日报；共 {status.get('scene_count', 0)} 个场景。"
    if status.get("has_scenes"):
        return f"{date_str} 已切好场景；共 {status.get('scene_count', 0)} 个场景。"
    if status.get("has_transcript"):
        return f"{date_str} 已有转写；还没产出日报。"
    return f"{date_str} 还没有可用数据。"


def handle_status_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    cli = _cli()
    items = []
    for date_str in cli.find_all_dates():
        item = dict(cli.get_date_status(date_str))
        item["date"] = date_str
        items.append(item)

    latest_date = items[0]["date"] if items else ""
    human_summary = "还没有任何 OpenMy 数据。" if not items else f"共有 {len(items)} 天数据；最近一天是 {latest_date}。"
    payload = build_success_payload(
        action="status.get",
        data={
            "items": items,
            "total_days": len(items),
            "latest_date": latest_date,
        },
        human_summary=human_summary,
        artifacts={"data_root": str(cli.DATA_ROOT)},
        next_actions=[] if items else ["先处理一天音频，再回来查看整体状态。"],
    )
    return (payload, 0)


def handle_day_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    cli = _cli()
    date_str = _require_date("day.get", getattr(args, "date", None))
    paths = cli.resolve_day_paths(date_str)
    status = cli.get_date_status(date_str)
    payload = build_success_payload(
        action="day.get",
        data={
            "date": date_str,
            "status": status,
            "briefing": _read_json(paths["briefing"], None) if paths["briefing"].exists() else None,
            "scenes": _read_json(paths["scenes"], None) if paths["scenes"].exists() else None,
            "meta": _read_json(paths["dir"] / f"{date_str}.meta.json", None)
            if (paths["dir"] / f"{date_str}.meta.json").exists()
            else None,
        },
        human_summary=_format_day_summary(date_str, status),
        artifacts={key: str(path) for key, path in paths.items()},
        next_actions=[]
        if status.get("has_briefing")
        else [f"如需补当天产物，请运行 openmy skill day.run --date {date_str} --json。"],
    )
    return (payload, 0)


def handle_context_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    cli = _cli()
    from openmy.services.context.active_context import ActiveContext
    from openmy.services.context.consolidation import consolidate
    from openmy.services.context.renderer import render_compact_md

    ctx_path = cli.DATA_ROOT / "active_context.json"
    compact_path = cli.DATA_ROOT / "active_context.compact.md"
    existing = ActiveContext.load(ctx_path) if ctx_path.exists() else None
    ctx = consolidate(cli.DATA_ROOT, existing_context=existing)
    ctx.save(ctx_path)

    data = {
        "level": args.level,
        "snapshot": asdict(ctx),
    }
    artifacts = {"active_context": str(ctx_path)}
    if getattr(args, "compact", False):
        compact_markdown = render_compact_md(ctx)
        compact_path.write_text(compact_markdown, encoding="utf-8")
        data["compact_markdown"] = compact_markdown
        artifacts["compact_markdown"] = str(compact_path)

    payload = build_success_payload(
        action="context.get",
        data=data,
        human_summary=ctx.status_line or "活动上下文已更新。",
        artifacts=artifacts,
        next_actions=[],
    )
    return (payload, 0)


def _validate_day_run_inputs(args: argparse.Namespace) -> None:
    cli = _cli()
    from openmy.services.ingest.audio_pipeline import load_sidecar_transcript

    date_str = _require_date("day.run", getattr(args, "date", None))
    paths = cli.resolve_day_paths(date_str)
    has_reusable_data = paths["raw"].exists() or paths["transcript"].exists() or paths["scenes"].exists()

    if args.skip_transcribe and not has_reusable_data:
        raise SkillDispatchError(
            action="day.run",
            error_code="missing_reusable_data",
            message="要求跳过转写，但当天没有任何可复用数据。",
            hint="请去掉 --skip-transcribe，或先确认该日期已有 transcript/scenes 数据。",
        )

    if not args.audio and not args.skip_transcribe and not (paths["raw"].exists() or paths["transcript"].exists()):
        raise SkillDispatchError(
            action="day.run",
            error_code="missing_audio",
            message="没有输入音频，也没有现成 transcript 数据。",
            hint="请提供 --audio，或先确认该日期已有数据。",
        )

    if args.audio and not args.skip_transcribe:
        audio_files = [Path(str(item)).expanduser() for item in args.audio]
        missing_sidecar_audio = [str(path) for path in audio_files if not load_sidecar_transcript(path)]
        if missing_sidecar_audio and not cli.get_stt_api_key():
            raise SkillDispatchError(
                action="day.run",
                error_code="missing_stt_key",
                message=cli.missing_stt_key_message(),
                hint=cli.missing_stt_key_hint(),
                data={
                    "date": date_str,
                    "audio_files": [str(path) for path in audio_files],
                    "missing_sidecar_audio": missing_sidecar_audio,
                    "env_path": str(cli.PROJECT_ENV_PATH),
                },
            )


def _collect_run_artifacts(run_status: dict[str, Any], status_path: Path) -> dict[str, Any]:
    artifacts: dict[str, Any] = {"run_status": str(status_path)}
    for step in run_status.get("steps", {}).values():
        for artifact in step.get("artifacts", []):
            if artifact not in artifacts.values():
                artifacts[f"artifact_{len(artifacts)}"] = artifact
    return artifacts


def handle_day_run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    date_str = _require_date("day.run", getattr(args, "date", None))
    _validate_day_run_inputs(args)

    exit_code = _run_existing_command("day.run", args)
    status_path = _day_run_status_path(date_str)
    run_status = _read_json(status_path, {}) if status_path.exists() else {}
    final_status = str(run_status.get("status", "") or "").strip()

    if exit_code not in (0, 2):
        message = str(run_status.get("steps", {}).get(run_status.get("current_step", ""), {}).get("message", "")).strip()
        error_payload = build_error_payload(
            action="day.run",
            error_code="run_failed",
            message=message or f"{date_str} 的处理失败了。",
            hint="先看 run_status 里的失败步骤，再决定是否重跑。",
            data={
                "date": date_str,
                "exit_code": exit_code,
                "run_status": run_status,
            },
        )
        return (error_payload, exit_code)

    summary = f"{date_str} 处理完成。"
    if final_status == "partial" or exit_code == 2:
        summary = f"{date_str} 已部分完成；主链产物已落盘，但有后续步骤失败。"

    payload = build_success_payload(
        action="day.run",
        data={
            "date": date_str,
            "exit_code": exit_code,
            "run_status": run_status,
        },
        human_summary=summary,
        artifacts=_collect_run_artifacts(run_status, status_path),
        next_actions=[] if final_status == "completed" else ["查看 run_status 并决定是否补跑失败步骤。"],
    )
    return (payload, exit_code)


def handle_correction_apply(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    tokens = build_correction_tokens(args)
    if not tokens:
        raise SkillDispatchError(
            action="correction.apply",
            error_code="missing_operation",
            message="缺少纠错动作。",
            hint="请传入 --op 和一个或多个 --arg，或继续使用 --correct-args。",
        )

    exit_code = _run_existing_command("correction.apply", args)
    if exit_code != 0:
        error_payload = build_error_payload(
            action="correction.apply",
            error_code="correction_failed",
            message=f"纠错动作执行失败：{tokens[0]}",
            hint="先确认 active_context 已存在，且参数与当前上下文里的标题一致。",
            data={"op": tokens[0], "args": tokens[1:], "status": args.status},
        )
        return (error_payload, exit_code)

    payload = build_success_payload(
        action="correction.apply",
        data={"op": tokens[0], "args": tokens[1:], "status": args.status},
        human_summary=f"已记录纠错动作：{tokens[0]}。",
        artifacts={"corrections": str(_cli().DATA_ROOT / "corrections.jsonl")},
        next_actions=["如需刷新上下文视图，再运行 openmy skill context.get --json。"],
    )
    return (payload, 0)


ACTION_HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "context.get": handle_context_get,
    "day.get": handle_day_get,
    "day.run": handle_day_run,
    "correction.apply": handle_correction_apply,
    "status.get": handle_status_get,
}


def dispatch_skill_action(action: str, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        payload = build_error_payload(
            action=action,
            error_code="unknown_action",
            message=f"不支持的 skill 动作：{action}",
            hint=f"可用动作：{', '.join(ACTION_HANDLERS.keys())}",
        )
        return (payload, 1)

    try:
        return handler(args)
    except SkillDispatchError as exc:
        return (
            build_error_payload(
                action=exc.action,
                error_code=exc.error_code,
                message=exc.message,
                hint=exc.hint,
                data=exc.data,
            ),
            exc.exit_code,
        )
