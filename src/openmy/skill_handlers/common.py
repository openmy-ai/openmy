from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from openmy.utils.errors import DEFAULT_DOC_URL, skill_error

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
    doc_url: str = DEFAULT_DOC_URL,
) -> dict[str, Any]:
    payload = {
        "ok": False,
        "action": action,
        "version": SKILL_CONTRACT_VERSION,
        **skill_error(
            code=error_code,
            message=message,
            fix=hint,
            doc_url=doc_url,
        ),
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


def load_json_payload_arg(action: str, args: argparse.Namespace) -> dict[str, Any]:
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


def require_date(date_re, action: str, date_str: str | None) -> str:
    final_date = str(date_str or "").strip()
    if not final_date:
        raise SkillDispatchError(
            action=action,
            error_code="missing_date",
            message="Missing date argument.",
            hint="Pass --date YYYY-MM-DD.",
        )
    if not date_re.match(final_date):
        raise SkillDispatchError(
            action=action,
            error_code="invalid_date",
            message="Invalid date argument.",
            hint="Pass --date YYYY-MM-DD.",
        )
    return final_date


def format_day_summary(date_str: str, status: dict[str, Any]) -> str:
    if status.get("has_briefing"):
        return f"Briefing ready for {date_str}; {status.get('scene_count', 0)} scenes available."
    if status.get("has_scenes"):
        return f"Scenes ready for {date_str}; {status.get('scene_count', 0)} scenes available."
    if status.get("has_transcript"):
        return f"Transcript ready for {date_str}; briefing not generated yet."
    return f"No usable data found for {date_str}."


def meta_has_core_content(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(payload.get("daily_summary", "") or "").strip():
        return True
    if any(isinstance(item, dict) for item in payload.get("intents", [])):
        return True
    if any(isinstance(item, dict) for item in payload.get("facts", [])):
        return True
    return False


def upsert_project_env(cli_getter: Callable[[], Any], key: str, value: str) -> Path:
    cli = cli_getter()
    env_path = cli.PROJECT_ENV_PATH
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    replaced = False
    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        existing_key = stripped.split("=", 1)[0].strip()
        if existing_key != key:
            continue
        lines[index] = f"{key}={value}"
        replaced = True
        break

    if not replaced:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return env_path


def normalize_week_value(raw: str | None) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("Missing ISO week")
    return value


def normalize_month_value(raw: str | None) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("Missing month")
    return value


def load_scene_payload(
    *,
    action: str,
    date_str: str,
    cli_getter: Callable[[], Any],
    read_json: Callable[[Path, Any], Any],
) -> tuple[Path, dict[str, Any]]:
    scenes_path = cli_getter().resolve_day_paths(date_str)["scenes"]
    if not scenes_path.exists():
        raise SkillDispatchError(
            action=action,
            error_code="missing_scenes",
            message=f"Scenes file not found for {date_str}.",
            hint=f"Run openmy skill day.run --date {date_str} --audio path/to/audio.wav --json first.",
        )
    payload = read_json(scenes_path, {})
    scenes = payload.get("scenes", [])
    if not isinstance(scenes, list):
        raise SkillDispatchError(
            action=action,
            error_code="invalid_scenes",
            message=f"Scenes payload is invalid for {date_str}.",
            hint="Re-run the day pipeline to rebuild scenes.json.",
        )
    return scenes_path, payload


def load_transcript_text(*, date_str: str, cli_getter: Callable[[], Any]) -> tuple[Path, str]:
    cli = cli_getter()
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


def scene_catalog_for_agent(scene_payload: dict[str, Any]) -> list[dict[str, str]]:
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


def validate_day_run_inputs(
    args: argparse.Namespace,
    *,
    require_date_fn: Callable[[str, str | None], str],
    cli_getter: Callable[[], Any],
) -> None:
    cli = cli_getter()
    from openmy.services.ingest.audio_pipeline import discover_configured_audio_files, load_sidecar_transcript

    date_str = require_date_fn("day.run", getattr(args, "date", None))
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
        discovered_audio = discover_configured_audio_files(date_str)
        if discovered_audio:
            args.audio = discovered_audio
        else:
            from openmy.config import get_audio_source_dir

            source_dir = str(get_audio_source_dir() or "").strip()
            if source_dir:
                hint = f"No audio found for {date_str} in configured audio source directory: {source_dir}."
            else:
                hint = "Pass --audio, or configure OPENMY_AUDIO_SOURCE_DIR first."
            raise SkillDispatchError(
                action="day.run",
                error_code="missing_audio",
                message="No audio provided and no existing transcript data found.",
                hint=hint,
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


def collect_run_artifacts(run_status: dict[str, Any], status_path: Path) -> dict[str, Any]:
    artifacts: dict[str, Any] = {"run_status": str(status_path)}
    for step in run_status.get("steps", {}).values():
        for artifact in step.get("artifacts", []):
            if artifact not in artifacts.values():
                artifacts[f"artifact_{len(artifacts)}"] = artifact
    return artifacts
