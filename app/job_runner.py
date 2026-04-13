from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable


@dataclass
class JobHandle:
    job_id: str
    _runner: "JobRunner"

    def log(self, message: str) -> None:
        self._runner.append_log(self.job_id, message)

    def set_step(self, step: str) -> None:
        self._runner.update_job(self.job_id, current_step=step)

    def step(self, step: str) -> None:
        self.set_step(step)

    def add_artifact(self, artifact_path: str) -> None:
        self._runner.add_artifact(self.job_id, artifact_path)


@dataclass
class JobRunner:
    job_dir: Path | None = None
    jobs: dict[str, dict] = field(default_factory=dict)
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
        }
        with self._lock:
            self.jobs[job_id] = payload
        self._persist_job(job_id)

        snapshot = payload.copy()
        if run_fn is not None:
            thread = threading.Thread(target=self._run_job, args=(job_id, run_fn), daemon=True)
            thread.start()
        return snapshot

    def _run_job(self, job_id: str, run_fn: Callable[[JobHandle], None]) -> None:
        self.update_job(job_id, status="running", started_at=self._timestamp(), finished_at=None, error="")
        handle = JobHandle(job_id=job_id, _runner=self)
        try:
            run_fn(handle)
            self.update_job(job_id, status="succeeded", finished_at=self._timestamp(), error="")
        except Exception as exc:
            self.append_log(job_id, str(exc))
            self.update_job(job_id, status="failed", finished_at=self._timestamp(), error=str(exc))

    def update_job(self, job_id: str, **updates) -> None:
        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].update(updates)
        self._persist_job(job_id)

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].setdefault("log_lines", []).append(message)
        self._persist_job(job_id)

    def add_artifact(self, job_id: str, artifact_path: str) -> None:
        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].setdefault("artifacts", []).append(artifact_path)
        self._persist_job(job_id)

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            payload = self.jobs.get(job_id)
            return payload.copy() if payload else None

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [
                payload.copy()
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
            if payload.get("status") == "running":
                payload["status"] = "interrupted"
                payload["current_step"] = "interrupted"
                payload["finished_at"] = self._timestamp()
                payload["error"] = "进程重启前任务未完成"
            self.jobs[job_id] = payload
            self._persist_job(job_id)
