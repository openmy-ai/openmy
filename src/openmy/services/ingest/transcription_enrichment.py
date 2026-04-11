from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from openmy.utils.io import safe_write_json

try:
    import whisperx
except ImportError:  # pragma: no cover - exercised in environments without optional dependency
    whisperx = None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _transcription_path(day_dir: Path) -> Path:
    return day_dir / "transcript.transcription.json"


def _meta_path(day_dir: Path) -> Path:
    return day_dir / f"{day_dir.name}.meta.json"


def _default_meta_payload(date_str: str) -> dict[str, Any]:
    return {
        "date": date_str,
        "daily_summary": "",
        "events": [],
        "decisions": [],
        "todos": [],
        "insights": [],
        "intents": [],
        "facts": [],
        "extract_enrich_status": "skipped",
        "extract_enrich_message": "",
    }


def update_pipeline_meta(day_dir: Path, **fields: Any) -> Path:
    path = _meta_path(day_dir)
    payload = _load_json(path) or _default_meta_payload(day_dir.name)
    payload.update({key: value for key, value in fields.items() if value is not None})
    safe_write_json(path, payload)
    return path


def _normalize_aligned_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, segment in enumerate(payload.get("segments", []), start=1):
        if not isinstance(segment, dict):
            continue
        words = []
        for word in segment.get("words", []) or []:
            if not isinstance(word, dict):
                continue
            text = str(word.get("word", "") or word.get("text", "") or "").strip()
            if not text:
                continue
            words.append(
                {
                    "text": text,
                    "start": float(word.get("start", 0.0) or 0.0),
                    "end": float(word.get("end", 0.0) or 0.0),
                    "probability": float(word.get("score", word.get("probability", 0.0)) or 0.0),
                    "speaker": str(word.get("speaker", "") or ""),
                }
            )
        normalized.append(
            {
                "id": str(segment.get("id", "") or f"aligned_{index:04d}"),
                "text": str(segment.get("text", "") or "").strip(),
                "start": float(segment.get("start", 0.0) or 0.0),
                "end": float(segment.get("end", 0.0) or 0.0),
                "speaker": str(segment.get("speaker", "") or ""),
                "words": words,
            }
        )
    return normalized


def plan_transcription_enrichment(
    *,
    provider_name: str,
    enrich_mode: str,
    diarize_requested: bool,
    diarization_token: str = "",
) -> dict[str, Any]:
    final_mode = (enrich_mode or "recommended").strip().lower()
    local_provider = provider_name in {"faster-whisper", "funasr"}
    if final_mode == "off":
        return {
            "enabled": False,
            "align": False,
            "diarize": False,
            "status": "disabled",
            "diarization_status": "disabled",
            "message": "未启用 WhisperX 精标层",
        }
    if whisperx is None:
        status = "failed" if final_mode == "force" else "skipped"
        return {
            "enabled": False,
            "align": False,
            "diarize": False,
            "status": status,
            "diarization_status": "degraded_missing_token" if diarize_requested else "skipped_missing_dependency",
            "message": "WhisperX 精标层不可用：缺少依赖 whisperx。",
        }
    if not local_provider and final_mode == "recommended":
        return {
            "enabled": False,
            "align": False,
            "diarize": False,
            "status": "skipped",
            "diarization_status": "disabled",
            "message": "推荐精标路径只默认作用于本地 STT provider。",
        }

    diarize = bool(diarize_requested and diarization_token)
    diarization_status = "completed" if diarize else ("degraded_missing_token" if diarize_requested else "disabled")
    return {
        "enabled": True,
        "align": True,
        "diarize": diarize,
        "status": "recommended" if final_mode == "recommended" else "forced",
        "diarization_status": diarization_status,
        "message": "" if diarize or not diarize_requested else "缺少 HuggingFace token，自动降级为仅对齐。",
    }


def run_transcription_enrichment(day_dir: Path, *, diarize: bool = False) -> dict[str, Any]:
    if whisperx is None:
        raise RuntimeError("WhisperX 精标层不可用：缺少依赖 whisperx。可先运行 `uv pip install whisperx`。")

    transcription_path = _transcription_path(day_dir)
    payload = _load_json(transcription_path)
    if not payload:
        raise RuntimeError("缺少 transcript.transcription.json，无法执行精标。")

    chunks = payload.get("chunks", [])
    if not isinstance(chunks, list) or not chunks:
        raise RuntimeError("当前没有可精标的转写 chunk。")

    device = os.getenv("OPENMY_WHISPERX_DEVICE", "cpu") or "cpu"
    diarization_token = os.getenv("HF_TOKEN", "") or os.getenv("HUGGINGFACE_TOKEN", "")
    diarization_pipeline = None
    diarization_enabled = False
    if diarize and diarization_token:
        diarization_pipeline = whisperx.DiarizationPipeline(use_auth_token=diarization_token, device=device)
        diarization_enabled = True

    for chunk in chunks:
        chunk_path = Path(str(chunk.get("chunk_path", "") or ""))
        if not chunk_path.exists():
            raise RuntimeError(f"精标所需 chunk 不存在: {chunk_path}")

        audio = whisperx.load_audio(str(chunk_path))
        raw_segments = []
        for index, segment in enumerate(chunk.get("segments", []), start=1):
            if not isinstance(segment, dict):
                continue
            text = str(segment.get("text", "") or "").strip()
            if not text:
                continue
            raw_segments.append(
                {
                    "id": str(segment.get("id", "") or f"seg_{index:04d}"),
                    "text": text,
                    "start": float(segment.get("start", 0.0) or 0.0),
                    "end": float(segment.get("end", 0.0) or 0.0),
                }
            )
        if not raw_segments and str(chunk.get("text", "")).strip():
            raw_segments.append(
                {
                    "id": "seg_0001",
                    "text": str(chunk.get("text", "")).strip(),
                    "start": 0.0,
                    "end": float(chunk.get("duration_seconds", 0.0) or 0.0),
                }
            )

        language_code = str(chunk.get("language") or payload.get("language") or "en").split("-", 1)[0]
        align_model, metadata = whisperx.load_align_model(language_code=language_code, device=device)
        aligned = whisperx.align(raw_segments, align_model, metadata, audio, device, return_char_alignments=False)

        if diarization_pipeline is not None:
            diarize_segments = diarization_pipeline(audio)
            aligned = whisperx.assign_word_speakers(diarize_segments, aligned)
            chunk["diarization_status"] = "completed"
        elif diarize:
            chunk["diarization_status"] = "skipped"
        else:
            chunk["diarization_status"] = "disabled"

        chunk["aligned_segments"] = _normalize_aligned_segments(aligned)
        chunk["alignment_status"] = "completed"

    payload["enrichment"] = {
        "status": "completed",
        "provider": "whisperx",
        "message": "",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "diarization_enabled": diarization_enabled,
        "diarization_requested": diarize,
    }
    safe_write_json(transcription_path, payload)
    return payload["enrichment"]


def apply_transcription_enrichment_to_scenes(day_dir: Path) -> None:
    scenes_path = day_dir / "scenes.json"
    transcription_path = _transcription_path(day_dir)
    scenes_payload = _load_json(scenes_path)
    transcription_payload = _load_json(transcription_path)
    if not scenes_payload or not transcription_payload:
        return

    chunk_by_time = {
        str(chunk.get("time_label", "")).strip(): chunk
        for chunk in transcription_payload.get("chunks", [])
        if isinstance(chunk, dict)
    }

    for scene in scenes_payload.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        chunk = chunk_by_time.get(str(scene.get("time_start", "")).strip())
        if not chunk:
            continue
        aligned_segments = chunk.get("aligned_segments") or chunk.get("segments") or []
        scene["transcription_evidence"] = [
            {
                "chunk_id": str(chunk.get("chunk_id", "") or ""),
                "segment_id": str(segment.get("id", "") or ""),
                "start": float(segment.get("start", 0.0) or 0.0),
                "end": float(segment.get("end", 0.0) or 0.0),
                "text": str(segment.get("text", "") or ""),
                "speaker": str(segment.get("speaker", "") or ""),
            }
            for segment in aligned_segments
            if isinstance(segment, dict)
        ]
        scene["speaker_hints"] = sorted(
            {
                str(segment.get("speaker", "") or "").strip()
                for segment in aligned_segments
                if isinstance(segment, dict) and str(segment.get("speaker", "") or "").strip()
            }
        )

    safe_write_json(scenes_path, scenes_payload)
