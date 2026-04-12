from __future__ import annotations

import argparse

from openmy.skill_handlers.common import (
    SkillDispatchError,
    build_correction_tokens,
    format_day_summary,
    load_json_payload_arg,
    load_scene_payload,
    load_transcript_text,
    meta_has_core_content,
    scene_catalog_for_agent,
)


def handle_day_get(args: argparse.Namespace, *, cli_getter, require_date_fn, read_json, build_success_payload):
    cli = cli_getter()
    date_str = require_date_fn("day.get", getattr(args, "date", None))
    paths = cli.resolve_day_paths(date_str)
    status = cli.get_date_status(date_str)
    payload = build_success_payload(
        action="day.get",
        data={
            "date": date_str,
            "status": status,
            "briefing": read_json(paths["briefing"], None) if paths["briefing"].exists() else None,
            "scenes": read_json(paths["scenes"], None) if paths["scenes"].exists() else None,
            "meta": read_json(paths["dir"] / f"{date_str}.meta.json", None)
            if (paths["dir"] / f"{date_str}.meta.json").exists()
            else None,
        },
        human_summary=format_day_summary(date_str, status),
        artifacts={key: str(path) for key, path in paths.items()},
        next_actions=[]
        if status.get("has_briefing")
        else [f"To generate missing outputs, run: openmy skill day.run --date {date_str} --json"],
    )
    return (payload, 0)


def handle_distill_pending(args: argparse.Namespace, *, cli_getter, require_date_fn, build_success_payload):
    date_str = require_date_fn("distill.pending", getattr(args, "date", None))
    scenes_path, scene_payload = load_scene_payload(
        action="distill.pending",
        date_str=date_str,
        cli_getter=cli_getter,
        read_json=lambda path, default: cli_getter().read_json(path, default),
    )

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


def handle_distill_submit(args: argparse.Namespace, *, cli_getter, require_date_fn, build_success_payload):
    from openmy.utils.io import safe_write_json

    submit_payload = load_json_payload_arg("distill.submit", args)
    date_str = require_date_fn("distill.submit", submit_payload.get("date") or getattr(args, "date", None))
    scenes_path, scene_payload = load_scene_payload(
        action="distill.submit",
        date_str=date_str,
        cli_getter=cli_getter,
        read_json=lambda path, default: cli_getter().read_json(path, default),
    )
    summaries = submit_payload.get("summaries", [])
    if not isinstance(summaries, list) or not summaries:
        raise SkillDispatchError(
            action="distill.submit",
            error_code="missing_summaries",
            message="Missing summaries array.",
            hint='Provide {"date": "YYYY-MM-DD", "summaries": [{"scene_id": "...", "summary": "..."}]}',
        )

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
                hint='Use {"scene_id": "...", "summary": "..."}.',
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


def handle_extract_core_pending(args: argparse.Namespace, *, cli_getter, require_date_fn, read_json, meta_path_fn, build_success_payload):
    from openmy.services.extraction.extractor import CORE_EXTRACTION_SCHEMA

    date_str = require_date_fn("extract.core.pending", getattr(args, "date", None))
    transcript_path, transcript_text = load_transcript_text(date_str=date_str, cli_getter=cli_getter)
    meta_path = meta_path_fn(date_str)
    meta_payload = read_json(meta_path, {}) if meta_path.exists() else {}
    if meta_has_core_content(meta_payload):
        status = "already_done"
        next_actions = [f"Run openmy skill day.run --date {date_str} --skip-transcribe --json to finish remaining steps."]
    else:
        status = "pending"
        next_actions = [
            f"Submit extraction with: openmy skill extract.core.submit --date {date_str} --payload-file path/to/payload.json --json"
        ]

    scenes_path, scene_payload = load_scene_payload(
        action="extract.core.pending",
        date_str=date_str,
        cli_getter=cli_getter,
        read_json=read_json,
    )
    payload = build_success_payload(
        action="extract.core.pending",
        data={
            "date": date_str,
            "status": status,
            "reference_date": date_str,
            "transcript_text": transcript_text,
            "output_schema": CORE_EXTRACTION_SCHEMA,
            "scene_catalog": scene_catalog_for_agent(scene_payload),
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


def handle_extract_core_submit(args: argparse.Namespace, *, require_date_fn, meta_path_fn, build_success_payload):
    from openmy.services.extraction.extractor import build_legacy_compatible_payload, normalize_extraction_payload
    from openmy.utils.io import safe_write_json

    submit_payload = load_json_payload_arg("extract.core.submit", args)
    date_str = require_date_fn("extract.core.submit", submit_payload.get("date") or getattr(args, "date", None))
    raw_payload = submit_payload.get("payload") if isinstance(submit_payload.get("payload"), dict) else submit_payload

    normalized = normalize_extraction_payload(raw_payload, reference_date=date_str)
    if not meta_has_core_content(normalized):
        raise SkillDispatchError(
            action="extract.core.submit",
            error_code="empty_extraction_payload",
            message="Submitted extraction payload has no usable core content.",
            hint="At minimum, include daily_summary, intents, or facts.",
        )
    normalized["extract_enrich_status"] = "pending"
    normalized["extract_enrich_message"] = ""

    meta_path = meta_path_fn(date_str)
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


def handle_day_run(
    args: argparse.Namespace,
    *,
    require_date_fn,
    validate_inputs,
    run_existing_command,
    day_run_status_path_fn,
    read_json,
    collect_run_artifacts_fn,
    build_success_payload,
    build_error_payload,
):
    from openmy.services.cleaning.cleaner import CORRECTIONS_FILE

    date_str = require_date_fn("day.run", getattr(args, "date", None))
    validate_inputs(args)

    exit_code = run_existing_command("day.run", args)
    status_path = day_run_status_path_fn(date_str)
    run_status = read_json(status_path, {}) if status_path.exists() else {}
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
        artifacts=collect_run_artifacts_fn(run_status, status_path),
        next_actions=next_actions,
    )
    return (payload, exit_code)


def handle_correction_apply(args: argparse.Namespace, *, cli_getter, run_existing_command, build_success_payload, build_error_payload):
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

    exit_code = run_existing_command("correction.apply", args)
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
        artifacts={"corrections": str(cli_getter().DATA_ROOT / "corrections.jsonl")},
        next_actions=["To refresh context view, run: openmy skill context.get --json"],
    )
    return (payload, 0)
