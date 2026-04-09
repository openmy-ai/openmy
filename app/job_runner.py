#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from threading import Lock, Thread
from typing import Callable
from uuid import uuid4


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
    def __init__(self):
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def _now(self) -> str:
        return datetime.now().astimezone().isoformat()

    def _serialize(self, job: JobRecord) -> dict:
        return asdict(job)

    def _update_job(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in fields.items():
                setattr(job, key, value)

    def _append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            self._jobs[job_id].log_lines.append(str(message))

    def _append_artifact(self, job_id: str, path: str) -> None:
        with self._lock:
            artifacts = self._jobs[job_id].artifacts
            if path not in artifacts:
                artifacts.append(path)

    def create_job(self, kind: str, target_date: str | None, run_fn: Callable[[JobHandle], None]) -> dict:
        job_id = f"job_{uuid4().hex[:12]}"
        job = JobRecord(job_id=job_id, kind=kind, target_date=target_date)
        with self._lock:
            self._jobs[job_id] = job
            queued_snapshot = self._serialize(job)

        worker = Thread(target=self._run_job, args=(job_id, run_fn), daemon=True)
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
