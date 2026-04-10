from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openmy.adapters.transcription.gemini_cli import load_vocab_terms
from openmy.config import (
    AUDIO_PIPELINE_TIMEOUT,
    GEMINI_MODEL,
    get_stt_api_key,
    get_stt_model,
    get_stt_provider_name,
    get_stt_vad_enabled,
    get_stt_word_timestamps_enabled,
    stt_provider_requires_api_key,
)
from openmy.providers.base import TranscriptionResult, TranscriptionSegment, TranscriptionWord
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
    provider_name: str | None = None,
    api_key: str,
    model: str,
    vocab_terms: str,
    timeout_seconds: int,
    vad_filter: bool = False,
    word_timestamps: bool = False,
) -> TranscriptionResult:
    final_provider_name = (provider_name or get_stt_provider_name()).lower()
    provider = ProviderRegistry.from_env().get_stt_provider(
        provider_name=final_provider_name,
        model=model,
        api_key=api_key,
    )
    return provider.transcribe(
        audio_path,
        vocab_terms=vocab_terms,
        timeout_seconds=timeout_seconds,
        vad_filter=vad_filter,
        word_timestamps=word_timestamps,
    )


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


def _coerce_transcription_result(payload: Any) -> TranscriptionResult:
    if isinstance(payload, TranscriptionResult):
        return payload
    if isinstance(payload, str):
        text = payload.strip()
        return TranscriptionResult(
            text=text,
            segments=[TranscriptionSegment(id="seg_0001", text=text)] if text else [],
        )
    if isinstance(payload, dict):
        segments: list[TranscriptionSegment] = []
        for index, item in enumerate(payload.get("segments", []), start=1):
            if not isinstance(item, dict):
                continue
            words = [
                TranscriptionWord(
                    text=str(word.get("text", "") or ""),
                    start=float(word.get("start", 0.0) or 0.0),
                    end=float(word.get("end", 0.0) or 0.0),
                    probability=float(word.get("probability", 0.0) or 0.0),
                    speaker=str(word.get("speaker", "") or ""),
                )
                for word in item.get("words", [])
                if isinstance(word, dict)
            ]
            segments.append(
                TranscriptionSegment(
                    id=str(item.get("id", "") or f"seg_{index:04d}"),
                    text=str(item.get("text", "") or ""),
                    start=float(item.get("start", 0.0) or 0.0),
                    end=float(item.get("end", 0.0) or 0.0),
                    speaker=str(item.get("speaker", "") or ""),
                    words=words,
                )
            )
        return TranscriptionResult(
            text=str(payload.get("text", "") or "").strip(),
            language=str(payload.get("language", "") or ""),
            duration_seconds=float(payload.get("duration_seconds", 0.0) or 0.0),
            segments=segments,
            provider_metadata=dict(payload.get("provider_metadata", {}) or {}),
        )
    raise TypeError(f"不支持的转写结果类型: {type(payload)!r}")


def transcribe_audio_files(
    date_str: str,
    audio_files: list[str],
    output_dir: Path,
    provider_name: str | None = None,
    model: str | None = None,
    chunk_minutes: int = 10,
    vad_filter: bool | None = None,
    word_timestamps: bool | None = None,
    gemini_home: Path | None = None,
) -> Path:
    del gemini_home
    output_dir.mkdir(parents=True, exist_ok=True)
    vocab_terms = load_vocab_terms(VOCAB_FILE)

    final_provider_name = (provider_name or get_stt_provider_name()).lower()
    final_model = model or get_stt_model(final_provider_name) or GEMINI_MODEL
    final_vad_filter = get_stt_vad_enabled() if vad_filter is None else vad_filter
    final_word_timestamps = (
        get_stt_word_timestamps_enabled() if word_timestamps is None else word_timestamps
    )
    api_key = get_stt_api_key(final_provider_name)
    if stt_provider_requires_api_key(final_provider_name) and not api_key:
        raise RuntimeError(f"缺少 {final_provider_name} STT 所需 API key，请检查 `OPENMY_STT_API_KEY` / `GEMINI_API_KEY`。")

    rendered_parts: list[str] = [
        f"# {date_str} 上下文（原始）",
        "",
        "> 来源：OpenMy CLI 音频导入",
        f"> 转写时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 音频文件数：{len(audio_files)} 段",
        f"> 转写后端：{final_provider_name}",
        "",
        "---",
        "",
    ]
    transcription_payload: dict[str, Any] = {
        "schema_version": "openmy.transcription.v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "date": date_str,
        "provider": final_provider_name,
        "model": final_model,
        "vad_filter": final_vad_filter,
        "word_timestamps": final_word_timestamps,
        "audio_file_count": len(audio_files),
        "chunks": [],
    }

    with tempfile.TemporaryDirectory(prefix="openmy-ingest-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for index, audio_name in enumerate(audio_files, start=1):
            audio_path = Path(audio_name).expanduser().resolve()
            if not audio_path.is_file():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")

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
                        transcript_payload = transcribe_audio(
                            audio_path=chunk.path,
                            provider_name=final_provider_name,
                            api_key=api_key,
                            model=final_model,
                            vocab_terms=vocab_terms,
                            timeout_seconds=AUDIO_PIPELINE_TIMEOUT,
                            vad_filter=final_vad_filter,
                            word_timestamps=final_word_timestamps,
                        )
                        transcript_result = _coerce_transcription_result(transcript_payload)
                        transcript = transcript_result.text
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
                transcription_payload["chunks"].append(
                    {
                        "chunk_id": f"chunk_{len(transcription_payload['chunks']) + 1:04d}",
                        "source_audio_path": str(audio_path),
                        "chunk_path": str(chunk.path),
                        "time_label": chunk.time_label,
                        "text": transcript_result.text,
                        "language": transcript_result.language,
                        "duration_seconds": transcript_result.duration_seconds,
                        "segments": [segment.to_dict() for segment in transcript_result.segments],
                        "provider_metadata": transcript_result.provider_metadata,
                    }
                )

    output_path = output_dir / "transcript.raw.md"
    output_path.write_text("\n".join(rendered_parts).strip() + "\n", encoding="utf-8")
    (output_dir / "transcript.transcription.json").write_text(
        json.dumps(transcription_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
