from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from openmy.skill_handlers.common import SkillDispatchError


def handle_status_get(args: argparse.Namespace, *, cli_getter, build_success_payload):
    del args
    cli = cli_getter()
    items = []
    for date_str in cli.find_all_dates():
        item = dict(cli.get_date_status(date_str))
        item["date"] = date_str
        items.append(item)

    latest_date = items[0]["date"] if items else ""
    human_summary = "No OpenMy data found." if not items else f"{len(items)} days of data available; latest: {latest_date}."
    payload = build_success_payload(
        action="status.get",
        data={"items": items, "total_days": len(items), "latest_date": latest_date},
        human_summary=human_summary,
        artifacts={"data_root": str(cli.DATA_ROOT)},
        next_actions=[] if items else ["Process one day of audio first, then check status again."],
    )
    return (payload, 0)


def handle_context_get(args: argparse.Namespace, *, cli_getter, build_success_payload):
    from openmy.services.context.active_context import ActiveContext
    from openmy.services.context.consolidation import consolidate
    from openmy.services.context.renderer import render_compact_md

    cli = cli_getter()
    ctx_path = cli.DATA_ROOT / "active_context.json"
    compact_path = cli.DATA_ROOT / "active_context.compact.md"
    existing = ActiveContext.load(ctx_path) if ctx_path.exists() else None
    ctx = consolidate(cli.DATA_ROOT, existing_context=existing)
    ctx.save(ctx_path)

    data = {"level": args.level, "snapshot": asdict(ctx)}
    artifacts = {"active_context": str(ctx_path)}
    if getattr(args, "compact", False):
        compact_markdown = render_compact_md(ctx, cli.DATA_ROOT)
        compact_path.write_text(compact_markdown, encoding="utf-8")
        data["compact_markdown"] = compact_markdown
        artifacts["compact_markdown"] = str(compact_path)

    payload = build_success_payload(
        action="context.get",
        data=data,
        human_summary=ctx.status_line or "Active context updated.",
        artifacts=artifacts,
        next_actions=[],
    )
    return (payload, 0)


def handle_context_query(args: argparse.Namespace, *, cli_getter, build_success_payload, build_error_payload):
    cli = cli_getter()
    result = cli.query_context(
        cli.DATA_ROOT,
        kind=str(getattr(args, "kind", "") or ""),
        query=str(getattr(args, "query", "") or ""),
        limit=int(getattr(args, "limit", 5) or 5),
        include_evidence=bool(getattr(args, "include_evidence", False)),
    )
    if result.get("error"):
        return (
            build_error_payload(
                action="context.query",
                error_code="query_failed",
                message=str(result.get("error") or "Query failed."),
                data={"result": result},
            ),
            1,
        )

    count = len(result.get("items", []))
    label_map = {
        "project": "project",
        "person": "person",
        "open": "open item",
        "closed": "closed item",
        "evidence": "evidence item",
    }
    kind = str(getattr(args, "kind", "") or "").strip()
    noun = label_map.get(kind, "item")
    summary = f"Found {count} {noun}{'' if count == 1 else 's'}." if count else f"No {noun}s found."

    payload = build_success_payload(
        action="context.query",
        data={"result": result},
        human_summary=summary,
        artifacts={"active_context": str(cli.DATA_ROOT / "active_context.json")},
        next_actions=[],
    )
    return (payload, 0)


def handle_vocab_init(args: argparse.Namespace, *, build_success_payload):
    del args
    from openmy.services.cleaning.cleaner import (
        CORRECTIONS_EXAMPLE_FILE,
        CORRECTIONS_FILE,
        VOCAB_EXAMPLE_FILE,
        VOCAB_FILE,
        resolve_resource_path,
    )

    created: list[str] = []
    before_corrections = CORRECTIONS_FILE.exists()
    before_vocab = VOCAB_FILE.exists()
    corrections_path = resolve_resource_path(CORRECTIONS_FILE, CORRECTIONS_EXAMPLE_FILE, auto_init=True)
    vocab_path = resolve_resource_path(VOCAB_FILE, VOCAB_EXAMPLE_FILE, auto_init=True)

    if corrections_path and not before_corrections and corrections_path == CORRECTIONS_FILE:
        created.append("corrections.json")
    if vocab_path and not before_vocab and vocab_path == VOCAB_FILE:
        created.append("vocab.txt")

    payload = build_success_payload(
        action="vocab.init",
        data={
            "created": created,
            "corrections_exists": bool(corrections_path and corrections_path.exists()),
            "vocab_exists": bool(vocab_path and vocab_path.exists()),
        },
        human_summary=(f"Vocabulary initialized; created {', '.join(created)}." if created else "Vocabulary already initialized."),
        artifacts={"corrections": str(CORRECTIONS_FILE), "vocab": str(VOCAB_FILE)},
        next_actions=["Review the example entries and replace them with your real names, projects, and terms."],
    )
    return (payload, 0)


def handle_profile_get(args: argparse.Namespace, *, cli_getter, build_success_payload):
    del args
    from openmy.services.context.consolidation import load_profile_settings, profile_path

    cli = cli_getter()
    profile = load_profile_settings(cli.DATA_ROOT)
    payload = build_success_payload(
        action="profile.get",
        data={"profile": profile},
        human_summary=f"Profile ready for {profile.get('name', 'user')}.",
        artifacts={"profile": str(profile_path(cli.DATA_ROOT))},
        next_actions=[],
    )
    return (payload, 0)


def handle_profile_set(args: argparse.Namespace, *, cli_getter, build_success_payload, upsert_project_env_fn):
    from openmy.config import DEFAULT_STT_MODELS
    from openmy.services.context.consolidation import profile_path, save_profile_settings

    cli = cli_getter()
    audio_source = str(getattr(args, "audio_source", "") or "").strip()
    stt_provider = str(getattr(args, "stt_provider", "") or "").strip().lower()
    if audio_source:
        audio_source_path = Path(audio_source).expanduser()
        if not audio_source_path.exists() or not audio_source_path.is_dir():
            raise SkillDispatchError(
                action="profile.set",
                error_code="invalid_audio_source_dir",
                message="Audio source directory does not exist.",
                hint="Pass an existing folder path for --audio-source.",
            )
        audio_source = str(audio_source_path)

    if stt_provider and stt_provider not in DEFAULT_STT_MODELS:
        raise SkillDispatchError(
            action="profile.set",
            error_code="invalid_stt_provider",
            message="Unknown STT provider.",
            hint="Pass one of: gemini, faster-whisper, funasr, groq, dashscope, deepgram.",
        )

    updates = {
        "name": str(getattr(args, "name", "") or "").strip(),
        "language": str(getattr(args, "language", "") or "").strip(),
        "timezone": str(getattr(args, "timezone", "") or "").strip(),
        "audio_source_dir": audio_source,
    }
    final_updates = {key: value for key, value in updates.items() if value}
    if not final_updates and not stt_provider:
        raise SkillDispatchError(
            action="profile.set",
            error_code="missing_profile_fields",
            message="No profile fields provided.",
            hint="Pass at least one of --name, --language, --timezone, --audio-source, or --stt-provider.",
        )

    profile = save_profile_settings(cli.DATA_ROOT, final_updates)
    artifacts = {"profile": str(profile_path(cli.DATA_ROOT))}
    env_path = None
    if audio_source:
        env_path = upsert_project_env_fn("OPENMY_AUDIO_SOURCE_DIR", audio_source)
    if stt_provider:
        env_path = upsert_project_env_fn("OPENMY_STT_PROVIDER", stt_provider)
    if env_path:
        artifacts["env"] = str(env_path)
    updated_fields = sorted(final_updates.keys())
    if stt_provider:
        updated_fields.append("stt_provider")
    if stt_provider and final_updates:
        human_summary = f"Profile updated for {profile.get('name', 'user')} and STT provider set to {stt_provider}."
    elif stt_provider:
        human_summary = f"STT provider set to {stt_provider}."
    else:
        human_summary = f"Profile updated for {profile.get('name', 'user')}."
    payload = build_success_payload(
        action="profile.set",
        data={"profile": profile, "updated_fields": updated_fields, "stt_provider": stt_provider},
        human_summary=human_summary,
        artifacts=artifacts,
        next_actions=["Run openmy skill context.get --json if you want a fresh context snapshot."],
    )
    return (payload, 0)
