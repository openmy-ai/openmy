from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from openmy.providers.base import (
    SpeechToTextProvider,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)

try:
    from funasr import AutoModel
except ImportError:  # pragma: no cover - exercised in environments without optional dependency
    AutoModel = None


_MODEL_CACHE: dict[tuple[str, str, bool], object] = {}


def _to_seconds(value: Any) -> float:
    numeric = float(value or 0.0)
    if numeric >= 100:
        return numeric / 1000.0
    return numeric


def _get_model(model_name: str, device: str, vad_filter: bool):
    cache_key = (model_name, device, vad_filter)
    cached = _MODEL_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if AutoModel is None:
        raise RuntimeError(
            "本地转写后端 FunASR 不可用：缺少 `funasr` 依赖。"
            "可先运行 `uv pip install 'funasr>=1.2.6' modelscope`。"
        )

    kwargs: dict[str, Any] = {
        "model": model_name,
        "device": device,
        "disable_update": True,
    }
    if vad_filter:
        kwargs["vad_model"] = os.getenv("OPENMY_FUNASR_VAD_MODEL", "fsmn-vad")
    punc_model = os.getenv("OPENMY_FUNASR_PUNC_MODEL", "").strip()
    if punc_model:
        kwargs["punc_model"] = punc_model

    model = AutoModel(**kwargs)
    _MODEL_CACHE[cache_key] = model
    return model


def _normalize_segments(payload: dict[str, Any]) -> list[TranscriptionSegment]:
    segments: list[TranscriptionSegment] = []
    sentence_info = payload.get("sentence_info")
    if isinstance(sentence_info, list) and sentence_info:
        for index, item in enumerate(sentence_info, start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "") or "").strip()
            if not text:
                continue
            segments.append(
                TranscriptionSegment(
                    id=f"seg_{index:04d}",
                    text=text,
                    start=_to_seconds(item.get("start", 0.0)),
                    end=_to_seconds(item.get("end", 0.0)),
                )
            )
        if segments:
            return segments

    timestamps = payload.get("timestamp")
    if isinstance(timestamps, list) and timestamps:
        for index, item in enumerate(timestamps, start=1):
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            text = str(item[2] or "").strip()
            if not text:
                continue
            start = _to_seconds(item[0])
            end = _to_seconds(item[1])
            segments.append(
                TranscriptionSegment(
                    id=f"seg_{index:04d}",
                    text=text,
                    start=start,
                    end=end,
                    words=[TranscriptionWord(text=text, start=start, end=end)],
                )
            )

    if segments:
        return segments

    text = str(payload.get("text", "") or "").strip()
    return [TranscriptionSegment(id="seg_0001", text=text)] if text else []


class FunASRSTTProvider(SpeechToTextProvider):
    name = "funasr"
    requires_api_key = False

    def transcribe(
        self,
        audio_path: Path,
        *,
        vocab_terms: str = "",
        timeout_seconds: int,
        vad_filter: bool = False,
        word_timestamps: bool = False,
    ) -> TranscriptionResult:
        del timeout_seconds  # 本地推理当前不走外部超时控制

        device = os.getenv("OPENMY_STT_DEVICE", "cpu") or "cpu"
        model = _get_model(self.model, device, vad_filter)
        kwargs: dict[str, Any] = {
            "input": str(audio_path),
            "batch_size_s": int(os.getenv("OPENMY_FUNASR_BATCH_SIZE_S", "300")),
        }
        if vocab_terms:
            kwargs["hotword"] = vocab_terms
        if word_timestamps:
            kwargs["sentence_timestamp"] = True

        raw_result = model.generate(**kwargs)
        if isinstance(raw_result, list) and raw_result:
            payload = raw_result[0] if isinstance(raw_result[0], dict) else {}
        elif isinstance(raw_result, dict):
            payload = raw_result
        else:
            payload = {}

        text = str(payload.get("text", "") or "").strip()
        if not text:
            raise RuntimeError(f"FunASR 没有返回转写内容: {audio_path.name}")

        segments = _normalize_segments(payload)
        duration = max((segment.end for segment in segments), default=0.0)

        return TranscriptionResult(
            text=text,
            language="zh",
            duration_seconds=duration,
            segments=segments,
            provider_metadata={
                "provider": self.name,
                "model": self.model,
                "device": device,
                "vad_filter": vad_filter,
                "word_timestamps": word_timestamps,
                "native_timestamps": bool(payload.get("sentence_info") or payload.get("timestamp")),
            },
        )
