#!/usr/bin/env python3
import time
import unittest

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


if __name__ == "__main__":
    unittest.main()
