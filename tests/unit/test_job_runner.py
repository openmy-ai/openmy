#!/usr/bin/env python3
import json
import tempfile
import time
import unittest
from pathlib import Path

from app.job_runner import JobRunner


class TestJobRunner(unittest.TestCase):
    def wait_for_status(self, runner: JobRunner, job_id: str, expected_status: str, timeout: float = 1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = runner.get_job(job_id)
            if job and job["status"] == expected_status:
                return job
            time.sleep(0.01)
        self.fail(f"job {job_id} did not reach status {expected_status}")

    def test_create_job_starts_in_queued_state(self):
        runner = JobRunner()

        job = runner.create_job(
            kind="context",
            target_date="2026-04-08",
            run_fn=lambda handle: time.sleep(0.05),
        )

        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["kind"], "context")
        self.assertEqual(job["target_date"], "2026-04-08")

    def test_job_transitions_to_running_and_succeeded(self):
        runner = JobRunner()

        def run_task(handle):
            handle.step("running context")
            handle.log("context started")
            time.sleep(0.05)
            handle.add_artifact("data/active_context.json")

        job = runner.create_job(kind="context", target_date="2026-04-08", run_fn=run_task)
        completed = self.wait_for_status(runner, job["job_id"], "succeeded")

        self.assertEqual(completed["current_step"], "running context")
        self.assertIn("context started", completed["log_lines"])
        self.assertEqual(completed["artifacts"], ["data/active_context.json"])
        self.assertIsNotNone(completed["started_at"])
        self.assertIsNotNone(completed["finished_at"])

    def test_job_failure_captures_log_lines(self):
        runner = JobRunner()

        def run_task(handle):
            handle.step("distilling")
            handle.log("about to fail")
            raise RuntimeError("gemini cli failed")

        job = runner.create_job(kind="distill", target_date="2026-04-08", run_fn=run_task)
        failed = self.wait_for_status(runner, job["job_id"], "failed")

        self.assertEqual(failed["current_step"], "distilling")
        self.assertIn("about to fail", failed["log_lines"])
        self.assertIn("gemini cli failed", failed["log_lines"])
        self.assertEqual(failed["error"], "gemini cli failed")

    def test_job_is_persisted_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = JobRunner(job_dir=Path(tmp_dir))

            job = runner.create_job(
                kind="context",
                target_date="2026-04-08",
                run_fn=lambda handle: handle.log("context ready"),
            )
            completed = self.wait_for_status(runner, job["job_id"], "succeeded")

            job_file = Path(tmp_dir) / f"{job['job_id']}.json"
            self.assertTrue(job_file.exists())
            payload = json.loads(job_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["job_id"], job["job_id"])
            self.assertEqual(payload["status"], "succeeded")
            self.assertIn("context ready", payload["log_lines"])
            self.assertEqual(payload["finished_at"], completed["finished_at"])

    def test_runner_restores_jobs_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = JobRunner(job_dir=Path(tmp_dir))
            created = runner.create_job(
                kind="briefing",
                target_date="2026-04-09",
                run_fn=lambda handle: handle.log("briefing ready"),
            )
            self.wait_for_status(runner, created["job_id"], "succeeded")

            restored = JobRunner(job_dir=Path(tmp_dir))
            payload = restored.get_job(created["job_id"])

            self.assertIsNotNone(payload)
            self.assertEqual(payload["kind"], "briefing")
            self.assertEqual(payload["status"], "succeeded")
            self.assertIn("briefing ready", payload["log_lines"])

    def test_restored_running_job_becomes_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            job_path = Path(tmp_dir) / "job_manual.json"
            job_path.write_text(
                json.dumps(
                    {
                        "job_id": "job_manual",
                        "kind": "run",
                        "target_date": "2026-04-10",
                        "status": "running",
                        "current_step": "distill running",
                        "log_lines": ["distill started"],
                        "started_at": "2026-04-10T10:00:00+08:00",
                        "finished_at": None,
                        "artifacts": [],
                        "error": "",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            runner = JobRunner(job_dir=Path(tmp_dir))
            payload = runner.get_job("job_manual")

            self.assertIsNotNone(payload)
            self.assertEqual(payload["status"], "interrupted")
            self.assertEqual(payload["current_step"], "interrupted")
            self.assertIn("进程重启前任务未完成", payload["error"])
            self.assertIsNotNone(payload["finished_at"])


if __name__ == "__main__":
    unittest.main()
