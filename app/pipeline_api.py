from __future__ import annotations

import subprocess
import sys


def _server():
    import app.server as server_module

    return server_module


def build_pipeline_command(kind: str, target_date: str | None) -> list[str]:
    commands = {
        "context": [sys.executable, "-m", "openmy", "context"],
        "run": [sys.executable, "-m", "openmy", "run", target_date or ""],
        "clean": [sys.executable, "-m", "openmy", "clean", target_date or ""],
        "roles": [sys.executable, "-m", "openmy", "roles", target_date or ""],
        "distill": [sys.executable, "-m", "openmy", "distill", target_date or ""],
        "briefing": [sys.executable, "-m", "openmy", "briefing", target_date or ""],
    }
    return commands[kind]


def run_pipeline_job_command(kind: str, target_date: str | None, handle) -> None:
    server = _server()
    command = build_pipeline_command(kind, target_date)
    handle.step(f"{kind} running")
    handle.log(" ".join(command))
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=server.ROOT_DIR,
    )
    for line in result.stdout.splitlines():
        if line.strip():
            handle.log(line)
    for line in result.stderr.splitlines():
        if line.strip():
            handle.log(line)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"{kind} failed")

    artifact_map = {
        "context": [str(server.DATA_ROOT / "active_context.json")],
        "run": [
            str(server.DATA_ROOT / (target_date or "") / "scenes.json"),
            str(server.DATA_ROOT / (target_date or "") / "daily_briefing.json"),
        ],
        "clean": [str(server.DATA_ROOT / (target_date or "") / "transcript.md")],
        "roles": [str(server.DATA_ROOT / (target_date or "") / "scenes.json")],
        "distill": [str(server.DATA_ROOT / (target_date or "") / "scenes.json")],
        "briefing": [str(server.DATA_ROOT / (target_date or "") / "daily_briefing.json")],
    }
    for artifact in artifact_map.get(kind, []):
        handle.add_artifact(artifact)


def handle_create_pipeline_job(data: dict) -> dict:
    server = _server()
    kind = str(data.get("kind", "")).strip()
    target_date = str(data.get("target_date", "")).strip() or None
    valid_kinds = {"context", "run", "clean", "roles", "distill", "briefing"}
    if kind not in valid_kinds:
        return {"success": False, "error": f"不支持的 pipeline kind: {kind}"}
    if kind != "context" and not target_date:
        return {"success": False, "error": "target_date 不能为空"}

    return server.JOB_RUNNER.create_job(
        kind=kind,
        target_date=target_date,
        run_fn=lambda handle: server.run_pipeline_job_command(kind, target_date, handle),
    )


def get_pipeline_jobs_payload(limit: int = 20) -> list[dict]:
    server = _server()
    return server.JOB_RUNNER.list_jobs(limit=limit)


def get_pipeline_job_payload(job_id: str):
    server = _server()
    return server.JOB_RUNNER.get_job(job_id)
