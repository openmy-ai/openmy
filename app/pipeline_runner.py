from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


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


def build_context_job_steps() -> list[dict[str, Any]]:
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


def _sync_job_from_run_status(job_id: str, date_str: str, last_synced_mtime_ns: int | None) -> tuple[str | None, int | None]:
    status_path = _server().DATA_ROOT / date_str / "run_status.json"
    if not status_path.exists():
        return None, last_synced_mtime_ns

    current_mtime_ns = status_path.stat().st_mtime_ns
    if last_synced_mtime_ns == current_mtime_ns:
        payload = _server().JOB_RUNNER.get_job(job_id) or {}
        return payload.get("current_step") or None, last_synced_mtime_ns

    payload = _read_json(status_path)
    if not payload:
        return None, last_synced_mtime_ns

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
    current_step_name = str(payload.get("current_step", "") or "")
    _server().JOB_RUNNER.update_job(
        job_id,
        steps=grouped_steps,
        current_step=current_ui_step or current_step_name,
        status=mapped_status,
        can_skip=can_skip,
        error="" if mapped_status != "failed" else _pick_result_summary([run_steps.get(current_step_name, {}) or {}]),
    )
    return current_ui_step, current_mtime_ns


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
    handle.update(steps=steps, current_step=name)


def _run_context_refresh(handle) -> None:
    handle.set_steps(build_context_job_steps())
    handle.set_step({"name": "refresh", "label": "刷新上下文", "status": "running", "result_summary": "正在刷新全局上下文"})
    handle.log("开始刷新全局上下文")
    _server().refresh_active_context_snapshot()
    _mark_single_step(handle, name="refresh", label="刷新上下文", status="done", result_summary="全局上下文已更新")
    handle.log("全局上下文刷新完成")


def run_pipeline_job_command(kind: str, target_date: str | None, handle) -> None:
    if kind == "context":
        _run_context_refresh(handle)
        return

    job_payload = handle.get_job() or {}
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

    pause_fn = (lambda: control.update(paused=True) or _send_signal(process, signal.SIGSTOP)) if hasattr(signal, "SIGSTOP") else None
    resume_fn = (lambda: control.update(paused=False) or _send_signal(process, signal.SIGCONT)) if hasattr(signal, "SIGCONT") else None
    handle.register_controller(
        pause_fn=pause_fn,
        resume_fn=resume_fn,
        cancel_fn=lambda: control.update(cancel_requested=True) or process.terminate(),
        skip_fn=lambda: control.update(skip_requested=True),
    )
    handle.update(can_skip=False)

    output_thread = threading.Thread(target=_pump_process_output, args=(process, handle), daemon=True)
    output_thread.start()

    current_ui_step = None
    last_synced_mtime_ns = None
    while process.poll() is None:
        if not control["paused"]:
            current_ui_step, last_synced_mtime_ns = _sync_job_from_run_status(handle.job_id, date_str, last_synced_mtime_ns)
            latest_job = handle.get_job() or {}
            current_ui_step = current_ui_step or latest_job.get("current_step")
            if current_ui_step in SKIP_ELIGIBLE_STEPS:
                handle.update(can_skip=True)
            elif current_ui_step:
                handle.update(can_skip=False)

        if control["cancel_requested"]:
            handle.log("任务已取消")
            handle.update(status="cancelled", finished_at=datetime.now().astimezone().isoformat(timespec="seconds"), can_skip=False)
            return

        if control["skip_requested"] and current_ui_step in SKIP_ELIGIBLE_STEPS:
            handle.log("已跳过当前蒸馏步骤，保留已完成结果")
            process.terminate()
            payload = handle.get_job() or {}
            steps = payload.get("steps") or []
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            for step in steps:
                if step.get("name") == current_ui_step:
                    step["status"] = "skipped"
                    step["finished_at"] = now
                    step["duration_seconds"] = step.get("duration_seconds") or 0
                    step["result_summary"] = "已手动跳过当前步骤"
            handle.update(steps=steps, status="partial", finished_at=now, can_skip=False)
            return
        time.sleep(0.5)

    output_thread.join(timeout=0.2)
    current_ui_step, last_synced_mtime_ns = _sync_job_from_run_status(handle.job_id, date_str, last_synced_mtime_ns)
    return_code = process.wait()
    final_status_payload = _read_json(status_path)
    final_status = str(final_status_payload.get("status", "") or "")
    if final_status == "partial":
        handle.update(status="partial", finished_at=datetime.now().astimezone().isoformat(timespec="seconds"), can_skip=False)
        return
    if return_code == 0:
        handle.update(status="succeeded", finished_at=datetime.now().astimezone().isoformat(timespec="seconds"), can_skip=False)
        return

    failed_message = "处理失败"
    if current_ui_step and final_status_payload:
        failed_message = _pick_result_summary([final_status_payload.get("steps", {}).get(final_status_payload.get("current_step", ""), {}) or {}]) or failed_message
    raise RuntimeError(failed_message)
