from __future__ import annotations

import json
import mimetypes
import uuid
from pathlib import Path
from urllib import error, request

from openmy.providers.base import SpeechToTextProvider, TranscriptionResult, TranscriptionSegment
from openmy.utils.errors import FriendlyCliError, doc_url

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
            raise FriendlyCliError(
                "缺少 Groq 的 API key（访问口令）。",
                code="missing_groq_key",
                fix='先把 `GROQ_API_KEY` 写进项目的 `.env（环境文件）`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="Missing Groq API key.",
                fix_en="Add GROQ_API_KEY to the project .env file, then retry.",
            )

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
            raise FriendlyCliError(
                f"Groq 云端转写失败：{detail or exc.reason}",
                code="groq_http_error",
                fix="先检查网络，再确认 key、模型名和配额都正常。",
                doc_url=doc_url("语音转写"),
                message_en=f"Groq transcription failed: {detail or exc.reason}",
                fix_en="Check your network connection, API key, model name, and quota, then retry.",
            ) from exc
        except error.URLError as exc:  # pragma: no cover - network path
            raise FriendlyCliError(
                f"Groq 请求没发出去：{exc.reason}",
                code="groq_network_error",
                fix="先确认这台机器能连外网，再重试。",
                doc_url=doc_url("语音转写"),
                message_en=f"Groq request failed: {exc.reason}",
                fix_en="Confirm this machine can reach the internet, then retry.",
            ) from exc

        text = str(payload.get("text", "") or "").strip()
        if not text:
            raise FriendlyCliError(
                f"Groq 没有返回这段音频的转写结果：{audio_path.name}",
                code="groq_empty_transcript",
                fix="先换一段更短、更清晰的音频试一次。",
                doc_url=doc_url("语音转写"),
                message_en=f"Groq returned no transcript for {audio_path.name}.",
                fix_en="Try a shorter and clearer audio file, then retry.",
            )

        return TranscriptionResult(
            text=text,
            language=str(payload.get("language", "") or ""),
            duration_seconds=0.0,
            segments=[TranscriptionSegment(id="seg_0001", text=text)],
            provider_metadata={"provider": self.name, "model": self.model},
        )
