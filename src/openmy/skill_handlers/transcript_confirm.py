"""transcript.confirm.pending / transcript.confirm.submit handlers.

Uncertain-span confirmation loop: after distillation, an agent can pull
up to 5 uncertain [?X] spans from scene texts that affect the daily
briefing, ask the user, then write corrections back to the dictionary,
vocab, and transcript/scenes files.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Callable

from openmy.services.markers import iter_uncertain_spans
from openmy.services.scene_quality import scene_is_usable_for_downstream
from openmy.skill_handlers.common import (
    SkillDispatchError,
    load_json_payload_arg,
    load_scene_payload,
)

MAX_PENDING_ITEMS = 5


def _make_item_id(scene_index: int, line_index: int, span_text: str) -> str:
    """Stable item id: sceneIdx + lineIdx + hash of span text."""
    text_hash = hashlib.sha256(span_text.encode("utf-8")).hexdigest()[:8]
    return f"s{scene_index}_l{line_index}_{text_hash}"


def handle_confirm_pending(
    args: argparse.Namespace,
    *,
    cli_getter: Callable,
    require_date_fn: Callable,
    build_success_payload: Callable,
) -> tuple[dict[str, Any], int]:
    date_str = require_date_fn("transcript.confirm.pending", getattr(args, "date", None))
    scenes_path, scene_payload = load_scene_payload(
        action="transcript.confirm.pending",
        date_str=date_str,
        cli_getter=cli_getter,
        read_json=lambda path, default: cli_getter().read_json(path, default),
    )

    items: list[dict[str, Any]] = []
    scenes = scene_payload.get("scenes", [])
    for scene_index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        # Coarse filter: scene usable AND summary non-empty
        if not scene_is_usable_for_downstream(scene):
            continue
        summary = str(scene.get("summary", "") or "").strip()
        if not summary:
            continue

        text = str(scene.get("text", "") or "")
        time_label = str(scene.get("time_start", "") or "").strip()

        for span in iter_uncertain_spans(text):
            item_id = _make_item_id(scene_index, span.line_index, span.text)
            items.append({
                "item_id": item_id,
                "uncertain_text": span.text,
                "context_line": span.line_text,
                "scene_time": time_label,
                "raw_marker": span.raw,
            })

    # Sort by scene time (items are already in scene-order, stable sort by time_label)
    items.sort(key=lambda x: x["scene_time"])

    # Cap at MAX_PENDING_ITEMS
    items = items[:MAX_PENDING_ITEMS]

    payload = build_success_payload(
        action="transcript.confirm.pending",
        data={
            "date": date_str,
            "status": "pending" if items else "no_items",
            "items": items,
        },
        human_summary=(
            f"{len(items)} uncertain span(s) found for {date_str}."
            if items
            else f"No uncertain spans need confirmation for {date_str}."
        ),
        artifacts={"scenes": str(scenes_path)},
        next_actions=(
            [
                f"Submit confirmations with: openmy skill transcript.confirm.submit --date {date_str} --payload-file path/to/payload.json --json"
            ]
            if items
            else []
        ),
    )
    return (payload, 0)


def handle_confirm_submit(
    args: argparse.Namespace,
    *,
    cli_getter: Callable,
    require_date_fn: Callable,
    build_success_payload: Callable,
) -> tuple[dict[str, Any], int]:
    from openmy.commands.correct import _upsert_word_correction
    from openmy.services.cleaning.cleaner import sync_correction_to_vocab
    from openmy.utils.io import safe_write_json

    submit_payload = load_json_payload_arg("transcript.confirm.submit", args)
    date_str = require_date_fn(
        "transcript.confirm.submit",
        submit_payload.get("date") or getattr(args, "date", None),
    )

    cli = cli_getter()
    paths = cli.resolve_day_paths(date_str)
    transcript_path: Path = paths["transcript"]
    scenes_path, scene_payload = load_scene_payload(
        action="transcript.confirm.submit",
        date_str=date_str,
        cli_getter=cli_getter,
        read_json=lambda path, default: cli.read_json(path, default),
    )

    confirmation_items = submit_payload.get("items", [])
    if not isinstance(confirmation_items, list) or not confirmation_items:
        raise SkillDispatchError(
            action="transcript.confirm.submit",
            error_code="missing_items",
            message="Missing items array.",
            hint='Provide {"date": "YYYY-MM-DD", "items": [{"item_id": "...", "wrong": "...", "right": "...", "resolution": "corrected|confirmed_correct|unknown"}]}',
        )

    valid_resolutions = {"corrected", "confirmed_correct", "unknown"}

    # Load transcript if it exists
    transcript_text = ""
    if transcript_path.exists():
        transcript_text = transcript_path.read_text(encoding="utf-8")

    stats = {"corrected": 0, "confirmed_correct": 0, "unknown": 0}

    for item in confirmation_items:
        if not isinstance(item, dict):
            raise SkillDispatchError(
                action="transcript.confirm.submit",
                error_code="invalid_item",
                message="Each items entry must be an object.",
                hint='Use {"item_id": "...", "wrong": "...", "right": "...", "resolution": "corrected"}.',
            )

        resolution = str(item.get("resolution", "") or "").strip()
        if resolution not in valid_resolutions:
            raise SkillDispatchError(
                action="transcript.confirm.submit",
                error_code="invalid_resolution",
                message=f"Invalid resolution: {resolution}",
                hint=f"Use one of: {', '.join(sorted(valid_resolutions))}.",
            )

        wrong = str(item.get("wrong", "") or "").strip()
        right = str(item.get("right", "") or "").strip()

        if resolution == "corrected":
            if not wrong or not right:
                raise SkillDispatchError(
                    action="transcript.confirm.submit",
                    error_code="missing_correction",
                    message="Corrected items require both wrong and right fields.",
                    hint='Provide {"wrong": "误词", "right": "正确词", "resolution": "corrected"}.',
                )

            # 1. Write corrections.json (upsert by wrong)
            _upsert_word_correction(wrong, right)

            # 2. Append vocab.txt
            sync_correction_to_vocab(wrong, right)

            # 3. Replace in transcript.md: [?wrong] -> right (marker-aware)
            marker_token = f"[?{wrong}]"
            transcript_text = transcript_text.replace(marker_token, right)
            # Also handle unclosed form at end of line
            _unclosed = f"[?{wrong}"
            for _line in transcript_text.split("\n"):
                if _line.rstrip().endswith(_unclosed):
                    transcript_text = transcript_text.replace(_unclosed, right, 1)

            # 4. Update scenes.json scene text the same way
            for scene in scene_payload.get("scenes", []):
                if isinstance(scene, dict) and "text" in scene:
                    scene_text = str(scene["text"])
                    scene_text = scene_text.replace(marker_token, right)
                    # Handle unclosed at end of lines within scene text
                    updated_lines = []
                    for sline in scene_text.split("\n"):
                        if sline.rstrip().endswith(_unclosed):
                            sline = sline.replace(_unclosed, right, 1)
                        updated_lines.append(sline)
                    scene["text"] = "\n".join(updated_lines)

            stats["corrected"] += 1

        elif resolution == "confirmed_correct":
            if not wrong:
                raise SkillDispatchError(
                    action="transcript.confirm.submit",
                    error_code="missing_wrong",
                    message="confirmed_correct items require the wrong field (the word that was uncertain).",
                    hint='Provide {"wrong": "存疑词", "resolution": "confirmed_correct"}.',
                )

            # Only unwrap [?word] -> word in transcript.md + scenes.json
            marker_token = f"[?{wrong}]"
            transcript_text = transcript_text.replace(marker_token, wrong)
            # Handle unclosed form
            _unclosed = f"[?{wrong}"
            for _line in transcript_text.split("\n"):
                if _line.rstrip().endswith(_unclosed):
                    transcript_text = transcript_text.replace(_unclosed, wrong, 1)

            for scene in scene_payload.get("scenes", []):
                if isinstance(scene, dict) and "text" in scene:
                    scene_text = str(scene["text"])
                    scene_text = scene_text.replace(marker_token, wrong)
                    updated_lines = []
                    for sline in scene_text.split("\n"):
                        if sline.rstrip().endswith(_unclosed):
                            sline = sline.replace(_unclosed, wrong, 1)
                        updated_lines.append(sline)
                    scene["text"] = "\n".join(updated_lines)

            stats["confirmed_correct"] += 1

        elif resolution == "unknown":
            # Remove from pending consideration: unwrap [?word] -> word
            # and append a skip marker so it's no longer uncertain.
            # Simplest mechanism: just unwrap the marker (same as confirmed_correct
            # for text treatment). The word stays, the [?] mark is removed,
            # so iter_uncertain_spans won't return it again. No dictionary writes.
            if not wrong:
                raise SkillDispatchError(
                    action="transcript.confirm.submit",
                    error_code="missing_wrong",
                    message="unknown items require the wrong field (the uncertain word).",
                    hint='Provide {"wrong": "存疑词", "resolution": "unknown"}.',
                )

            marker_token = f"[?{wrong}]"
            transcript_text = transcript_text.replace(marker_token, wrong)
            _unclosed = f"[?{wrong}"
            for _line in transcript_text.split("\n"):
                if _line.rstrip().endswith(_unclosed):
                    transcript_text = transcript_text.replace(_unclosed, wrong, 1)

            for scene in scene_payload.get("scenes", []):
                if isinstance(scene, dict) and "text" in scene:
                    scene_text = str(scene["text"])
                    scene_text = scene_text.replace(marker_token, wrong)
                    updated_lines = []
                    for sline in scene_text.split("\n"):
                        if sline.rstrip().endswith(_unclosed):
                            sline = sline.replace(_unclosed, wrong, 1)
                        updated_lines.append(sline)
                    scene["text"] = "\n".join(updated_lines)

            stats["unknown"] += 1

    # Write back transcript.md
    if transcript_path.exists():
        transcript_path.write_text(transcript_text, encoding="utf-8")

    # Write back scenes.json
    safe_write_json(scenes_path, scene_payload)

    total = sum(stats.values())
    payload = build_success_payload(
        action="transcript.confirm.submit",
        data={
            "date": date_str,
            "status": "completed",
            "stats": stats,
            "total_processed": total,
        },
        human_summary=f"Processed {total} confirmation(s) for {date_str}: {stats['corrected']} corrected, {stats['confirmed_correct']} confirmed correct, {stats['unknown']} unknown.",
        artifacts={
            "scenes": str(scenes_path),
            "transcript": str(transcript_path),
        },
        next_actions=[f"Continue with: openmy skill extract.core.pending --date {date_str} --json"],
    )
    return (payload, 0)
