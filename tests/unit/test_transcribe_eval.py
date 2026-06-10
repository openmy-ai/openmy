#!/usr/bin/env python3
"""评测入口 scripts/transcribe_eval.py 的单测：清单加载、产物组装、prompt 参数化回归。"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "transcribe_eval", PROJECT_ROOT / "scripts" / "transcribe_eval.py"
)
transcribe_eval = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SPEC and transcribe_eval)


def _write_manifest(tmpdir: Path, segments: list[dict]) -> Path:
    manifest_path = tmpdir / "testset.json"
    manifest_path.write_text(
        json.dumps({"segments": segments, "hard_error_categories": ["凑字", "歌词混入"]}),
        encoding="utf-8",
    )
    return manifest_path


class LoadManifestTest(unittest.TestCase):
    def test_loads_complete_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = _write_manifest(tmp, [
                {"id": "a", "label": "段A", "audio": "data/a.mp3", "time_label": "16:50"},
            ])
            manifest = transcribe_eval.load_manifest(manifest_path, require_audio=False)
            self.assertEqual(len(manifest["segments"]), 1)
            self.assertEqual(manifest["segments"][0]["id"], "a")

    def test_missing_field_reports_segment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = _write_manifest(tmp, [
                {"id": "a", "label": "段A", "time_label": "16:50"},
            ])
            with self.assertRaises(SystemExit) as ctx:
                transcribe_eval.load_manifest(manifest_path, require_audio=False)
            self.assertIn("audio", str(ctx.exception))

    def test_missing_audio_names_segment_not_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = _write_manifest(tmp, [
                {"id": "ktv", "label": "KTV 段", "audio": "data/__no_such__.mp3", "time_label": "21:03"},
            ])
            with self.assertRaises(SystemExit) as ctx:
                transcribe_eval.load_manifest(manifest_path, require_audio=True)
            message = str(ctx.exception)
            self.assertIn("ktv", message)
            self.assertIn("不在本地磁盘", message)

    def test_repo_manifest_is_valid(self):
        manifest = transcribe_eval.load_manifest(
            PROJECT_ROOT / "scripts" / "eval_testset.json", require_audio=False
        )
        self.assertEqual(len(manifest["segments"]), 4)
        self.assertIn("wearer_split_criteria", manifest)
        self.assertEqual(len(manifest["hard_error_categories"]), 4)


class RenderTest(unittest.TestCase):
    SEGMENTS = [
        {"id": "a", "label": "段A", "audio": "data/a.mp3", "time_label": "16:50"},
        {"id": "b", "label": "段B", "audio": "data/b.mp3", "time_label": "21:03"},
    ]

    def test_side_by_side_aligns_runs_and_labels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dir_a, dir_b = tmp / "run_a", tmp / "run_b"
            dir_a.mkdir()
            dir_b.mkdir()
            for seg in self.SEGMENTS:
                (dir_a / f"{seg['id']}.md").write_text(
                    transcribe_eval.render_segment_md("run_a", seg, f"A版{seg['id']}正文"),
                    encoding="utf-8",
                )
            (dir_b / "a.md").write_text(
                transcribe_eval.render_segment_md("run_b", self.SEGMENTS[0], "B版a正文"),
                encoding="utf-8",
            )
            manifest = {"segments": self.SEGMENTS, "hard_error_categories": ["凑字"]}
            output = transcribe_eval.render_side_by_side(manifest, "run_a", dir_a, "run_b", dir_b)
            self.assertIn("段A（16:50）", output)
            self.assertIn("A版a正文", output)
            self.assertIn("B版a正文", output)
            # run_b 缺段 b 时明确标注而非崩溃
            self.assertIn("[该 run 缺少本段产物]", output)
            # 两个版本标识都在
            self.assertIn("### run_a", output)
            self.assertIn("### run_b", output)


class PromptParameterizationTest(unittest.TestCase):
    """U1 回归：不传 system_instruction 时行为与原先逐字一致。"""

    def _make_provider_and_client(self):
        from openmy.providers.stt import gemini as gemini_stt

        provider = gemini_stt.GeminiSTTProvider(api_key="fake", model="gemini-test")
        mock_client = MagicMock()
        uploaded = MagicMock()
        uploaded.state = "ACTIVE"
        uploaded.uri = "files/fake"
        uploaded.mime_type = "audio/mp3"
        mock_client.files.upload.return_value = uploaded
        response = MagicMock()
        response.text = "转写文本"
        mock_client.models.generate_content.return_value = response
        return gemini_stt, provider, mock_client

    def test_default_uses_builtin_instruction_and_prompt(self):
        gemini_stt, provider, mock_client = self._make_provider_and_client()
        with patch.object(gemini_stt.genai, "Client", return_value=mock_client):
            provider.transcribe(Path("/tmp/fake.mp3"), vocab_terms="词A", timeout_seconds=10)
        call = mock_client.models.generate_content.call_args
        config = call.kwargs["config"]
        self.assertEqual(config.system_instruction, gemini_stt.SYSTEM_INSTRUCTION)
        self.assertEqual(config.temperature, 0.0)
        parts = call.kwargs["contents"][0].parts
        self.assertIn("词A", parts[0].text)
        self.assertEqual(parts[0].text, gemini_stt.build_prompt("词A"))

    def test_override_instruction_is_passed_through(self):
        gemini_stt, provider, mock_client = self._make_provider_and_client()
        with patch.object(gemini_stt.genai, "Client", return_value=mock_client):
            provider.transcribe(
                Path("/tmp/fake.mp3"),
                vocab_terms="",
                timeout_seconds=10,
                system_instruction="实验版指令",
            )
        config = mock_client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.system_instruction, "实验版指令")


if __name__ == "__main__":
    unittest.main()
