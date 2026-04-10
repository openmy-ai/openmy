#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from threading import Lock, Thread
from pathlib import Path
from typing import Callable
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JOB_DIR = ROOT_DIR / "data" / "runtime" / "jobs"


@dataclass
class JobRecord:
    job_id: str
    kind: str
    target_date: str | None
    status: str = "queued"
    current_step: str = "queued"
    log_lines: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    artifacts: list[str] = field(default_factory=list)
    error: str = ""


class JobHandle:
    def __init__(self, runner: "JobRunner", job_id: str):
        self._runner = runner
        self._job_id = job_id

    def step(self, value: str) -> None:
        self._runner._update_job(self._job_id, current_step=value)

    def log(self, message: str) -> None:
        self._runner._append_log(self._job_id, message)

    def add_artifact(self, path: str) -> None:
        self._runner._append_artifact(self._job_id, path)


class JobRunner:
    def __init__(self, job_dir: Path | None = None, worker_daemon: bool = True):
        self._job_dir = Path(job_dir or DEFAULT_JOB_DIR)
        self._job_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._worker_daemon = worker_daemon
        self._load_jobs()

    def _now(self) -> str:
        return datetime.now().astimezone().isoformat()

    def _serialize(self, job: JobRecord) -> dict:
        return asdict(job)

    def _job_path(self, job_id: str) -> Path:
        return self._job_dir / f"{job_id}.json"

    def _persist_job_locked(self, job: JobRecord) -> None:
        target = self._job_path(job.job_id)
        temp_path = target.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(self._serialize(job), ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(target)

    def _coerce_job_record(self, payload: dict) -> JobRecord | None:
        job_id = str(payload.get("job_id", "")).strip()
        kind = str(payload.get("kind", "")).strip()
        if not job_id or not kind:
            return None
        status = str(payload.get("status", "queued")).strip() or "queued"
        current_step = str(payload.get("current_step", status)).strip() or status
        log_lines = payload.get("log_lines", [])
        artifacts = payload.get("artifacts", [])
        error = str(payload.get("error", "") or "")
        finished_at = payload.get("finished_at")
        if status in {"queued", "running"}:
            status = "interrupted"
            current_step = "interrupted"
            finished_at = finished_at or self._now()
            error = error or "进程重启前任务未完成，已标记为 interrupted"
            if "进程重启前任务未完成" not in log_lines:
                log_lines = [*list(log_lines), "进程重启前任务未完成，已标记为 interrupted"]
        return JobRecord(
            job_id=job_id,
            kind=kind,
            target_date=payload.get("target_date"),
            status=status,
            current_step=current_step,
            log_lines=list(log_lines),
            started_at=payload.get("started_at"),
            finished_at=finished_at,
            artifacts=list(artifacts),
            error=error,
        )

    def _load_jobs(self) -> None:
        for path in sorted(self._job_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            job = self._coerce_job_record(payload)
            if job is None:
                continue
            self._jobs[job.job_id] = job
            self._persist_job_locked(job)

    def _update_job(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in fields.items():
                setattr(job, key, value)
            self._persist_job_locked(job)

    def _append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.log_lines.append(str(message))
            self._persist_job_locked(job)

    def _append_artifact(self, job_id: str, path: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            artifacts = job.artifacts
            if path not in artifacts:
                artifacts.append(path)
                self._persist_job_locked(job)

    def create_job(self, kind: str, target_date: str | None, run_fn: Callable[[JobHandle], None]) -> dict:
        job_id = f"job_{uuid4().hex[:12]}"
        job = JobRecord(job_id=job_id, kind=kind, target_date=target_date)
        with self._lock:
            self._jobs[job_id] = job
            self._persist_job_locked(job)
            queued_snapshot = self._serialize(job)

        worker = Thread(target=self._run_job, args=(job_id, run_fn), daemon=self._worker_daemon)
        worker.start()
        return queued_snapshot

    def _run_job(self, job_id: str, run_fn: Callable[[JobHandle], None]) -> None:
        self._update_job(job_id, status="running", started_at=self._now())
        handle = JobHandle(self, job_id)
        try:
            run_fn(handle)
        except Exception as exc:
            message = str(exc)
            if message:
                self._append_log(job_id, message)
            self._update_job(job_id, status="failed", error=message, finished_at=self._now())
            return

        self._update_job(job_id, status="succeeded", finished_at=self._now())

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._serialize(job) if job else None

    def list_jobs(self, limit: int | None = None) -> list[dict]:
        with self._lock:
            jobs = [self._serialize(job) for job in self._jobs.values()]
        jobs.sort(key=lambda item: item["started_at"] or "", reverse=True)
        if limit is not None:
            return jobs[:limit]
        return jobs
