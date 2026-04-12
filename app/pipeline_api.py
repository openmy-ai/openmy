from __future__ import annotations

from typing import Any


def _server():
    import app.server as server_module
    return server_module


def get_pipeline_jobs_payload() -> list[dict]:
    return _server().JOB_RUNNER.list_jobs()


def get_pipeline_job_payload(job_id: str) -> dict | None:
    return _server().JOB_RUNNER.get_job(job_id)


def build_pipeline_command(kind: str, target_date: str | None = None) -> list[str]:
    return ['openmy', kind, target_date or '']


def run_pipeline_job_command(kind: str, target_date: str | None, handle) -> None:
    return None


def handle_create_pipeline_job(data: dict[str, Any]) -> dict:
    kind = str((data or {}).get('kind', '')).strip() or 'context'
    target_date = str((data or {}).get('target_date', '')).strip() or None

    def run_fn(handle):
        return _server().run_pipeline_job_command(kind, target_date, handle)

    return _server().JOB_RUNNER.create_job(kind=kind, target_date=target_date, run_fn=run_fn)
