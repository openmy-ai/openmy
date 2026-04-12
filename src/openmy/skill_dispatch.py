from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from openmy.skill_handlers import context_profile, day_pipeline, health_aggregate
from openmy.skill_handlers.common import (
    SkillDispatchError,
    build_correction_tokens,
    build_error_payload,
    build_success_payload,
    collect_run_artifacts,
    normalize_month_value,
    normalize_week_value,
    require_date,
    upsert_project_env,
    validate_day_run_inputs,
)


def _cli():
    from openmy import cli as cli_module

    return cli_module


def _read_json(path: Path, default: Any) -> Any:
    return _cli().read_json(path, default)


def _day_run_status_path(date_str: str) -> Path:
    return _cli().ensure_day_dir(date_str) / "run_status.json"


def _meta_path(date_str: str) -> Path:
    return _cli().ensure_day_dir(date_str) / f"{date_str}.meta.json"


def _run_existing_command(command: str, args: argparse.Namespace) -> int:
    cli = _cli()

    if command == "day.run":
        final_stt_provider = getattr(args, "stt_provider", None) or cli.get_stt_provider_name()
        return int(
            cli._run_with_silent_console(
                cli.cmd_run,
                argparse.Namespace(
                    date=args.date,
                    audio=args.audio,
                    skip_transcribe=args.skip_transcribe,
                    skip_aggregate=bool(getattr(args, "skip_aggregate", False)),
                    stt_provider=final_stt_provider,
                    stt_model=getattr(args, "stt_model", None),
                    stt_vad=bool(getattr(args, "stt_vad", False)),
                    stt_word_timestamps=bool(getattr(args, "stt_word_timestamps", False)),
                    stt_enrich_mode=getattr(args, "stt_enrich_mode", "recommended"),
                    stt_align=bool(getattr(args, "stt_align", False)),
                    stt_diarize=bool(getattr(args, "stt_diarize", False)),
                ),
            )
        )

    if command == "correction.apply":
        return int(
            cli._run_with_silent_console(
                cli.cmd_correct,
                argparse.Namespace(correct_args=build_correction_tokens(args), status=args.status),
            )
        )

    raise ValueError(f"unsupported bridge command: {command}")


def _require_date(action: str, date_str: str | None) -> str:
    return require_date(_cli().DATE_RE, action, date_str)


def _upsert_project_env(key: str, value: str) -> Path:
    return upsert_project_env(_cli, key, value)


def _validate_day_run_inputs(args: argparse.Namespace) -> None:
    validate_day_run_inputs(args, require_date_fn=_require_date, cli_getter=_cli)


def handle_status_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return context_profile.handle_status_get(args, cli_getter=_cli, build_success_payload=build_success_payload)


def handle_day_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return day_pipeline.handle_day_get(
        args,
        cli_getter=_cli,
        require_date_fn=_require_date,
        read_json=_read_json,
        build_success_payload=build_success_payload,
    )


def handle_distill_pending(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return day_pipeline.handle_distill_pending(
        args,
        cli_getter=_cli,
        require_date_fn=_require_date,
        build_success_payload=build_success_payload,
    )


def handle_distill_submit(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return day_pipeline.handle_distill_submit(
        args,
        cli_getter=_cli,
        require_date_fn=_require_date,
        build_success_payload=build_success_payload,
    )


def handle_extract_core_pending(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return day_pipeline.handle_extract_core_pending(
        args,
        cli_getter=_cli,
        require_date_fn=_require_date,
        read_json=_read_json,
        meta_path_fn=_meta_path,
        build_success_payload=build_success_payload,
    )


def handle_extract_core_submit(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return day_pipeline.handle_extract_core_submit(
        args,
        require_date_fn=_require_date,
        meta_path_fn=_meta_path,
        build_success_payload=build_success_payload,
    )


def handle_aggregate_weekly(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return health_aggregate.handle_aggregate_weekly(
        args,
        cli_getter=_cli,
        normalize_week_value_fn=normalize_week_value,
        build_success_payload=build_success_payload,
    )


def handle_aggregate_monthly(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return health_aggregate.handle_aggregate_monthly(
        args,
        cli_getter=_cli,
        normalize_month_value_fn=normalize_month_value,
        build_success_payload=build_success_payload,
    )


def handle_aggregate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return health_aggregate.handle_aggregate(
        args,
        handle_weekly=handle_aggregate_weekly,
        handle_monthly=handle_aggregate_monthly,
    )


def handle_context_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return context_profile.handle_context_get(args, cli_getter=_cli, build_success_payload=build_success_payload)


def handle_context_query(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return context_profile.handle_context_query(
        args,
        cli_getter=_cli,
        build_success_payload=build_success_payload,
        build_error_payload=build_error_payload,
    )


def handle_vocab_init(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return context_profile.handle_vocab_init(args, build_success_payload=build_success_payload)


def handle_profile_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return context_profile.handle_profile_get(args, cli_getter=_cli, build_success_payload=build_success_payload)


def handle_profile_set(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return context_profile.handle_profile_set(
        args,
        cli_getter=_cli,
        build_success_payload=build_success_payload,
        upsert_project_env_fn=_upsert_project_env,
    )


def handle_day_run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return day_pipeline.handle_day_run(
        args,
        require_date_fn=_require_date,
        validate_inputs=_validate_day_run_inputs,
        run_existing_command=_run_existing_command,
        day_run_status_path_fn=_day_run_status_path,
        read_json=_read_json,
        collect_run_artifacts_fn=collect_run_artifacts,
        build_success_payload=build_success_payload,
        build_error_payload=build_error_payload,
    )


def handle_correction_apply(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return day_pipeline.handle_correction_apply(
        args,
        cli_getter=_cli,
        run_existing_command=_run_existing_command,
        build_success_payload=build_success_payload,
        build_error_payload=build_error_payload,
    )


def handle_health_check(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return health_aggregate.handle_health_check(args, cli_getter=_cli, build_success_payload=build_success_payload)


ACTION_HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "aggregate": handle_aggregate,
    "aggregate.monthly": handle_aggregate_monthly,
    "aggregate.weekly": handle_aggregate_weekly,
    "context.get": handle_context_get,
    "context.query": handle_context_query,
    "distill.pending": handle_distill_pending,
    "distill.submit": handle_distill_submit,
    "extract.core.pending": handle_extract_core_pending,
    "extract.core.submit": handle_extract_core_submit,
    "health.check": handle_health_check,
    "profile.get": handle_profile_get,
    "profile.set": handle_profile_set,
    "day.get": handle_day_get,
    "day.run": handle_day_run,
    "correction.apply": handle_correction_apply,
    "status.get": handle_status_get,
    "vocab.init": handle_vocab_init,
}


def dispatch_skill_action(action: str, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        payload = build_error_payload(
            action=action,
            error_code="unknown_action",
            message=f"Unsupported skill action: {action}",
            hint=f"Available actions: {', '.join(ACTION_HANDLERS.keys())}",
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
