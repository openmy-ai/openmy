from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


UPLOAD_LIMIT_BYTES = 500 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".mp4",
    ".mov",
    ".flac",
    ".ogg",
    ".webm",
}
PIPELINE_HOME_STEPS = [
    {"name": "transcribe", "label": "转写", "status": "pending", "result_summary": "等待开始"},
    {"name": "clean", "label": "清洗", "status": "pending", "result_summary": "等待开始"},
    {"name": "segment", "label": "场景切分", "status": "pending", "result_summary": "等待开始"},
    {"name": "distill", "label": "蒸馏", "status": "pending", "result_summary": "等待开始"},
]
RUN_STATUS_GROUPS = {
    "transcribe": ("transcribe", "transcribe_enrich"),
    "clean": ("clean",),
    "segment": ("segment", "roles"),
    "distill": ("distill", "briefing", "extract_core", "consolidate", "extract_enrich", "aggregate"),
}
RUN_STEP_LABELS = {
    "transcribe": "转写",
    "clean": "清洗",
    "segment": "场景切分",
    "distill": "蒸馏",
}
SKIP_ELIGIBLE_STEPS = {"distill"}


def _server():
    import app.server as server_module

    return server_module


def _today_date() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "upload")
    return cleaned.strip("._") or "upload.bin"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def get_pipeline_jobs_payload() -> list[dict]:
    return _server().JOB_RUNNER.list_jobs()


def get_pipeline_job_payload(job_id: str) -> dict | None:
    return _server().JOB_RUNNER.get_job(job_id)


def build_pipeline_command(kind: str, target_date: str | None = None, audio_files: list[str] | None = None) -> list[str]:
    command = [sys.executable, "-m", "openmy"]
    if kind == "context":
        return [sys.executable, "-m", "openmy", "skill", "context.get", "--compact", "--json"]

    resolved_date = target_date or _today_date()
    command.extend([kind, resolved_date])
    for audio_path in audio_files or []:
        command.extend(["--audio", audio_path])
    return command


def _build_context_job_steps() -> list[dict[str, Any]]:
    return [{"name": "refresh", "label": "刷新上下文", "status": "pending", "result_summary": "等待开始"}]


def _coerce_iso_timestamp(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value).astimezone().isoformat(timespec="seconds")
    except ValueError:
        return raw_value


def _map_group_status(step_payloads: list[dict[str, Any]]) -> str:
    statuses = [str(item.get("status", "") or "pending") for item in step_payloads]
    if any(status == "failed" for status in statuses):
        return "failed"
    if any(status == "running" for status in statuses):
        return "running"
    if any(status == "completed" for status in statuses):
        return "done"
    if statuses and all(status == "skipped" for status in statuses):
        return "skipped"
    return "pending"


def _pick_result_summary(step_payloads: list[dict[str, Any]]) -> str:
    for item in reversed(step_payloads):
        message = str(item.get("message", "") or "").strip()
        if message:
            return message
    return "等待开始"


def _collect_started_at(step_payloads: list[dict[str, Any]]) -> str | None:
    timestamps = [_coerce_iso_timestamp(item.get("updated_at")) for item in step_payloads if item.get("status") != "pending"]
    values = [item for item in timestamps if item]
    return min(values) if values else None


def _collect_finished_at(step_payloads: list[dict[str, Any]]) -> str | None:
    statuses = {str(item.get("status", "") or "pending") for item in step_payloads}
    if "running" in statuses or "pending" in statuses:
        return None
    timestamps = [_coerce_iso_timestamp(item.get("updated_at")) for item in step_payloads]
    values = [item for item in timestamps if item]
    return max(values) if values else None


def _duration_seconds(started_at: str | None, finished_at: str | None) -> int | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return max(0, int((finished - started).total_seconds()))


def _sync_job_from_run_status(job_id: str, date_str: str) -> str | None:
    status_path = _server().DATA_ROOT / date_str / "run_status.json"
    payload = _read_json(status_path)
    if not payload:
        return None

    grouped_steps: list[dict[str, Any]] = []
    current_ui_step = None
    run_steps = payload.get("steps", {}) or {}
    for ui_name, member_names in RUN_STATUS_GROUPS.items():
        member_payloads = [run_steps.get(name, {}) or {} for name in member_names]
        status = _map_group_status(member_payloads)
        started_at = _collect_started_at(member_payloads)
        finished_at = _collect_finished_at(member_payloads)
        grouped_steps.append(
            {
                "name": ui_name,
                "label": RUN_STEP_LABELS[ui_name],
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": _duration_seconds(started_at, finished_at),
                "result_summary": _pick_result_summary(member_payloads),
            }
        )
        if payload.get("current_step") in member_names:
            current_ui_step = ui_name

    final_status = str(payload.get("status", "running") or "running")
    mapped_status = {
        "completed": "succeeded",
        "partial": "partial",
        "failed": "failed",
        "timeout": "partial",
        "running": "running",
    }.get(final_status, "running")
    can_skip = mapped_status == "running" and current_ui_step in SKIP_ELIGIBLE_STEPS
    _server().JOB_RUNNER.update_job(
        job_id,
        steps=grouped_steps,
        current_step=current_ui_step or payload.get("current_step", ""),
        status=mapped_status,
        can_skip=can_skip,
        error="" if mapped_status != "failed" else _pick_result_summary([run_steps.get(str(payload.get('current_step', '') or ''), {}) or {}]),
    )
    return current_ui_step


def _pump_process_output(process: subprocess.Popen[str], handle) -> None:
    if process.stdout is None:
        return
    for raw_line in iter(process.stdout.readline, ""):
        line = raw_line.strip()
        if line:
            handle.log(line)


def _send_signal(process: subprocess.Popen[str], sig: int) -> None:
    try:
        os.kill(process.pid, sig)
    except OSError:
        return


def _mark_single_step(handle, *, name: str, label: str, status: str, result_summary: str) -> None:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    steps = [
        {
            "name": name,
            "label": label,
            "status": status,
            "started_at": now,
            "finished_at": now if status in {"done", "skipped", "failed"} else None,
            "duration_seconds": 0 if status in {"done", "skipped", "failed"} else None,
            "result_summary": result_summary,
        }
    ]
    handle._runner.update_job(handle.job_id, steps=steps, current_step=name)


def _run_context_refresh(handle) -> None:
    handle.set_steps(_build_context_job_steps())
    handle.set_step({"name": "refresh", "label": "刷新上下文", "status": "running", "result_summary": "正在刷新全局上下文"})
    handle.log("开始刷新全局上下文")
    _server().refresh_active_context_snapshot()
    _mark_single_step(handle, name="refresh", label="刷新上下文", status="done", result_summary="全局上下文已更新")
    handle.log("全局上下文刷新完成")


def run_pipeline_job_command(kind: str, target_date: str | None, handle) -> None:
    if kind == "context":
        _run_context_refresh(handle)
        return

    job_payload = handle._runner.get_job(handle.job_id) or {}
    audio_files = list(job_payload.get("audio_files") or [])
    source_file = str(job_payload.get("source_file", "") or "")
    date_str = target_date or _today_date()
    command = build_pipeline_command(kind, date_str, audio_files)
    status_path = _server().DATA_ROOT / date_str / "run_status.json"
    control = {"skip_requested": False, "cancel_requested": False, "paused": False}

    handle.set_steps(PIPELINE_HOME_STEPS)
    handle.log(f"开始处理 {source_file or date_str}")
    process = subprocess.Popen(
        command,
        cwd=str(_server().ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    handle.register_controller(
        pause_fn=(lambda: control.update(paused=True) or _send_signal(process, signal.SIGSTOP)) if hasattr(signal, "SIGSTOP") else None,
        resume_fn=(lambda: control.update(paused=False) or _send_signal(process, signal.SIGCONT)) if hasattr(signal, "SIGCONT") else None,
        cancel_fn=lambda: control.update(cancel_requested=True) or process.terminate(),
        skip_fn=lambda: control.update(skip_requested=True),
    )
    handle._runner.update_job(handle.job_id, can_skip=False)

    output_thread = threading.Thread(target=_pump_process_output, args=(process, handle), daemon=True)
    output_thread.start()

    current_ui_step = None
    while process.poll() is None:
        if not control["paused"]:
            current_ui_step = _sync_job_from_run_status(handle.job_id, date_str) or current_ui_step
            if current_ui_step in SKIP_ELIGIBLE_STEPS:
                handle._runner.update_job(handle.job_id, can_skip=True)
            elif current_ui_step:
                handle._runner.update_job(handle.job_id, can_skip=False)

        if control["cancel_requested"]:
            handle.log("任务已取消")
            handle._runner.update_job(handle.job_id, status="cancelled", finished_at=datetime.now().astimezone().isoformat(timespec="seconds"), can_skip=False)
            return

        if control["skip_requested"] and current_ui_step in SKIP_ELIGIBLE_STEPS:
            handle.log("已跳过当前蒸馏步骤，保留已完成结果")
            process.terminate()
            payload = handle._runner.get_job(handle.job_id) or {}
            steps = payload.get("steps") or []
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            for step in steps:
                if step.get("name") == current_ui_step:
                    step["status"] = "skipped"
                    step["finished_at"] = now
                    step["duration_seconds"] = step.get("duration_seconds") or 0
                    step["result_summary"] = "已手动跳过当前步骤"
            handle._runner.update_job(
                handle.job_id,
                steps=steps,
                status="partial",
                finished_at=now,
                can_skip=False,
            )
            return
        time.sleep(0.5)

    output_thread.join(timeout=0.2)
    current_ui_step = _sync_job_from_run_status(handle.job_id, date_str) or current_ui_step
    return_code = process.wait()
    final_status_payload = _read_json(status_path)
    final_status = str(final_status_payload.get("status", "") or "")
    if final_status == "partial":
        handle._runner.update_job(handle.job_id, status="partial", finished_at=datetime.now().astimezone().isoformat(timespec="seconds"), can_skip=False)
        return
    if return_code == 0:
        handle._runner.update_job(handle.job_id, status="succeeded", finished_at=datetime.now().astimezone().isoformat(timespec="seconds"), can_skip=False)
        return

    failed_message = "处理失败"
    if current_ui_step and final_status_payload:
        failed_message = _pick_result_summary([final_status_payload.get("steps", {}).get(final_status_payload.get("current_step", ""), {}) or {}]) or failed_message
    raise RuntimeError(failed_message)


def handle_upload_request(handler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0") or 0)
    if content_length <= 0:
        return {"error": "missing upload body"}
    if content_length > UPLOAD_LIMIT_BYTES:
        return {"error": "file too large", "limit_bytes": UPLOAD_LIMIT_BYTES}

    content_type = handler.headers.get("Content-Type", "")
    boundary_match = re.search(r"boundary=(.+)", content_type)
    if not boundary_match:
        return {"error": "missing multipart boundary"}

    boundary = boundary_match.group(1).strip().strip('"').encode("utf-8")
    opening_boundary = b"--" + boundary
    first_line = handler.rfile.readline()
    if not first_line:
        return {"error": "empty upload body"}
    if first_line.strip() != opening_boundary:
        return {"error": "invalid multipart payload"}

    header_lines: list[bytes] = []
    consumed = len(first_line)
    while True:
        line = handler.rfile.readline()
        consumed += len(line)
        if line in {b"", b"\r\n", b"\n"}:
            break
        header_lines.append(line.rstrip(b"\r\n"))
    header_blob = b"\n".join(header_lines)
    filename_match = re.search(rb'filename=\"([^\"]+)\"', header_blob)
    filename = Path(filename_match.group(1).decode("utf-8", errors="ignore")).name if filename_match else ""
    if not filename:
        return {"error": "missing filename"}
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return {"error": "unsupported file type", "allowed_suffixes": sorted(ALLOWED_UPLOAD_SUFFIXES)}

    inbox_dir = _server().DATA_ROOT / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    saved_name = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{_safe_filename(filename)}"
    saved_path = inbox_dir / saved_name

    with saved_path.open("wb") as target:
        end_marker = b"\r\n--" + boundary
        buffer = b""
        remaining = max(0, content_length - consumed)
        while remaining > 0:
            chunk = handler.rfile.read(min(64 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            buffer += chunk
            boundary_index = buffer.find(end_marker)
            if boundary_index != -1:
                target.write(buffer[:boundary_index])
                break
            keep_bytes = max(0, len(buffer) - len(end_marker))
            if keep_bytes:
                target.write(buffer[:keep_bytes])
                buffer = buffer[keep_bytes:]
    size_bytes = saved_path.stat().st_size
    if size_bytes > UPLOAD_LIMIT_BYTES:
        saved_path.unlink(missing_ok=True)
        return {"error": "file too large", "limit_bytes": UPLOAD_LIMIT_BYTES}

    return {
        "file_path": str(saved_path),
        "filename": filename,
        "size_bytes": size_bytes,
    }


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

    initial_steps = PIPELINE_HOME_STEPS if kind == "run" else _build_context_job_steps()
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
