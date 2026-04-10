from __future__ import annotations

from pathlib import Path
from typing import Any


class SpeechToTextProvider:
    name = "unknown"

    def __init__(self, *, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def transcribe(
        self,
        audio_path: Path,
        *,
        vocab_terms: str = "",
        timeout_seconds: int,
    ) -> str:
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
