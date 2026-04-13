from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.pipeline_runner import (
    PIPELINE_HOME_STEPS,
    build_context_job_steps,
    build_pipeline_command,
    get_pipeline_job_payload,
    get_pipeline_jobs_payload,
    run_pipeline_job_command,
)
from app.upload import handle_upload_request

__all__ = [
    "build_pipeline_command",
    "get_pipeline_job_payload",
    "get_pipeline_jobs_payload",
    "handle_create_pipeline_job",
    "handle_job_action",
    "handle_upload_request",
    "run_pipeline_job_command",
]


def _server():
    import app.server as server_module

    return server_module


def _today_date() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def handle_job_action(job_id: str, action: str) -> tuple[dict[str, Any], int]:
    runner = _server().JOB_RUNNER
    payload = runner.get_job(job_id)
    if not payload:
        return {"error": "job not found", "job_id": job_id}, 404

    success = False
    if action == "pause":
        success = runner.pause_job(job_id)
    elif action == "resume":
        success = runner.resume_job(job_id)
    elif action == "cancel":
        success = runner.cancel_job(job_id)
    elif action == "skip":
        success = runner.skip_job_step(job_id)
    else:
        return {"error": "unsupported action", "action": action}, 400
    if not success:
        return {
            "error": "invalid job action for current state",
            "job_id": job_id,
            "action": action,
            "status": payload.get("status"),
        }, 409
    return runner.get_job(job_id) or {}, 200


def handle_create_pipeline_job(data: dict[str, Any]) -> dict:
    payload = data or {}
    raw_audio_files = payload.get("audio_files") or []
    audio_files = [str(item).strip() for item in raw_audio_files if str(item).strip()]
    kind = str(payload.get("kind", "") or "").strip() or ("run" if audio_files else "context")
    target_date = str(payload.get("target_date", "") or "").strip() or None
    source_file = str(payload.get("source_file", "") or "").strip()
    source_size_bytes = int(payload.get("source_size_bytes", 0) or 0)
    if audio_files and not target_date:
        target_date = _today_date()
    if audio_files and not source_file:
        source_file = Path(audio_files[0]).name
        if not source_size_bytes:
            try:
                source_size_bytes = Path(audio_files[0]).stat().st_size
            except OSError:
                source_size_bytes = 0

    def run_fn(handle):
        return _server().run_pipeline_job_command(kind, target_date, handle)

    initial_steps = PIPELINE_HOME_STEPS if kind == "run" else build_context_job_steps()
    return _server().JOB_RUNNER.create_job(
        kind=kind,
        target_date=target_date,
        run_fn=run_fn,
        steps=initial_steps,
        source_file=source_file,
        source_size_bytes=source_size_bytes,
        can_skip=kind == "run",
        audio_files=audio_files,
    )
