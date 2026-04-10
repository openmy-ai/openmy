from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openmy.adapters.transcription.gemini_cli import load_vocab_terms
from openmy.config import AUDIO_PIPELINE_TIMEOUT, GEMINI_MODEL, get_stt_api_key, get_stt_model
from openmy.providers.registry import ProviderRegistry


ROOT_DIR = Path(__file__).resolve().parents[4]
VOCAB_FILE = ROOT_DIR / "src" / "openmy" / "resources" / "vocab.txt"
AUDIO_TIME_RE = re.compile(r".*?(\d{8})_(\d{2})(\d{2})(\d{2}).*")
SILENCE_FILTER = (
    "silenceremove="
    "stop_periods=-1:"
    "stop_duration=1.5:"
    "stop_threshold=-35dB:"
    "start_periods=1:"
    "start_threshold=-35dB"
)


@dataclass(frozen=True)
class PreparedChunk:
    path: Path
    time_label: str


def run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(
        ["ffmpeg", *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:2000] or "ffmpeg 执行失败")


def probe_duration_seconds(path: Path) -> int:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:2000] or f"ffprobe 读取时长失败: {path}")
    try:
        return int(float(proc.stdout.strip() or "0"))
    except ValueError as exc:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"无法解析音频时长: {path}") from exc


def parse_audio_time(audio_path: Path) -> str:
    match = AUDIO_TIME_RE.match(audio_path.name)
    if not match:
        return ""
    return f"{match.group(2)}:{match.group(3)}"


def offset_time_label(base_time: str, offset_minutes: int) -> str:
    if not base_time or ":" not in base_time:
        base_time = "00:00"

    hour_str, minute_str = base_time.split(":", 1)
    total_minutes = int(hour_str) * 60 + int(minute_str) + offset_minutes
    hour = total_minutes // 60
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


def transcribe_audio(
    audio_path: Path,
    *,
    api_key: str,
    model: str,
    vocab_terms: str,
    timeout_seconds: int,
) -> str:
    provider = ProviderRegistry.from_env().get_stt_provider(model=model, api_key=api_key)
    return provider.transcribe(
        audio_path,
        vocab_terms=vocab_terms,
        timeout_seconds=timeout_seconds,
    )


def load_sidecar_transcript(audio_path: Path) -> str:
    candidates = [
        audio_path.with_suffix(".transcript.txt"),
        audio_path.with_suffix(".transcript.md"),
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return ""


def prepare_audio_chunks(audio_path: Path, work_dir: Path, chunk_minutes: int = 10) -> list[PreparedChunk]:
    work_dir.mkdir(parents=True, exist_ok=True)
    stripped_path = work_dir / f"{audio_path.stem}_stripped.wav"

    run_ffmpeg(
        [
            "-i",
            str(audio_path),
            "-af",
            SILENCE_FILTER,
            "-ar",
            "16000",
            "-ac",
            "1",
            str(stripped_path),
            "-y",
            "-loglevel",
            "error",
        ]
    )

    stripped_duration = probe_duration_seconds(stripped_path)
    if stripped_duration < 3:
        return []

    compressed_path = work_dir / f"{audio_path.stem}.mp3"
    run_ffmpeg(
        [
            "-i",
            str(stripped_path),
            "-codec:a",
            "libmp3lame",
            "-qscale:a",
            "4",
            str(compressed_path),
            "-y",
            "-loglevel",
            "error",
        ]
    )

    processed_duration = probe_duration_seconds(compressed_path)
    base_time = parse_audio_time(audio_path)
    split_threshold = chunk_minutes * 60
    if processed_duration <= split_threshold:
        return [PreparedChunk(path=compressed_path, time_label=offset_time_label(base_time, 0))]

    chunk_dir = work_dir / f"{audio_path.stem}_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_pattern = chunk_dir / "sub_%04d.mp3"
    run_ffmpeg(
        [
            "-i",
            str(compressed_path),
            "-f",
            "segment",
            "-segment_time",
            str(split_threshold),
            "-c",
            "copy",
            "-reset_timestamps",
            "1",
            str(chunk_pattern),
            "-y",
            "-loglevel",
            "warning",
        ]
    )

    chunks = sorted(chunk_dir.glob("sub_*.mp3"))
    return [
        PreparedChunk(path=chunk_path, time_label=offset_time_label(base_time, index * chunk_minutes))
        for index, chunk_path in enumerate(chunks)
    ]


def transcribe_audio_files(
    date_str: str,
    audio_files: list[str],
    output_dir: Path,
    model: str | None = None,
    chunk_minutes: int = 10,
    gemini_home: Path | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    vocab_terms = load_vocab_terms(VOCAB_FILE)

    final_model = model or get_stt_model() or GEMINI_MODEL
    api_key = get_stt_api_key()

    rendered_parts: list[str] = [
        f"# {date_str} 上下文（原始）",
        "",
        "> 来源：OpenMy CLI 音频导入",
        f"> 转写时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 音频文件数：{len(audio_files)} 段",
        "",
        "---",
        "",
    ]

    with tempfile.TemporaryDirectory(prefix="openmy-ingest-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for index, audio_name in enumerate(audio_files, start=1):
            audio_path = Path(audio_name).expanduser().resolve()
            if not audio_path.is_file():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")

            if not api_key:
                sidecar_transcript = load_sidecar_transcript(audio_path)
                if sidecar_transcript:
                    rendered_parts.extend([f"## {offset_time_label(parse_audio_time(audio_path), 0)}", "", sidecar_transcript, ""])
                    continue
                raise RuntimeError("缺少 GEMINI_API_KEY 环境变量")

            chunks = prepare_audio_chunks(
                audio_path=audio_path,
                work_dir=tmp_root / f"audio_{index:03d}",
                chunk_minutes=chunk_minutes,
            )

            for chunk in chunks:
                transcript = ""
                last_error: Exception | None = None
                for attempt in range(1, 4):
                    try:
                        transcript = transcribe_audio(
                            audio_path=chunk.path,
                            api_key=api_key,
                            model=final_model,
                            vocab_terms=vocab_terms,
                            timeout_seconds=AUDIO_PIPELINE_TIMEOUT,
                        )
                        last_error = None
                        break
                    except Exception as exc:  # pragma: no cover - retried behavior exercised by tests
                        last_error = exc
                        if attempt == 3:
                            raise
                        time.sleep(5)

                if last_error is not None:  # pragma: no cover - guarded by raise above
                    raise last_error

                rendered_parts.extend([f"## {chunk.time_label}", "", transcript.strip(), ""])

    output_path = output_dir / "transcript.raw.md"
    output_path.write_text("\n".join(rendered_parts).strip() + "\n", encoding="utf-8")
    return output_path
