from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TranscriptionWord:
    text: str = ""
    start: float = 0.0
    end: float = 0.0
    probability: float = 0.0
    speaker: str = ""


@dataclass
class TranscriptionSegment:
    id: str = ""
    text: str = ""
    start: float = 0.0
    end: float = 0.0
    speaker: str = ""
    words: list[TranscriptionWord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["words"] = [word if isinstance(word, dict) else asdict(word) for word in self.words]
        return payload


@dataclass
class TranscriptionResult:
    text: str = ""
    language: str = ""
    duration_seconds: float = 0.0
    segments: list[TranscriptionSegment] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["segments"] = [
            segment if isinstance(segment, dict) else segment.to_dict()
            for segment in self.segments
        ]
        return payload


class SpeechToTextProvider:
    name = "unknown"
    requires_api_key = True

    def __init__(self, *, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def transcribe(
        self,
        audio_path: Path,
        *,
        vocab_terms: str = "",
        timeout_seconds: int,
        vad_filter: bool = False,
        word_timestamps: bool = False,
    ) -> TranscriptionResult:
        raise NotImplementedError


class TextGenerationProvider:
    name = "unknown"

    def __init__(self, *, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate_text(
        self,
        *,
        task: str,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        thinking_level: str | None = None,
    ) -> str:
        raise NotImplementedError

    def generate_json(
        self,
        *,
        task: str,
        prompt: str,
        schema: dict[str, Any],
        model: str | None = None,
        temperature: float | None = None,
        thinking_level: str | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError
