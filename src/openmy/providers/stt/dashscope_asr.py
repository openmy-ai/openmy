from __future__ import annotations

from pathlib import Path

from openmy.providers.base import SpeechToTextProvider, TranscriptionResult, TranscriptionSegment

try:
    import dashscope
except ImportError:  # pragma: no cover - optional dependency
    dashscope = None


class DashScopeASRProvider(SpeechToTextProvider):
    name = "dashscope"

    def transcribe(
        self,
        audio_path: Path,
        *,
        vocab_terms: str = "",
        timeout_seconds: int,
        vad_filter: bool = False,
        word_timestamps: bool = False,
    ) -> TranscriptionResult:
        del vocab_terms, vad_filter, word_timestamps, timeout_seconds
        if not self.api_key:
            raise RuntimeError("Missing DASHSCOPE_API_KEY.")
        if dashscope is None:
            raise RuntimeError("DashScope SDK unavailable. Install dashscope to use this provider.")

        dashscope.api_key = self.api_key
        recognizer = getattr(getattr(dashscope, "audio", None), "asr", None)
        recognizer_cls = getattr(recognizer, "Recognizer", None)
        if recognizer_cls is None:
            raise RuntimeError("DashScope ASR SDK interface unavailable.")

        client = recognizer_cls(model=self.model)
        result = client.call(str(audio_path))
        output = getattr(result, "output", None) or {}
        text = str(output.get("text", "") or "").strip()
        if not text:
            raise RuntimeError(f"DashScope returned no transcript: {audio_path.name}")

        return TranscriptionResult(
            text=text,
            language="zh",
            duration_seconds=0.0,
            segments=[TranscriptionSegment(id="seg_0001", text=text)],
            provider_metadata={"provider": self.name, "model": self.model},
        )
