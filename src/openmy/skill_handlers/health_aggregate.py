from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from openmy.skill_handlers.common import SkillDispatchError


def handle_aggregate_weekly(args: argparse.Namespace, *, cli_getter, normalize_week_value_fn, build_success_payload):
    from openmy.services.aggregation import generate_weekly_review

    cli = cli_getter()
    try:
        week_str = normalize_week_value_fn(getattr(args, "week", None)) if getattr(args, "week", None) else None
        review = generate_weekly_review(cli.DATA_ROOT, week_str)
    except ValueError as exc:
        raise SkillDispatchError(
            action="aggregate.weekly",
            error_code="invalid_week",
            message=str(exc),
            hint="Pass --week YYYY-Www, for example 2026-W15.",
        ) from exc

    return (
        build_success_payload(
            action="aggregate.weekly",
            data=review,
            human_summary=f"Weekly review ready for {review['week']}.",
            artifacts={"weekly_review": str(cli.DATA_ROOT / 'weekly' / f"{review['week']}.json")},
            next_actions=[],
        ),
        0,
    )


def handle_aggregate_monthly(args: argparse.Namespace, *, cli_getter, normalize_month_value_fn, build_success_payload):
    from openmy.services.aggregation import generate_monthly_review

    cli = cli_getter()
    try:
        month_str = normalize_month_value_fn(getattr(args, "month", None)) if getattr(args, "month", None) else None
        review = generate_monthly_review(cli.DATA_ROOT, month_str)
    except ValueError as exc:
        raise SkillDispatchError(
            action="aggregate.monthly",
            error_code="invalid_month",
            message=str(exc),
            hint="Pass --month YYYY-MM, for example 2026-04.",
        ) from exc

    return (
        build_success_payload(
            action="aggregate.monthly",
            data=review,
            human_summary=f"Monthly review ready for {review['month']}.",
            artifacts={"monthly_review": str(cli.DATA_ROOT / 'monthly' / f"{review['month']}.json")},
            next_actions=[],
        ),
        0,
    )


def handle_aggregate(args: argparse.Namespace, *, handle_weekly, handle_monthly):
    week = str(getattr(args, "week", "") or "").strip()
    month = str(getattr(args, "month", "") or "").strip()
    if week and month:
        raise SkillDispatchError(
            action="aggregate",
            error_code="conflicting_target",
            message="Pass either --week or --month, not both.",
            hint="Use one target per aggregation call.",
        )
    if month:
        return handle_monthly(args)
    return handle_weekly(args)


def handle_health_check(args: argparse.Namespace, *, cli_getter, build_success_payload):
    del args
    from openmy.config import (
        DEFAULT_STT_MODELS,
        LOCAL_STT_PROVIDERS,
        get_export_config,
        get_export_provider_name,
        get_llm_provider_name,
        get_stt_api_key,
        get_stt_provider_name,
        has_llm_credentials,
        has_stt_credentials,
        stt_provider_requires_api_key,
    )
    from openmy.services.cleaning.cleaner import CORRECTIONS_FILE, VOCAB_FILE
    from openmy.services.context.consolidation import profile_path
    from openmy.services.onboarding.state import build_onboarding_state, save_onboarding_state
    from openmy.services.screen_recognition.settings import load_screen_context_settings

    cli = cli_getter()
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)

    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None

    current_stt = get_stt_provider_name()
    stt_providers: list[dict[str, object]] = []
    for name, default_model in DEFAULT_STT_MODELS.items():
        needs_key = stt_provider_requires_api_key(name)
        has_key = bool(get_stt_api_key(name)) if needs_key else True
        stt_providers.append(
            {
                "name": name,
                "type": "local" if name in LOCAL_STT_PROVIDERS else "api",
                "default_model": default_model,
                "needs_api_key": needs_key,
                "api_key_configured": has_key,
                "is_active": name == current_stt,
                "ready": has_key if needs_key else True,
            }
        )

    llm_provider = get_llm_provider_name()
    llm_key_ok = has_llm_credentials()
    profile_exists = profile_path(cli.DATA_ROOT).exists()
    vocab_exists = CORRECTIONS_FILE.exists() and VOCAB_FILE.exists()
    data_days = len(cli.find_all_dates()) if hasattr(cli, "find_all_dates") else 0

    export_provider = get_export_provider_name()
    export_config = get_export_config()
    safe_export_config = {key: ("***" if "api_key" in key and value else "") for key, value in export_config.items()}
    for key, value in export_config.items():
        if "api_key" not in key:
            safe_export_config[key] = value
    export_configured = any(bool(value) for value in export_config.values())
    export_ready = False
    if not export_provider:
        export_ready = False
    elif export_provider == "obsidian":
        vault_path = str(export_config.get("vault_path", "") or "").strip()
        export_ready = bool(vault_path) and Path(vault_path).expanduser().exists()
    elif export_provider == "notion":
        export_ready = bool(export_config.get("api_key")) and bool(export_config.get("database_id"))

    screen_settings = load_screen_context_settings(data_root=cli.DATA_ROOT)
    screen_service_available = False
    screen_daemon_running = False
    if screen_settings.enabled:
        try:
            from openmy.adapters.screen_recognition.client import ScreenRecognitionClient

            screen_client = ScreenRecognitionClient(data_root=cli.DATA_ROOT)
            screen_service_available = screen_client.is_available()
            screen_daemon_running = screen_client.daemon_running()
        except Exception:
            screen_service_available = False
            screen_daemon_running = False

    issues: list[str] = []
    if not py_ok:
        issues.append(f"Python {py_version} is below minimum 3.10.")
    if not ffmpeg_ok:
        issues.append("ffmpeg not found. Install it: brew install ffmpeg (macOS) or apt install ffmpeg (Linux).")
    if not ffprobe_ok:
        issues.append("ffprobe not found. Usually installed together with ffmpeg.")
    if not current_stt:
        issues.append("No STT provider selected yet. Ask the user to choose one local or cloud engine first.")
    elif not has_stt_credentials():
        issues.append(f"Active STT provider '{current_stt}' needs an API key but none is configured.")
    if not llm_key_ok:
        issues.append("No LLM API key configured. Agent handoff is available for distillation and extraction.")
    if not profile_exists:
        issues.append("User profile not initialized. Run: openmy skill profile.set --name 'Your Name' --json")
    if not vocab_exists:
        issues.append("Vocabulary not initialized. Run: openmy skill vocab.init --json")
    if export_provider and not export_ready:
        issues.append(f"Export provider '{export_provider}' is configured but not ready.")
    if screen_settings.enabled and not screen_daemon_running:
        issues.append("Screen recognition is enabled, but the built-in capture loop is not running.")

    all_ok = len(issues) == 0
    next_actions: list[str] = []
    if not profile_exists:
        next_actions.append("Run: openmy skill profile.set --name 'Your Name' --language en --timezone UTC --json")
    if not vocab_exists:
        next_actions.append("Run: openmy skill vocab.init --json")
    if not llm_key_ok:
        next_actions.append("If you want agent-native processing, run day.run first, then use distill.pending / distill.submit and extract.core.pending / extract.core.submit.")
    if not current_stt:
        next_actions.insert(0, "Ask the user to choose an STT engine first. Local choices are faster-whisper and funasr; cloud choices need an API key.")
    elif not has_stt_credentials() and current_stt not in LOCAL_STT_PROVIDERS:
        next_actions.append(f"Add API key for '{current_stt}' to .env, or switch to a local provider: OPENMY_STT_PROVIDER=faster-whisper")
    if export_provider and not export_ready:
        if export_provider == "obsidian":
            next_actions.append("Set OPENMY_OBSIDIAN_VAULT_PATH to your vault folder, then run health.check again.")
        elif export_provider == "notion":
            next_actions.append("Add NOTION_API_KEY and NOTION_DATABASE_ID, then run health.check again.")
    if screen_settings.enabled and not screen_daemon_running:
        next_actions.append("Run openmy screen on to start the built-in screen capture loop, or set SCREEN_RECOGNITION_ENABLED=false if you do not want it.")

    onboarding = build_onboarding_state(
        data_root=cli.DATA_ROOT,
        stt_providers=stt_providers,
        current_stt=current_stt,
        profile_exists=profile_exists,
        vocab_exists=vocab_exists,
    )
    save_onboarding_state(cli.DATA_ROOT, onboarding)

    summary_parts = [onboarding["headline"]]
    if current_stt:
        summary_parts.append(f"当前在用 {current_stt}。")
    else:
        summary_parts.append("当前还没选转写引擎。")
    summary_parts.append(f"已经有 {data_days} 天数据。")
    if not llm_key_ok:
        summary_parts.append("后面的整理步骤，代理也能先接住。")

    if onboarding.get("primary_action"):
        next_actions.insert(0, onboarding["primary_action"])

    payload = build_success_payload(
        action="health.check",
        data={
            "python": {"version": py_version, "ok": py_ok},
            "ffmpeg": {"available": ffmpeg_ok, "ffprobe_available": ffprobe_ok},
            "stt_providers": stt_providers,
            "stt_active": current_stt,
            "stt_configured": bool(current_stt) and (current_stt in LOCAL_STT_PROVIDERS or has_stt_credentials()),
            "llm_available": llm_key_ok,
            "llm": {"provider": llm_provider, "api_key_configured": llm_key_ok},
            "profile_exists": profile_exists,
            "vocab_exists": vocab_exists,
            "data_days": data_days,
            "export": {
                "provider": export_provider,
                "configured": export_configured,
                "ready": export_ready,
                "config": safe_export_config,
            },
            "screen_recognition": {
                "enabled": bool(screen_settings.enabled),
                "mode": screen_settings.participation_mode,
                "service_available": screen_service_available,
                "daemon_running": screen_daemon_running,
                "capture_interval_seconds": screen_settings.capture_interval_seconds,
                "screenshot_retention_hours": screen_settings.screenshot_retention_hours,
            },
            "onboarding": onboarding,
            "data_root": str(cli.DATA_ROOT),
            "issues": issues,
            "healthy": all_ok,
        },
        human_summary=" ".join(summary_parts),
        artifacts={"data_root": str(cli.DATA_ROOT), "onboarding_state": onboarding["state_path"]},
        next_actions=next_actions,
    )
    return (payload, 0)
