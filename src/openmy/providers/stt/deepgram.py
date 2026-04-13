from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from urllib import error, parse, request

from openmy.providers.base import SpeechToTextProvider, TranscriptionResult, TranscriptionSegment
from openmy.utils.errors import FriendlyCliError, doc_url

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
            raise FriendlyCliError(
                "缺少 Deepgram 的 API key（访问口令）。",
                code="missing_deepgram_key",
                fix='先把 `DEEPGRAM_API_KEY` 写进项目的 `.env（环境文件）`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="Missing Deepgram API key.",
                fix_en="Add DEEPGRAM_API_KEY to the project .env file, then retry.",
            )

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
            raise FriendlyCliError(
                f"Deepgram 云端转写失败：{detail or exc.reason}",
                code="deepgram_http_error",
                fix="先检查网络，再确认 key、模型名和配额都正常。",
                doc_url=doc_url("语音转写"),
                message_en=f"Deepgram transcription failed: {detail or exc.reason}",
                fix_en="Check your network connection, API key, model name, and quota, then retry.",
            ) from exc
        except error.URLError as exc:  # pragma: no cover - network path
            raise FriendlyCliError(
                f"Deepgram 请求没发出去：{exc.reason}",
                code="deepgram_network_error",
                fix="先确认这台机器能连外网，再重试。",
                doc_url=doc_url("语音转写"),
                message_en=f"Deepgram request failed: {exc.reason}",
                fix_en="Confirm this machine can reach the internet, then retry.",
            ) from exc

        channel = ((payload.get("results") or {}).get("channels") or [{}])[0]
        alternative = (channel.get("alternatives") or [{}])[0]
        text = str(alternative.get("transcript", "") or "").strip()
        if not text:
            raise FriendlyCliError(
                f"Deepgram 没有返回这段音频的转写结果：{audio_path.name}",
                code="deepgram_empty_transcript",
                fix="先换一段更短、更清晰的音频试一次。",
                doc_url=doc_url("语音转写"),
                message_en=f"Deepgram returned no transcript for {audio_path.name}.",
                fix_en="Try a shorter and clearer audio file, then retry.",
            )

        return TranscriptionResult(
            text=text,
            language=str((payload.get("results") or {}).get("language", "") or ""),
            duration_seconds=0.0,
            segments=[TranscriptionSegment(id="seg_0001", text=text)],
            provider_metadata={"provider": self.name, "model": self.model},
        )
