from __future__ import annotations

import argparse
import json
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


def _meta_path(date_str: str) -> Path:
    return _cli().ensure_day_dir(date_str) / f"{date_str}.meta.json"


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
    if op in {"typo", "scene-role"}:
        date_str = str(getattr(args, "date", "") or "").strip()
        return [op, date_str, *extra_args] if date_str else [op, *extra_args]
    return [op, *extra_args]


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
            message="Missing date argument.",
            hint="Pass --date YYYY-MM-DD.",
        )
    if not _cli().DATE_RE.match(final_date):
        raise SkillDispatchError(
            action=action,
            error_code="invalid_date",
            message="Invalid date argument.",
            hint="Pass --date YYYY-MM-DD.",
        )
    return final_date


def _format_day_summary(date_str: str, status: dict[str, Any]) -> str:
    if status.get("has_briefing"):
        return f"Briefing ready for {date_str}; {status.get('scene_count', 0)} scenes available."
    if status.get("has_scenes"):
        return f"Scenes ready for {date_str}; {status.get('scene_count', 0)} scenes available."
    if status.get("has_transcript"):
        return f"Transcript ready for {date_str}; briefing not generated yet."
    return f"No usable data found for {date_str}."


def _load_json_payload_arg(action: str, args: argparse.Namespace) -> dict[str, Any]:
    payload_json = str(getattr(args, "payload_json", "") or "").strip()
    payload_file = str(getattr(args, "payload_file", "") or "").strip()

    if payload_json and payload_file:
        raise SkillDispatchError(
            action=action,
            error_code="conflicting_payload_input",
            message="Provide either --payload-json or --payload-file, not both.",
            hint="Keep one payload source.",
        )

    if payload_json:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            raise SkillDispatchError(
                action=action,
                error_code="invalid_payload_json",
                message=f"Payload JSON is invalid: {exc.msg}",
                hint="Pass a valid JSON object string.",
            ) from exc
    elif payload_file:
        payload_path = Path(payload_file).expanduser()
        if not payload_path.exists():
            raise SkillDispatchError(
                action=action,
                error_code="missing_payload_file",
                message=f"Payload file not found: {payload_path}",
                hint="Pass an existing JSON file path.",
            )
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SkillDispatchError(
                action=action,
                error_code="invalid_payload_file",
                message=f"Payload file JSON is invalid: {exc.msg}",
                hint="Make sure the file contains one valid JSON object.",
            ) from exc
    else:
        raise SkillDispatchError(
            action=action,
            error_code="missing_payload",
            message="Missing payload input.",
            hint="Pass --payload-json or --payload-file.",
        )

    if not isinstance(payload, dict):
        raise SkillDispatchError(
            action=action,
            error_code="invalid_payload_type",
            message="Payload must be a JSON object.",
            hint="Wrap the submitted fields in one JSON object.",
        )
    return payload


def _meta_has_core_content(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(payload.get("daily_summary", "") or "").strip():
        return True
    if any(isinstance(item, dict) for item in payload.get("intents", [])):
        return True
    if any(isinstance(item, dict) for item in payload.get("facts", [])):
        return True
    return False


def _load_scene_payload(action: str, date_str: str) -> tuple[Path, dict[str, Any]]:
    scenes_path = _cli().resolve_day_paths(date_str)["scenes"]
    if not scenes_path.exists():
        raise SkillDispatchError(
            action=action,
            error_code="missing_scenes",
            message=f"Scenes file not found for {date_str}.",
            hint=f"Run openmy skill day.run --date {date_str} --audio path/to/audio.wav --json first.",
        )
    payload = _read_json(scenes_path, {})
    scenes = payload.get("scenes", [])
    if not isinstance(scenes, list):
        raise SkillDispatchError(
            action=action,
            error_code="invalid_scenes",
            message=f"Scenes payload is invalid for {date_str}.",
            hint="Re-run the day pipeline to rebuild scenes.json.",
        )
    return scenes_path, payload


def _load_transcript_text(date_str: str) -> tuple[Path, str]:
    cli = _cli()
    transcript_path = cli.resolve_day_paths(date_str)["transcript"]
    if not transcript_path.exists():
        raise SkillDispatchError(
            action="extract.core.pending",
            error_code="missing_transcript",
            message=f"Transcript file not found for {date_str}.",
            hint=f"Run openmy skill day.run --date {date_str} --audio path/to/audio.wav --json first.",
        )
    text = transcript_path.read_text(encoding="utf-8")
    text = cli.strip_document_header(text).strip()
    if not text:
        raise SkillDispatchError(
            action="extract.core.pending",
            error_code="empty_transcript",
            message=f"Transcript is empty for {date_str}.",
            hint="Re-run transcription before extraction.",
        )
    return transcript_path, text


def _scene_catalog_for_agent(scene_payload: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for raw in scene_payload.get("scenes", []):
        if not isinstance(raw, dict):
            continue
        role = raw.get("role", {}) if isinstance(raw.get("role"), dict) else {}
        screen_context = raw.get("screen_context", {}) if isinstance(raw.get("screen_context"), dict) else {}
        items.append(
            {
                "scene_id": str(raw.get("scene_id", "") or "").strip(),
                "time_start": str(raw.get("time_start", "") or "").strip(),
                "summary": str(raw.get("summary", "") or "").strip(),
                "preview": str(raw.get("preview", "") or "").strip(),
                "role": str(role.get("addressed_to", "") or role.get("scene_type_label", "") or "").strip(),
                "screen_context": str(screen_context.get("summary", "") or "").strip(),
            }
        )
    return items


def handle_status_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    cli = _cli()
    items = []
    for date_str in cli.find_all_dates():
        item = dict(cli.get_date_status(date_str))
        item["date"] = date_str
        items.append(item)

    latest_date = items[0]["date"] if items else ""
    human_summary = (
        "No OpenMy data found."
        if not items
        else f"{len(items)} days of data available; latest: {latest_date}."
    )
    payload = build_success_payload(
        action="status.get",
        data={
            "items": items,
            "total_days": len(items),
            "latest_date": latest_date,
        },
        human_summary=human_summary,
        artifacts={"data_root": str(cli.DATA_ROOT)},
        next_actions=[] if items else ["Process one day of audio first, then check status again."],
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
        else [f"To generate missing outputs, run: openmy skill day.run --date {date_str} --json"],
    )
    return (payload, 0)


def handle_distill_pending(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    date_str = _require_date("distill.pending", getattr(args, "date", None))
    scenes_path, scene_payload = _load_scene_payload("distill.pending", date_str)

    pending_scenes: list[dict[str, str]] = []
    for raw in scene_payload.get("scenes", []):
        if not isinstance(raw, dict):
            continue
        if str(raw.get("summary", "") or "").strip():
            continue
        role = raw.get("role", {}) if isinstance(raw.get("role"), dict) else {}
        screen_context = raw.get("screen_context", {}) if isinstance(raw.get("screen_context"), dict) else {}
        pending_scenes.append(
            {
                "scene_id": str(raw.get("scene_id", "") or "").strip(),
                "text": str(raw.get("text", "") or "").strip(),
                "role": str(role.get("addressed_to", "") or role.get("scene_type_label", "") or "").strip(),
                "screen_context": str(screen_context.get("summary", "") or "").strip(),
            }
        )

    status = "pending" if pending_scenes else "already_done"
    next_actions = []
    if pending_scenes:
        next_actions.append(
            f"Submit summaries with: openmy skill distill.submit --date {date_str} --payload-file path/to/payload.json --json"
        )
    else:
        next_actions.append(f"Continue with: openmy skill extract.core.pending --date {date_str} --json")

    payload = build_success_payload(
        action="distill.pending",
        data={
            "date": date_str,
            "status": status,
            "pending_scenes": pending_scenes,
            "guidelines": "1-3句话，30-80字，用'我'做主语，只写干货",
        },
        human_summary=(
            f"{len(pending_scenes)} scenes need distillation for {date_str}."
            if pending_scenes
            else f"All scene summaries already exist for {date_str}."
        ),
        artifacts={"scenes": str(scenes_path)},
        next_actions=next_actions,
    )
    return (payload, 0)


def handle_distill_submit(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from openmy.utils.io import safe_write_json

    submit_payload = _load_json_payload_arg("distill.submit", args)
    date_str = _require_date("distill.submit", submit_payload.get("date") or getattr(args, "date", None))
    summaries = submit_payload.get("summaries", [])
    if not isinstance(summaries, list) or not summaries:
        raise SkillDispatchError(
            action="distill.submit",
            error_code="missing_summaries",
            message="Missing summaries array.",
            hint="Provide {\"date\": \"YYYY-MM-DD\", \"summaries\": [{\"scene_id\": \"...\", \"summary\": \"...\"}]}",
        )

    scenes_path, scene_payload = _load_scene_payload("distill.submit", date_str)
    scene_index = {}
    for index, raw in enumerate(scene_payload.get("scenes", [])):
        if not isinstance(raw, dict):
            continue
        scene_id = str(raw.get("scene_id", "") or "").strip()
        if scene_id:
            scene_index[scene_id] = index

    updated_ids: list[str] = []
    seen_ids: set[str] = set()
    for item in summaries:
        if not isinstance(item, dict):
            raise SkillDispatchError(
                action="distill.submit",
                error_code="invalid_summary_item",
                message="Each summaries item must be an object.",
                hint="Use {\"scene_id\": \"...\", \"summary\": \"...\"}.",
            )
        scene_id = str(item.get("scene_id", "") or "").strip()
        summary = str(item.get("summary", "") or "").strip()
        if not scene_id or not summary:
            raise SkillDispatchError(
                action="distill.submit",
                error_code="invalid_summary_item",
                message="Each summary item needs non-empty scene_id and summary.",
                hint="Fill both fields before submitting.",
            )
        if scene_id in seen_ids:
            raise SkillDispatchError(
                action="distill.submit",
                error_code="duplicate_scene_id",
                message=f"Duplicate scene_id in submission: {scene_id}",
                hint="Keep only one summary per scene_id.",
            )
        seen_ids.add(scene_id)
        if scene_id not in scene_index:
            raise SkillDispatchError(
                action="distill.submit",
                error_code="unknown_scene_id",
                message=f"Unknown scene_id: {scene_id}",
                hint=f"Run openmy skill distill.pending --date {date_str} --json again and use returned scene_id values.",
            )
        scene_payload["scenes"][scene_index[scene_id]]["summary"] = summary
        updated_ids.append(scene_id)

    safe_write_json(scenes_path, scene_payload)
    pending_count = sum(1 for item in scene_payload.get("scenes", []) if not str(item.get("summary", "") or "").strip())
    payload = build_success_payload(
        action="distill.submit",
        data={
            "date": date_str,
            "status": "completed" if pending_count == 0 else "partial",
            "updated_count": len(updated_ids),
            "updated_scene_ids": updated_ids,
            "pending_count": pending_count,
        },
        human_summary=(
            f"Saved {len(updated_ids)} scene summaries for {date_str}."
            if pending_count
            else f"Saved all pending scene summaries for {date_str}."
        ),
        artifacts={"scenes": str(scenes_path)},
        next_actions=(
            [f"Continue with: openmy skill extract.core.pending --date {date_str} --json"]
            if pending_count == 0
            else [f"Run openmy skill distill.pending --date {date_str} --json to review remaining scenes."]
        ),
    )
    return (payload, 0)


def handle_extract_core_pending(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from openmy.services.extraction.extractor import CORE_EXTRACTION_SCHEMA

    date_str = _require_date("extract.core.pending", getattr(args, "date", None))
    transcript_path, transcript_text = _load_transcript_text(date_str)
    meta_path = _meta_path(date_str)
    meta_payload = _read_json(meta_path, {}) if meta_path.exists() else {}
    if _meta_has_core_content(meta_payload):
        status = "already_done"
        next_actions = [f"Run openmy skill day.run --date {date_str} --skip-transcribe --json to finish remaining steps."]
    else:
        status = "pending"
        next_actions = [
            f"Submit extraction with: openmy skill extract.core.submit --date {date_str} --payload-file path/to/payload.json --json"
        ]

    scenes_path, scene_payload = _load_scene_payload("extract.core.pending", date_str)
    payload = build_success_payload(
        action="extract.core.pending",
        data={
            "date": date_str,
            "status": status,
            "reference_date": date_str,
            "transcript_text": transcript_text,
            "output_schema": CORE_EXTRACTION_SCHEMA,
            "scene_catalog": _scene_catalog_for_agent(scene_payload),
        },
        human_summary=(
            f"Core extraction is ready for {date_str}."
            if status == "pending"
            else f"Core extraction already exists for {date_str}."
        ),
        artifacts={
            "transcript": str(transcript_path),
            "scenes": str(scenes_path),
            "meta": str(meta_path),
        },
        next_actions=next_actions,
    )
    return (payload, 0)


def handle_extract_core_submit(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from openmy.services.extraction.extractor import build_legacy_compatible_payload, normalize_extraction_payload
    from openmy.utils.io import safe_write_json

    submit_payload = _load_json_payload_arg("extract.core.submit", args)
    date_str = _require_date("extract.core.submit", submit_payload.get("date") or getattr(args, "date", None))
    raw_payload = submit_payload.get("payload") if isinstance(submit_payload.get("payload"), dict) else submit_payload

    normalized = normalize_extraction_payload(raw_payload, reference_date=date_str)
    if not _meta_has_core_content(normalized):
        raise SkillDispatchError(
            action="extract.core.submit",
            error_code="empty_extraction_payload",
            message="Submitted extraction payload has no usable core content.",
            hint="At minimum, include daily_summary, intents, or facts.",
        )
    normalized["extract_enrich_status"] = "pending"
    normalized["extract_enrich_message"] = ""

    meta_path = _meta_path(date_str)
    safe_write_json(meta_path, build_legacy_compatible_payload(normalized))
    payload = build_success_payload(
        action="extract.core.submit",
        data={
            "date": date_str,
            "status": "completed",
            "extract_enrich_status": "pending",
            "daily_summary": normalized.get("daily_summary", ""),
            "intent_count": len(normalized.get("intents", [])),
            "fact_count": len(normalized.get("facts", [])),
        },
        human_summary=f"Saved core extraction payload for {date_str}.",
        artifacts={"meta": str(meta_path)},
        next_actions=[f"Run openmy skill day.run --date {date_str} --skip-transcribe --json to finish briefing and consolidation."],
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


def handle_context_query(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    cli = _cli()
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


def handle_vocab_init(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
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
        human_summary=(
            f"Vocabulary initialized; created {', '.join(created)}."
            if created
            else "Vocabulary already initialized."
        ),
        artifacts={
            "corrections": str(CORRECTIONS_FILE),
            "vocab": str(VOCAB_FILE),
        },
        next_actions=["Review the example entries and replace them with your real names, projects, and terms."],
    )
    return (payload, 0)


def handle_profile_get(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    del args
    from openmy.services.context.consolidation import load_profile_settings, profile_path

    cli = _cli()
    profile = load_profile_settings(cli.DATA_ROOT)
    payload = build_success_payload(
        action="profile.get",
        data={"profile": profile},
        human_summary=f"Profile ready for {profile.get('name', 'user')}.",
        artifacts={"profile": str(profile_path(cli.DATA_ROOT))},
        next_actions=[],
    )
    return (payload, 0)


def handle_profile_set(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from openmy.services.context.consolidation import profile_path, save_profile_settings

    cli = _cli()
    updates = {
        "name": str(getattr(args, "name", "") or "").strip(),
        "language": str(getattr(args, "language", "") or "").strip(),
        "timezone": str(getattr(args, "timezone", "") or "").strip(),
    }
    final_updates = {key: value for key, value in updates.items() if value}
    if not final_updates:
        raise SkillDispatchError(
            action="profile.set",
            error_code="missing_profile_fields",
            message="No profile fields provided.",
            hint="Pass at least one of --name, --language, or --timezone.",
        )

    profile = save_profile_settings(cli.DATA_ROOT, final_updates)
    payload = build_success_payload(
        action="profile.set",
        data={"profile": profile, "updated_fields": sorted(final_updates.keys())},
        human_summary=f"Profile updated for {profile.get('name', 'user')}.",
        artifacts={"profile": str(profile_path(cli.DATA_ROOT))},
        next_actions=["Run openmy skill context.get --json if you want a fresh context snapshot."],
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
            message="Skip-transcribe requested, but no reusable data found for that date.",
            hint="Remove --skip-transcribe, or make sure transcript/scenes data already exists for that date.",
        )

    if not args.audio and not args.skip_transcribe and not (paths["raw"].exists() or paths["transcript"].exists()):
        raise SkillDispatchError(
            action="day.run",
            error_code="missing_audio",
            message="No audio provided and no existing transcript data found.",
            hint="Pass --audio, or make sure data already exists for that date.",
        )

    if args.audio and not args.skip_transcribe:
        audio_files = [Path(str(item)).expanduser() for item in args.audio]
        missing_sidecar_audio = [str(path) for path in audio_files if not load_sidecar_transcript(path)]
        final_stt_provider = str(getattr(args, "stt_provider", "") or cli.get_stt_provider_name()).strip().lower()
        if (
            missing_sidecar_audio
            and cli.stt_provider_requires_api_key(final_stt_provider)
            and not cli.get_stt_api_key(final_stt_provider)
        ):
            raise SkillDispatchError(
                action="day.run",
                error_code="missing_stt_key",
                message="Missing speech-to-text API key.",
                hint="If you want API transcription, add GEMINI_API_KEY or OPENMY_STT_API_KEY to the current project .env file.",
                data={
                    "date": date_str,
                    "audio_files": [str(path) for path in audio_files],
                    "missing_sidecar_audio": missing_sidecar_audio,
                    "stt_provider": final_stt_provider,
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
            message=message or f"Processing failed for {date_str}.",
            hint="Check the failed step in run_status, then decide whether to re-run it.",
            data={
                "date": date_str,
                "exit_code": exit_code,
                "run_status": run_status,
            },
        )
        return (error_payload, exit_code)

    summary = f"Processing complete for {date_str}."
    if final_status == "partial" or exit_code == 2:
        summary = f"{date_str} partially complete; main artifacts saved but some later steps failed."

    next_actions: list[str] = [] if final_status == "completed" else ["Check run_status and decide whether to re-run failed steps."]
    from openmy.services.cleaning.cleaner import CORRECTIONS_FILE
    if not CORRECTIONS_FILE.exists():
        next_actions.append("Personal vocab not initialized. Run: openmy skill vocab.init --json")

    current_step = str(run_status.get("current_step", "") or "").strip()
    current_step_payload = run_status.get("steps", {}).get(current_step, {}) or {}
    current_message = str(current_step_payload.get("message", "") or "").strip()
    current_skip_reason = str(current_step_payload.get("skip_reason", "") or "").strip()
    missing_llm_handoff = current_skip_reason == "missing_llm_key_agent_handoff"
    if final_status == "partial" and current_step == "distill" and (
        "distill.pending" in current_message or missing_llm_handoff
    ):
        summary = f"{date_str} paused after deterministic steps; an agent now needs to distill scenes."
        next_actions = [f"Run openmy skill distill.pending --date {date_str} --json next."]
    elif final_status == "partial" and current_step == "extract_core" and (
        "extract.core.pending" in current_message or missing_llm_handoff
    ):
        summary = f"{date_str} paused after scene distillation; an agent now needs to submit core extraction."
        next_actions = [f"Run openmy skill extract.core.pending --date {date_str} --json next."]

    payload = build_success_payload(
        action="day.run",
        data={
            "date": date_str,
            "exit_code": exit_code,
            "run_status": run_status,
        },
        human_summary=summary,
        artifacts=_collect_run_artifacts(run_status, status_path),
        next_actions=next_actions,
    )
    return (payload, exit_code)


def handle_correction_apply(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    tokens = build_correction_tokens(args)
    if not tokens:
        raise SkillDispatchError(
            action="correction.apply",
            error_code="missing_operation",
            message="Missing correction operation.",
            hint="Pass --op and one or more --arg values, or keep using --correct-args.",
        )

    if tokens[0] in {"typo", "scene-role"} and not str(getattr(args, "date", "") or "").strip():
        raise SkillDispatchError(
            action="correction.apply",
            error_code="missing_date",
            message=f"Correction operation {tokens[0]} requires a date.",
            hint="Pass --date YYYY-MM-DD.",
            data={"op": tokens[0], "args": tokens[1:]},
        )

    exit_code = _run_existing_command("correction.apply", args)
    if exit_code != 0:
        error_payload = build_error_payload(
            action="correction.apply",
            error_code="correction_failed",
            message=f"Correction operation failed: {tokens[0]}",
            hint="Make sure active_context exists and the arguments match titles in the current context.",
            data={"op": tokens[0], "args": tokens[1:], "status": args.status},
        )
        return (error_payload, exit_code)

    payload = build_success_payload(
        action="correction.apply",
        data={"op": tokens[0], "args": tokens[1:], "status": args.status},
        human_summary=f"Correction recorded: {tokens[0]}.",
        artifacts={"corrections": str(_cli().DATA_ROOT / "corrections.jsonl")},
        next_actions=["To refresh context view, run: openmy skill context.get --json"],
    )
    return (payload, 0)


def handle_health_check(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    del args
    import shutil
    import sys

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
    from openmy.services.screen_recognition.settings import load_screen_context_settings

    cli = _cli()

    # Python
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)

    # ffmpeg / ffprobe
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None

    # STT providers
    current_stt = get_stt_provider_name()
    stt_providers: list[dict[str, Any]] = []
    for name, default_model in DEFAULT_STT_MODELS.items():
        is_local = name in LOCAL_STT_PROVIDERS
        needs_key = stt_provider_requires_api_key(name)
        has_key = bool(get_stt_api_key(name)) if needs_key else True
        stt_providers.append({
            "name": name,
            "type": "local" if is_local else "api",
            "default_model": default_model,
            "needs_api_key": needs_key,
            "api_key_configured": has_key,
            "is_active": name == current_stt,
            "ready": has_key if needs_key else True,
        })

    # LLM
    llm_provider = get_llm_provider_name()
    llm_key_ok = has_llm_credentials()

    # Data state
    profile_exists = profile_path(cli.DATA_ROOT).exists()
    vocab_exists = CORRECTIONS_FILE.exists() and VOCAB_FILE.exists()
    data_days = len(cli.find_all_dates()) if hasattr(cli, "find_all_dates") else 0

    export_provider = get_export_provider_name()
    export_config = get_export_config()
    safe_export_config = {
        key: ("***" if "api_key" in key and value else "")
        for key, value in export_config.items()
    }
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
    if screen_settings.enabled:
        try:
            from openmy.adapters.screen_recognition.client import ScreenRecognitionClient

            screen_service_available = ScreenRecognitionClient(base_url=screen_settings.provider_base_url).is_available()
        except Exception:
            screen_service_available = False

    # Build issues list
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
    if screen_settings.enabled and not screen_service_available:
        issues.append("Screen recognition is enabled, but the local screen service is not reachable.")

    all_ok = len(issues) == 0
    summary_parts = []
    if all_ok:
        summary_parts.append("Environment healthy.")
    else:
        summary_parts.append(f"{len(issues)} issue(s) found.")
    summary_parts.append(f"STT: {current_stt or 'not selected'}; LLM: {llm_provider}; {data_days} days of data.")
    if not llm_key_ok:
        summary_parts.append("An agent can finish distillation and extraction with its own model.")

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
    if screen_settings.enabled and not screen_service_available:
        next_actions.append("Start your local screen recognition service, or set SCREEN_RECOGNITION_ENABLED=false if you do not want it.")

    payload = build_success_payload(
        action="health.check",
        data={
            "python": {"version": py_version, "ok": py_ok},
            "ffmpeg": {"available": ffmpeg_ok, "ffprobe_available": ffprobe_ok},
            "stt_providers": stt_providers,
            "stt_active": current_stt,
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
                "provider_base_url": screen_settings.provider_base_url,
                "service_available": screen_service_available,
            },
            "data_root": str(cli.DATA_ROOT),
            "issues": issues,
            "healthy": all_ok,
        },
        human_summary=" ".join(summary_parts),
        artifacts={"data_root": str(cli.DATA_ROOT)},
        next_actions=next_actions,
    )
    return (payload, 0)


ACTION_HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
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
