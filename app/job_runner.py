from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class JobHandle:
    job_id: str
    _runner: 'JobRunner'

    def log(self, message: str) -> None:
        self._runner.append_log(self.job_id, message)

    def set_step(self, step: str) -> None:
        self._runner.update_job(self.job_id, current_step=step)

    def step(self, step: str) -> None:
        self.set_step(step)


@dataclass
class JobRunner:
    job_dir: Path | None = None
    jobs: dict[str, dict] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def create_job(self, *, kind: str, target_date: str | None = None, run_fn: Callable[[JobHandle], None] | None = None) -> dict:
        job_id = uuid.uuid4().hex[:12]
        payload = {
            'job_id': job_id,
            'kind': kind,
            'target_date': target_date,
            'status': 'queued',
            'current_step': '',
            'artifacts': [],
            'log_lines': [],
            'created_at': time.time(),
        }
        with self._lock:
            self.jobs[job_id] = payload

        snapshot = payload.copy()
        if run_fn is not None:
            thread = threading.Thread(target=self._run_job, args=(job_id, run_fn), daemon=True)
            thread.start()
        return snapshot

    def _run_job(self, job_id: str, run_fn: Callable[[JobHandle], None]) -> None:
        self.update_job(job_id, status='running')
        handle = JobHandle(job_id=job_id, _runner=self)
        try:
            run_fn(handle)
            self.update_job(job_id, status='succeeded')
        except Exception as exc:
            self.append_log(job_id, str(exc))
            self.update_job(job_id, status='failed')

    def update_job(self, job_id: str, **updates) -> None:
        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].update(updates)

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].setdefault('log_lines', []).append(message)

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            payload = self.jobs.get(job_id)
            return payload.copy() if payload else None

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [payload.copy() for payload in sorted(self.jobs.values(), key=lambda item: item.get('created_at', 0), reverse=True)]
