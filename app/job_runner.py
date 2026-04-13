from __future__ import annotations

import copy
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


TERMINAL_JOB_STATUSES = {"succeeded", "failed", "cancelled", "interrupted", "partial"}
STEP_DONE_STATUSES = {"done", "completed", "succeeded"}
STEP_PENDING_STATUSES = {"pending", "queued"}
STEP_RUNNING_STATUSES = {"running"}
STEP_SKIPPED_STATUSES = {"skipped"}
STEP_FAILED_STATUSES = {"failed"}


@dataclass
class JobController:
    pause_fn: Callable[[], None] | None = None
    resume_fn: Callable[[], None] | None = None
    cancel_fn: Callable[[], None] | None = None
    skip_fn: Callable[[], None] | None = None


@dataclass
class JobHandle:
    job_id: str
    _runner: "JobRunner"

    def get_job(self) -> dict[str, Any] | None:
        return self._runner.get_job(self.job_id)

    def update(self, **updates: Any) -> None:
        self._runner.update_job(self.job_id, **updates)

    def log(self, message: str) -> None:
        self._runner.append_log(self.job_id, message)

    def set_step(self, step: str | dict[str, Any], **kwargs) -> None:
        self._runner.set_step(self.job_id, step, **kwargs)

    def step(self, step: str | dict[str, Any], **kwargs) -> None:
        self.set_step(step, **kwargs)

    def set_steps(self, steps: list[dict[str, Any] | str]) -> None:
        self._runner.set_steps(self.job_id, steps)

    def add_artifact(self, artifact_path: str) -> None:
        self._runner.add_artifact(self.job_id, artifact_path)

    def pause(self) -> None:
        self._runner.pause_job(self.job_id)

    def resume(self) -> None:
        self._runner.resume_job(self.job_id)

    def cancel(self) -> None:
        self._runner.cancel_job(self.job_id)

    def skip_step(self) -> None:
        self._runner.skip_job_step(self.job_id)

    def register_controller(self, **kwargs) -> None:
        self._runner.register_controller(self.job_id, JobController(**kwargs))


@dataclass
class JobRunner:
    job_dir: Path | None = None
    jobs: dict[str, dict] = field(default_factory=dict)
    controllers: dict[str, JobController] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if self.job_dir is None:
            return
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self._restore_jobs()

    def create_job(
        self,
        *,
        kind: str,
        target_date: str | None = None,
        run_fn: Callable[[JobHandle], None] | None = None,
        steps: list[dict[str, Any] | str] | None = None,
        source_file: str = "",
        source_size_bytes: int = 0,
        can_skip: bool = False,
        **extra_fields: Any,
    ) -> dict:
        job_id = uuid.uuid4().hex[:12]
        payload = {
            "job_id": job_id,
            "kind": kind,
            "target_date": target_date,
            "status": "queued",
            "current_step": "",
            "artifacts": [],
            "log_lines": [],
            "created_at": self._timestamp(),
            "started_at": None,
            "finished_at": None,
            "error": "",
            "steps": [],
            "progress_pct": 0,
            "eta_seconds": None,
            "source_file": source_file,
            "source_size_bytes": int(source_size_bytes or 0),
            "can_pause": False,
            "can_skip": bool(can_skip),
            "skip_allowed": bool(can_skip),
        }
        if extra_fields:
            payload.update(extra_fields)
        with self._lock:
            self.jobs[job_id] = payload
        if steps:
            self.set_steps(job_id, steps)
        self._persist_job(job_id)

        snapshot = self.get_job(job_id) or {}
        if run_fn is not None:
            thread = threading.Thread(target=self._run_job, args=(job_id, run_fn), daemon=True)
            thread.start()
        return snapshot

    def _run_job(self, job_id: str, run_fn: Callable[[JobHandle], None]) -> None:
        self.update_job(job_id, status="running", started_at=self._timestamp(), finished_at=None, error="")
        handle = JobHandle(job_id=job_id, _runner=self)
        try:
            run_fn(handle)
            current = self.get_job(job_id)
            if current and current.get("status") not in TERMINAL_JOB_STATUSES:
                self.update_job(job_id, status="succeeded", finished_at=self._timestamp(), error="")
        except Exception as exc:
            current = self.get_job(job_id)
            if current and current.get("status") in TERMINAL_JOB_STATUSES:
                return
            self.append_log(job_id, str(exc))
            self.update_job(job_id, status="failed", finished_at=self._timestamp(), error=str(exc))
        finally:
            self.controllers.pop(job_id, None)

    def update_job(self, job_id: str, **updates) -> None:
        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].update(updates)
            if "can_skip" in updates:
                self.jobs[job_id]["skip_allowed"] = bool(updates["can_skip"])
            self._recompute_locked(self.jobs[job_id])
        self._persist_job(job_id)

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].setdefault("log_lines", []).append(message)
            self._recompute_locked(self.jobs[job_id])
        self._persist_job(job_id)

    def add_artifact(self, job_id: str, artifact_path: str) -> None:
        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].setdefault("artifacts", []).append(artifact_path)
            self._recompute_locked(self.jobs[job_id])
        self._persist_job(job_id)

    def set_steps(self, job_id: str, steps: list[dict[str, Any] | str]) -> None:
        with self._lock:
            payload = self.jobs.get(job_id)
            if payload is None:
                return
            existing_by_name = {
                str(item.get("name", "") or ""): item
                for item in payload.get("steps", [])
                if isinstance(item, dict) and item.get("name")
            }
            canonical_steps = []
            for index, raw_step in enumerate(steps, start=1):
                step = self._normalize_step(raw_step, index=index)
                existing = existing_by_name.get(step["name"])
                if existing:
                    step = {
                        **step,
                        "status": existing.get("status", step["status"]),
                        "started_at": existing.get("started_at"),
                        "finished_at": existing.get("finished_at"),
                        "duration_seconds": existing.get("duration_seconds"),
                        "result_summary": existing.get("result_summary", step["result_summary"]),
                    }
                canonical_steps.append(step)
            payload["steps"] = canonical_steps
            self._recompute_locked(payload)
        self._persist_job(job_id)

    def set_step(self, job_id: str, step: str | dict[str, Any], **kwargs) -> None:
        with self._lock:
            payload = self.jobs.get(job_id)
            if payload is None:
                return

            if isinstance(step, dict):
                step_name = str(step.get("name", "") or kwargs.get("name", "")).strip()
                step_label = str(step.get("label", "") or kwargs.get("label", "")).strip()
                result_summary = str(step.get("result_summary", "") or kwargs.get("result_summary", "")).strip()
                status = str(step.get("status", "") or kwargs.get("status", "running")).strip() or "running"
            else:
                step_name = str(step or "").strip()
                step_label = str(kwargs.get("label", "") or "").strip()
                result_summary = str(kwargs.get("result_summary", "") or "").strip()
                status = str(kwargs.get("status", "running") or "running").strip()

            if not payload.get("steps"):
                payload["current_step"] = step_name
                self._recompute_locked(payload)
                self._persist_job(job_id)
                return

            now = self._timestamp()
            found = False
            for item in payload["steps"]:
                if item.get("name") != step_name:
                    if item.get("status") in STEP_RUNNING_STATUSES and status in STEP_RUNNING_STATUSES:
                        item["status"] = "done"
                        item["finished_at"] = item.get("finished_at") or now
                        item["duration_seconds"] = self._duration_seconds(item.get("started_at"), item.get("finished_at"))
                    continue
                found = True
                if step_label:
                    item["label"] = step_label
                if not item.get("started_at"):
                    item["started_at"] = now
                item["status"] = status
                if result_summary:
                    item["result_summary"] = result_summary
                if status in STEP_DONE_STATUSES | STEP_SKIPPED_STATUSES | STEP_FAILED_STATUSES:
                    item["finished_at"] = now
                    item["duration_seconds"] = self._duration_seconds(item.get("started_at"), item["finished_at"])
                else:
                    item["finished_at"] = None
                    item["duration_seconds"] = None
                payload["current_step"] = step_name
            if not found:
                payload["current_step"] = step_name
            self._recompute_locked(payload)
        self._persist_job(job_id)

    def register_controller(self, job_id: str, controller: JobController) -> None:
        self.controllers[job_id] = controller
        with self._lock:
            payload = self.jobs.get(job_id)
            if payload is not None:
                self._recompute_locked(payload)
        self._persist_job(job_id)

    def pause_job(self, job_id: str) -> bool:
        current = self.get_job(job_id)
        if not current or current.get("status") != "running":
            return False
        controller = self.controllers.get(job_id)
        if not controller or not controller.pause_fn:
            return False
        controller.pause_fn()
        self.update_job(job_id, status="paused", can_pause=False)
        return True

    def resume_job(self, job_id: str) -> bool:
        current = self.get_job(job_id)
        if not current or current.get("status") != "paused":
            return False
        controller = self.controllers.get(job_id)
        if not controller or not controller.resume_fn:
            return False
        controller.resume_fn()
        self.update_job(job_id, status="running")
        return True

    def cancel_job(self, job_id: str) -> bool:
        current = self.get_job(job_id)
        if not current or current.get("status") in TERMINAL_JOB_STATUSES:
            return False
        controller = self.controllers.get(job_id)
        if controller and controller.cancel_fn:
            controller.cancel_fn()
        self.update_job(job_id, status="cancelled", finished_at=self._timestamp(), error="")
        return True

    def skip_job_step(self, job_id: str) -> bool:
        current = self.get_job(job_id)
        if not current or current.get("status") != "running" or not current.get("can_skip"):
            return False
        controller = self.controllers.get(job_id)
        if controller and controller.skip_fn:
            controller.skip_fn()
        self.append_log(job_id, "已收到跳过当前步骤的请求")
        return True

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            payload = self.jobs.get(job_id)
            return self._public_payload(payload) if payload else None

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [
                self._public_payload(payload)
                for payload in sorted(
                    self.jobs.values(),
                    key=lambda item: item.get("created_at", ""),
                    reverse=True,
                )
            ]

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().astimezone().isoformat(timespec="microseconds")

    def _job_path(self, job_id: str) -> Path | None:
        if self.job_dir is None:
            return None
        return self.job_dir / f"{job_id}.json"

    def _persist_job(self, job_id: str) -> None:
        job_path = self._job_path(job_id)
        if job_path is None:
            return
        with self._lock:
            payload = self.jobs.get(job_id)
            if payload is None:
                return
            content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        job_path.write_text(content, encoding="utf-8")

    def _restore_jobs(self) -> None:
        assert self.job_dir is not None
        for job_path in sorted(self.job_dir.glob("*.json")):
            try:
                payload = json.loads(job_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            job_id = str(payload.get("job_id", "") or "")
            if not job_id:
                continue
            if payload.get("status") in {"running", "paused"}:
                payload["status"] = "interrupted"
                payload["current_step"] = "interrupted"
                payload["finished_at"] = self._timestamp()
                payload["error"] = "进程重启前任务未完成"
            self._recompute_locked(payload)
            self.jobs[job_id] = payload
            self._persist_job(job_id)

    def _public_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        snapshot = copy.deepcopy(payload)
        self._recompute_locked(snapshot)
        return {key: value for key, value in snapshot.items() if not str(key).startswith("_")}

    def _recompute_locked(self, payload: dict[str, Any]) -> None:
        steps = payload.get("steps") or []
        payload["progress_pct"] = self._compute_progress_pct(steps, payload.get("status", ""))
        payload["eta_seconds"] = self._compute_eta_seconds(payload)
        controller = self.controllers.get(str(payload.get("job_id", "") or ""))
        payload["can_pause"] = payload.get("status") == "running" and bool(controller and controller.pause_fn)
        payload["can_skip"] = bool(payload.get("skip_allowed")) and payload.get("status") == "running"

    @staticmethod
    def _normalize_step(raw_step: dict[str, Any] | str, *, index: int) -> dict[str, Any]:
        if isinstance(raw_step, str):
            name = raw_step
            label = raw_step
            status = "pending"
            result_summary = ""
        else:
            name = str(raw_step.get("name", "") or raw_step.get("label", "") or f"step_{index}")
            label = str(raw_step.get("label", "") or name)
            status = str(raw_step.get("status", "pending") or "pending")
            result_summary = str(raw_step.get("result_summary", "") or "")
        return {
            "name": name,
            "label": label,
            "status": status,
            "started_at": raw_step.get("started_at") if isinstance(raw_step, dict) else None,
            "finished_at": raw_step.get("finished_at") if isinstance(raw_step, dict) else None,
            "duration_seconds": raw_step.get("duration_seconds") if isinstance(raw_step, dict) else None,
            "result_summary": result_summary,
        }

    @staticmethod
    def _duration_seconds(started_at: str | None, finished_at: str | None) -> int | None:
        if not started_at or not finished_at:
            return None
        try:
            started = datetime.fromisoformat(started_at)
            finished = datetime.fromisoformat(finished_at)
        except ValueError:
            return None
        return max(0, int((finished - started).total_seconds()))

    @staticmethod
    def _compute_progress_pct(steps: list[dict[str, Any]], status: str) -> int:
        if not steps:
            return 100 if status in TERMINAL_JOB_STATUSES - {"failed", "cancelled", "interrupted"} else 0
        done = 0.0
        for item in steps:
            step_status = str(item.get("status", "") or "")
            if step_status in STEP_DONE_STATUSES | STEP_SKIPPED_STATUSES:
                done += 1.0
            elif step_status in STEP_RUNNING_STATUSES:
                done += 0.5
        return int(round((done / len(steps)) * 100))

    def _compute_eta_seconds(self, payload: dict[str, Any]) -> int | None:
        status = str(payload.get("status", "") or "")
        if status in TERMINAL_JOB_STATUSES:
            return 0

        steps = payload.get("steps") or []
        running_steps = [item for item in steps if item.get("status") in STEP_RUNNING_STATUSES]
        remaining_steps = [item for item in steps if item.get("status") in STEP_PENDING_STATUSES]
        completed_durations = [
            int(item.get("duration_seconds"))
            for item in steps
            if item.get("duration_seconds") not in (None, "") and item.get("status") in STEP_DONE_STATUSES | STEP_SKIPPED_STATUSES
        ]
        if not running_steps and not remaining_steps:
            return None

        average_duration = int(sum(completed_durations) / len(completed_durations)) if completed_durations else None
        if average_duration is None:
            size_bytes = int(payload.get("source_size_bytes") or 0)
            if size_bytes <= 0:
                return None
            size_mb = max(1, size_bytes // (1024 * 1024))
            average_duration = min(600, max(15, size_mb * 2))

        running_eta = average_duration // 2 if running_steps else 0
        return max(0, running_eta + average_duration * len(remaining_steps))
