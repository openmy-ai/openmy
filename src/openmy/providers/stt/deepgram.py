from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from urllib import error, parse, request

from openmy.providers.base import SpeechToTextProvider, TranscriptionResult, TranscriptionSegment

API_URL = "https://api.deepgram.com/v1/listen"


class DeepgramSTTProvider(SpeechToTextProvider):
    name = "deepgram"

    def transcribe(
        self,
        audio_path: Path,
        *,
        vocab_terms: str = "",
        timeout_seconds: int,
        vad_filter: bool = False,
        word_timestamps: bool = False,
    ) -> TranscriptionResult:
        del vocab_terms, vad_filter, word_timestamps
        if not self.api_key:
            raise RuntimeError("Missing DEEPGRAM_API_KEY.")

        query = parse.urlencode({"model": self.model, "language": "zh"})
        req = request.Request(
            f"{API_URL}?{query}",
            data=audio_path.read_bytes(),
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - network path
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Deepgram transcription failed: {detail or exc.reason}") from exc
        except error.URLError as exc:  # pragma: no cover - network path
            raise RuntimeError(f"Deepgram request failed: {exc.reason}") from exc

        channel = ((payload.get("results") or {}).get("channels") or [{}])[0]
        alternative = (channel.get("alternatives") or [{}])[0]
        text = str(alternative.get("transcript", "") or "").strip()
        if not text:
            raise RuntimeError(f"Deepgram returned no transcript: {audio_path.name}")

        return TranscriptionResult(
            text=text,
            language=str((payload.get("results") or {}).get("language", "") or ""),
            duration_seconds=0.0,
            segments=[TranscriptionSegment(id="seg_0001", text=text)],
            provider_metadata={"provider": self.name, "model": self.model},
        )
