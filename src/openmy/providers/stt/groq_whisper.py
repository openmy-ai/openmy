from __future__ import annotations

import json
import mimetypes
import uuid
from pathlib import Path
from urllib import error, request

from openmy.providers.base import SpeechToTextProvider, TranscriptionResult, TranscriptionSegment

API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def _build_multipart_body(audio_path: Path, *, model: str) -> tuple[bytes, str]:
    boundary = f"----OpenMyBoundary{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    file_bytes = audio_path.read_bytes()
    chunks: list[bytes] = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="model"\r\n\r\n',
        model.encode("utf-8"),
        b"\r\n",
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'.encode("utf-8"),
        f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), boundary


class GroqWhisperSTTProvider(SpeechToTextProvider):
    name = "groq"

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
            raise RuntimeError("Missing GROQ_API_KEY.")

        body, boundary = _build_multipart_body(audio_path, model=self.model)
        req = request.Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - network path
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Groq transcription failed: {detail or exc.reason}") from exc
        except error.URLError as exc:  # pragma: no cover - network path
            raise RuntimeError(f"Groq request failed: {exc.reason}") from exc

        text = str(payload.get("text", "") or "").strip()
        if not text:
            raise RuntimeError(f"Groq returned no transcript: {audio_path.name}")

        return TranscriptionResult(
            text=text,
            language=str(payload.get("language", "") or ""),
            duration_seconds=0.0,
            segments=[TranscriptionSegment(id="seg_0001", text=text)],
            provider_metadata={"provider": self.name, "model": self.model},
        )
