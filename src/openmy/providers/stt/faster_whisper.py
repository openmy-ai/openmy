from __future__ import annotations

import os
from pathlib import Path

from openmy.providers.base import (
    SpeechToTextProvider,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)

try:
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover - exercised in environments without optional dependency
    WhisperModel = None


_MODEL_CACHE: dict[tuple[str, str, str], object] = {}


def _build_initial_prompt(vocab_terms: str) -> str:
    if not vocab_terms:
        return ""
    return f"专有名词：{vocab_terms}"


def _get_model(model_name: str, device: str, compute_type: str):
    cache_key = (model_name, device, compute_type)
    cached = _MODEL_CACHE.get(cache_key)
    if cached is not None:
        return cached
        if WhisperModel is None:
            raise RuntimeError(
                "本地转写后端 faster-whisper 不可用：缺少 `faster-whisper` 依赖。"
                "可先运行 `pip install \"openmy[local]\"`。"
            )
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    _MODEL_CACHE[cache_key] = model
    return model


class FasterWhisperSTTProvider(SpeechToTextProvider):
    name = "faster-whisper"
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

        device = os.getenv("OPENMY_STT_DEVICE", "auto") or "auto"
        compute_type = os.getenv("OPENMY_STT_COMPUTE_TYPE", "int8") or "int8"
        beam_size = int(os.getenv("OPENMY_STT_BEAM_SIZE", "5") or "5")
        language = os.getenv("OPENMY_STT_LANGUAGE", "zh") or "zh"
        model = _get_model(self.model, device, compute_type)

        segments_iter, info = model.transcribe(
            str(audio_path),
            language=language or None,
            beam_size=beam_size,
            vad_filter=vad_filter,
            word_timestamps=word_timestamps,
            initial_prompt=_build_initial_prompt(vocab_terms),
        )

        segments: list[TranscriptionSegment] = []
        text_parts: list[str] = []
        for index, item in enumerate(segments_iter, start=1):
            text = str(getattr(item, "text", "") or "").strip()
            if not text:
                continue
            words: list[TranscriptionWord] = []
            for word in getattr(item, "words", []) or []:
                word_text = str(getattr(word, "word", "") or "").strip()
                if not word_text:
                    continue
                words.append(
                    TranscriptionWord(
                        text=word_text,
                        start=float(getattr(word, "start", 0.0) or 0.0),
                        end=float(getattr(word, "end", 0.0) or 0.0),
                        probability=float(getattr(word, "probability", 0.0) or 0.0),
                    )
                )
            segments.append(
                TranscriptionSegment(
                    id=f"seg_{index:04d}",
                    text=text,
                    start=float(getattr(item, "start", 0.0) or 0.0),
                    end=float(getattr(item, "end", 0.0) or 0.0),
                    words=words,
                )
            )
            text_parts.append(text)

        transcript_text = "\n".join(text_parts).strip()
        if not transcript_text:
            raise RuntimeError(f"faster-whisper 没有返回转写内容: {audio_path.name}")

        return TranscriptionResult(
            text=transcript_text,
            language=str(getattr(info, "language", language) or language),
            duration_seconds=float(getattr(info, "duration", 0.0) or 0.0),
            segments=segments,
            provider_metadata={
                "provider": self.name,
                "model": self.model,
                "device": device,
                "compute_type": compute_type,
                "beam_size": beam_size,
                "vad_filter": vad_filter,
                "word_timestamps": word_timestamps,
            },
        )
