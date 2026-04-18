from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openmy.adapters.transcription.gemini_cli import load_vocab_terms
from openmy.config import (
    AUDIO_PIPELINE_TIMEOUT,
    GEMINI_MODEL,
    get_audio_source_dir,
    get_stt_api_key,
    get_stt_model,
    get_stt_provider_name,
    get_stt_vad_enabled,
    get_stt_word_timestamps_enabled,
    stt_provider_requires_api_key,
)
from openmy.utils.errors import FriendlyCliError, doc_url
from openmy.providers.base import TranscriptionResult, TranscriptionSegment, TranscriptionWord
from openmy.providers.registry import ProviderRegistry
from openmy.services.cleaning.cleaner import VOCAB_EXAMPLE_FILE, VOCAB_FILE, resolve_resource_path


ROOT_DIR = Path(__file__).resolve().parents[4]
AUDIO_TIME_RE = re.compile(r".*?(\d{8})_(\d{2})(\d{2})(\d{2}).*")
SILENCE_FILTER = (
    "silenceremove="
    "stop_periods=-1:"
    "stop_duration=1.5:"
    "stop_threshold=-35dB:"
    "start_periods=1:"
    "start_threshold=-35dB"
)

AUDIO_SOURCE_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".mp4",
    ".mov",
    ".flac",
    ".ogg",
    ".webm",
}


@dataclass(frozen=True)
class PreparedChunk:
    path: Path
    time_label: str
    duration_seconds: float = 0.0
    speech_segments: list[dict[str, float]] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkJob:
    source_audio_path: Path
    persistent_chunk_path: Path
    time_label: str
    duration_seconds: float = 0.0
    speech_segments: list[dict[str, float]] = field(default_factory=list)


def run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(
        ["ffmpeg", *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:2000] or "ffmpeg 执行失败")


def probe_duration_seconds(path: Path) -> float:
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
    raw_duration = proc.stdout.strip() or "0"
    try:
        return float(raw_duration)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", raw_duration)
        if match:
            return float(match.group(0))
        return 0.0


def run_silero_vad(audio_path: Path) -> list[dict[str, float]]:
    """用 Silero VAD 检测音频中的人声段，返回秒级片段。"""
    try:
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad
    except ImportError:
        return []

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        tmp_wav = Path(handle.name)

    try:
        run_ffmpeg(
            [
                "-i",
                str(audio_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "wav",
                "-acodec",
                "pcm_s16le",
                str(tmp_wav),
                "-y",
                "-loglevel",
                "error",
            ]
        )

        import struct
        import wave

        with wave.open(str(tmp_wav), "rb") as wav_file:
            frame_count = wav_file.getnframes()
            if frame_count <= 0:
                return []
            raw_data = wav_file.readframes(frame_count)
            sample_rate = wav_file.getframerate()

        samples = struct.unpack(f"<{frame_count}h", raw_data)
        wav_tensor = torch.tensor(samples, dtype=torch.float32) / 32768.0
        model = load_silero_vad()
        speech_timestamps = get_speech_timestamps(
            wav_tensor,
            model,
            sampling_rate=sample_rate,
            return_seconds=True,
        )
        segments: list[dict[str, float]] = []
        for item in speech_timestamps:
            try:
                start = round(float(item.get("start", 0.0) or 0.0), 2)
                end = round(float(item.get("end", 0.0) or 0.0), 2)
            except (AttributeError, TypeError, ValueError):
                continue
            if end < start:
                end = start
            segments.append({"start": start, "end": end})
        return segments
    except Exception:
        return []
    finally:
        if tmp_wav.exists():
            tmp_wav.unlink()


def parse_audio_time(audio_path: Path) -> str:
    match = AUDIO_TIME_RE.match(audio_path.name)
    if not match:
        return ""
    return f"{match.group(2)}:{match.group(3)}"


def discover_audio_files_for_date(source_dir: str | Path | None, date_str: str) -> list[str]:
    raw_dir = Path(str(source_dir or "")).expanduser() if source_dir else None
    if raw_dir is None or not raw_dir.exists() or not raw_dir.is_dir():
        return []

    discovered: list[tuple[float, str]] = []
    for path in raw_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in AUDIO_SOURCE_EXTENSIONS:
            continue
        try:
            modified_date = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        except OSError:
            continue
        if modified_date != date_str:
            continue
        discovered.append((path.stat().st_mtime, str(path.resolve())))

    discovered.sort()
    return [path for _, path in discovered]


def discover_configured_audio_files(date_str: str) -> list[str]:
    return discover_audio_files_for_date(get_audio_source_dir(), date_str)


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


def load_sidecar_transcript(audio_path: Path) -> str:
    candidates = [
        audio_path.with_suffix(".transcript.txt"),
        audio_path.with_suffix(".transcript.md"),
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return ""


def build_prepared_chunk(
    chunk_path: Path,
    time_label: str,
    *,
    vad_enabled: bool = True,
) -> PreparedChunk:
    duration_seconds = float(probe_duration_seconds(chunk_path) or 0.0)
    speech_segments = run_silero_vad(chunk_path) if vad_enabled else []
    return PreparedChunk(
        path=chunk_path,
        time_label=time_label,
        duration_seconds=duration_seconds,
        speech_segments=speech_segments,
    )


def prepare_audio_chunks(
    audio_path: Path,
    work_dir: Path,
    chunk_minutes: int = 10,
    provider_name: str | None = None,
    vad_enabled: bool = True,
) -> list[PreparedChunk]:
    work_dir.mkdir(parents=True, exist_ok=True)
    final_provider_name = (provider_name or "").lower()
    prefer_wav_chunks = final_provider_name == "funasr"
    compressed_path = work_dir / f"{audio_path.stem}.mp3"
    normalized_wav_path = work_dir / f"{audio_path.stem}.wav"

    def normalize_source(source_path: Path, output_path: Path) -> Path:
        command = [
            "-i",
            str(source_path),
            "-ar",
            "16000",
            "-ac",
            "1",
        ]
        if output_path.suffix == ".mp3":
            command.extend(["-codec:a", "libmp3lame", "-qscale:a", "4"])
        command.extend([str(output_path), "-y", "-loglevel", "error"])
        run_ffmpeg(command)
        return output_path

    processed_path = normalize_source(audio_path, normalized_wav_path if prefer_wav_chunks else compressed_path)
    processed_duration = probe_duration_seconds(processed_path)
    base_time = parse_audio_time(audio_path)
    split_threshold = chunk_minutes * 60
    if processed_duration <= split_threshold:
        return [
            build_prepared_chunk(
                processed_path,
                offset_time_label(base_time, 0),
                vad_enabled=vad_enabled,
            )
        ]

    chunk_dir = work_dir / f"{audio_path.stem}_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_suffix = "wav" if prefer_wav_chunks else "mp3"
    chunk_pattern = chunk_dir / f"sub_%04d.{chunk_suffix}"
    segment_args = [
        "-i",
        str(processed_path),
        "-f",
        "segment",
        "-segment_time",
        str(split_threshold),
    ]
    if prefer_wav_chunks:
        segment_args.extend(["-ar", "16000", "-ac", "1"])
    else:
        segment_args.extend(["-c", "copy", "-reset_timestamps", "1"])
    segment_args.extend([str(chunk_pattern), "-y", "-loglevel", "warning"])
    run_ffmpeg(segment_args)

    chunks = sorted(chunk_dir.glob(f"sub_*.{chunk_suffix}"))
    return [
        build_prepared_chunk(
            chunk_path,
            offset_time_label(base_time, index * chunk_minutes),
            vad_enabled=vad_enabled,
        )
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


def _transcribe_chunk_with_retry(
    chunk_job: ChunkJob,
    *,
    provider_name: str,
    api_key: str,
    model: str,
    vocab_terms: str,
    vad_filter: bool,
    word_timestamps: bool,
) -> tuple[ChunkJob, TranscriptionResult]:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            transcript_payload = transcribe_audio(
                audio_path=chunk_job.persistent_chunk_path,
                provider_name=provider_name,
                api_key=api_key,
                model=model,
                vocab_terms=vocab_terms,
                timeout_seconds=AUDIO_PIPELINE_TIMEOUT,
                vad_filter=vad_filter,
                word_timestamps=word_timestamps,
            )
            return chunk_job, _coerce_transcription_result(transcript_payload)
        except Exception as exc:  # pragma: no cover - retried behavior exercised by tests
            last_error = exc
            if attempt == 3:
                raise
            time.sleep(5)

    if last_error is not None:  # pragma: no cover - guarded by raise above
        raise last_error
    raise RuntimeError("转写 chunk 失败")


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
    vocab_path = resolve_resource_path(VOCAB_FILE, VOCAB_EXAMPLE_FILE)
    vocab_terms = load_vocab_terms(vocab_path) if vocab_path else ""
    persisted_chunk_dir = output_dir / "stt_chunks"
    persisted_chunk_dir.mkdir(parents=True, exist_ok=True)

    final_provider_name = (provider_name or get_stt_provider_name()).lower()
    final_model = model or get_stt_model(final_provider_name) or GEMINI_MODEL
    final_vad_filter = get_stt_vad_enabled() if vad_filter is None else vad_filter
    final_word_timestamps = (
        get_stt_word_timestamps_enabled() if word_timestamps is None else word_timestamps
    )
    api_key = get_stt_api_key(final_provider_name)

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
                raise FriendlyCliError(
                    "音频文件不存在，没法开始处理。",
                    code="audio_file_missing",
                    fix="先确认音频路径写对了，再重试。",
                    doc_url=doc_url("一分钟跑起来"),
                    message_en=f"Audio file does not exist: {audio_path}",
                    fix_en="Check the audio file path and retry.",
                )

            if stt_provider_requires_api_key(final_provider_name) and not api_key:
                sidecar_transcript = load_sidecar_transcript(audio_path)
                if sidecar_transcript:
                    rendered_parts.extend([f"## {offset_time_label(parse_audio_time(audio_path), 0)}", "", sidecar_transcript, ""])
                    continue
                raise FriendlyCliError(
                    f"缺少 {final_provider_name} 转写路线要用的 API key（访问口令）。",
                    code="stt_api_key_missing",
                    fix="先把对应 key 写进项目 `.env（环境文件）`，再重试。",
                    doc_url=doc_url("语音转写"),
                    message_en=f"Missing API key for the {final_provider_name} speech-to-text route.",
                    fix_en="Add the matching API key to the project .env file, then retry.",
                )

            chunks = prepare_audio_chunks(
                audio_path=audio_path,
                work_dir=tmp_root / f"audio_{index:03d}",
                chunk_minutes=chunk_minutes,
                provider_name=final_provider_name,
                vad_enabled=final_vad_filter,
            )
            chunk_jobs: list[ChunkJob] = []
            for chunk in chunks:
                persistent_chunk_path = persisted_chunk_dir / f"audio_{index:03d}_{chunk.path.name}"
                shutil.copy2(chunk.path, persistent_chunk_path)
                chunk_jobs.append(
                    ChunkJob(
                        source_audio_path=audio_path,
                        persistent_chunk_path=persistent_chunk_path,
                        time_label=chunk.time_label,
                        duration_seconds=chunk.duration_seconds,
                        speech_segments=chunk.speech_segments,
                    )
                )

            def transcribe_fn(job: ChunkJob) -> tuple[ChunkJob, TranscriptionResult]:
                return _transcribe_chunk_with_retry(
                    job,
                    provider_name=final_provider_name,
                    api_key=api_key,
                    model=final_model,
                    vocab_terms=vocab_terms,
                    vad_filter=final_vad_filter,
                    word_timestamps=final_word_timestamps,
                )

            if stt_provider_requires_api_key(final_provider_name):
                with ThreadPoolExecutor(max_workers=5) as executor:
                    chunk_results = list(executor.map(transcribe_fn, chunk_jobs))
            else:
                chunk_results = [transcribe_fn(job) for job in chunk_jobs]

            for chunk_job, transcript_result in chunk_results:
                rendered_parts.extend([f"## {chunk_job.time_label}", "", transcript_result.text.strip(), ""])
                transcription_payload["chunks"].append(
                    {
                        "chunk_id": f"chunk_{len(transcription_payload['chunks']) + 1:04d}",
                        "source_audio_path": str(chunk_job.source_audio_path),
                        "chunk_path": str(chunk_job.persistent_chunk_path),
                        "time_label": chunk_job.time_label,
                        "text": transcript_result.text,
                        "language": transcript_result.language,
                        "duration_seconds": chunk_job.duration_seconds or transcript_result.duration_seconds,
                        "speech_segments": chunk_job.speech_segments,
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
