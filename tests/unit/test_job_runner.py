#!/usr/bin/env python3
import json
import tempfile
import time
import unittest
from pathlib import Path

from app.job_runner import JobController, JobRunner


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

    def test_structured_steps_drive_progress_and_eta(self):
        runner = JobRunner()
        job = runner.create_job(
            kind="run",
            target_date="2026-04-10",
            steps=[
                {"name": "transcribe", "label": "转写"},
                {"name": "clean", "label": "清洗"},
            ],
            source_file="demo.wav",
            source_size_bytes=20 * 1024 * 1024,
        )

        initial = runner.get_job(job["job_id"])
        self.assertEqual(initial["progress_pct"], 0)
        self.assertGreater(initial["eta_seconds"], 0)

        runner.set_step(job["job_id"], {"name": "transcribe", "label": "转写", "status": "running"})
        running = runner.get_job(job["job_id"])
        self.assertEqual(running["current_step"], "transcribe")
        self.assertEqual(running["progress_pct"], 25)
        self.assertGreater(running["eta_seconds"], 0)

        runner.set_step(
            job["job_id"],
            {"name": "transcribe", "label": "转写", "status": "done", "result_summary": "检测到 3 段对话"},
        )
        completed = runner.get_job(job["job_id"])
        self.assertEqual(completed["steps"][0]["status"], "done")
        self.assertEqual(completed["steps"][0]["result_summary"], "检测到 3 段对话")
        self.assertEqual(completed["progress_pct"], 50)

    def test_pause_resume_cancel_and_skip_update_job_state(self):
        runner = JobRunner()
        job = runner.create_job(
            kind="run",
            target_date="2026-04-10",
            steps=["转写", "清洗"],
        )
        runner.update_job(job["job_id"], status="running")

        self.assertFalse(runner.pause_job(job["job_id"]))
        self.assertFalse(runner.get_job(job["job_id"])["can_pause"])

        runner.register_controller(
            job["job_id"],
            JobController(
                pause_fn=lambda: None,
                resume_fn=lambda: None,
                skip_fn=lambda: None,
            ),
        )

        runner.pause_job(job["job_id"])
        paused = runner.get_job(job["job_id"])
        self.assertEqual(paused["status"], "paused")
        self.assertFalse(paused["can_pause"])

        runner.resume_job(job["job_id"])
        resumed = runner.get_job(job["job_id"])
        self.assertEqual(resumed["status"], "running")
        self.assertTrue(resumed["can_pause"])

        runner.update_job(job["job_id"], can_skip=True)
        runner.skip_job_step(job["job_id"])
        skipped = runner.get_job(job["job_id"])
        self.assertIn("已收到跳过当前步骤的请求", skipped["log_lines"])

        runner.cancel_job(job["job_id"])
        cancelled = runner.get_job(job["job_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["eta_seconds"], 0)

    def test_progress_hits_hundred_for_all_skipped_steps(self):
        runner = JobRunner()
        job = runner.create_job(
            kind="run",
            target_date="2026-04-10",
            steps=[
                {"name": "distill", "label": "蒸馏", "status": "skipped"},
                {"name": "briefing", "label": "日报", "status": "skipped"},
            ],
        )

        payload = runner.get_job(job["job_id"])
        self.assertEqual(payload["progress_pct"], 100)

    def test_single_step_progress_and_eta_fallbacks(self):
        runner = JobRunner()
        job = runner.create_job(
            kind="run",
            target_date="2026-04-10",
            steps=[{"name": "transcribe", "label": "转写"}],
            source_size_bytes=1024,
        )
        runner.set_step(job["job_id"], {"name": "transcribe", "label": "转写", "status": "running"})
        running = runner.get_job(job["job_id"])
        self.assertEqual(running["progress_pct"], 50)
        self.assertEqual(running["eta_seconds"], 7)

        runner.set_step(job["job_id"], {"name": "transcribe", "label": "转写", "status": "done"})
        runner.update_job(job["job_id"], status="succeeded")
        completed = runner.get_job(job["job_id"])
        self.assertEqual(completed["progress_pct"], 100)
        self.assertEqual(completed["eta_seconds"], 0)

    def test_zero_step_jobs_report_reasonable_progress(self):
        runner = JobRunner()
        queued = runner.create_job(kind="context", target_date="2026-04-10", steps=[])
        self.assertEqual(runner.get_job(queued["job_id"])["progress_pct"], 0)

        runner.update_job(queued["job_id"], status="succeeded")
        succeeded = runner.get_job(queued["job_id"])
        self.assertEqual(succeeded["progress_pct"], 100)
        self.assertEqual(succeeded["eta_seconds"], 0)

    def test_eta_returns_none_without_history_or_size(self):
        runner = JobRunner()
        job = runner.create_job(
            kind="run",
            target_date="2026-04-10",
            steps=[{"name": "transcribe", "label": "转写"}],
        )
        runner.set_step(job["job_id"], {"name": "transcribe", "label": "转写", "status": "running"})

        payload = runner.get_job(job["job_id"])
        self.assertIsNone(payload["eta_seconds"])

    def test_eta_clamps_large_files(self):
        runner = JobRunner()
        job = runner.create_job(
            kind="run",
            target_date="2026-04-10",
            steps=[
                {"name": "transcribe", "label": "转写"},
                {"name": "distill", "label": "蒸馏"},
            ],
            source_size_bytes=10 * 1024 * 1024 * 1024,
        )
        runner.set_step(job["job_id"], {"name": "transcribe", "label": "转写", "status": "running"})

        payload = runner.get_job(job["job_id"])
        self.assertEqual(payload["eta_seconds"], 900)


if __name__ == "__main__":
    unittest.main()
