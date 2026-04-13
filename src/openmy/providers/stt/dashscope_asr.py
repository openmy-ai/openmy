from __future__ import annotations

from pathlib import Path

from openmy.providers.base import SpeechToTextProvider, TranscriptionResult, TranscriptionSegment
from openmy.utils.errors import FriendlyCliError, doc_url

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
            raise FriendlyCliError(
                "缺少 DashScope 的 API key（访问口令）。",
                code="missing_dashscope_key",
                fix='先把 `DASHSCOPE_API_KEY` 写进项目的 `.env（环境文件）`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="Missing DashScope API key.",
                fix_en="Add DASHSCOPE_API_KEY to the project .env file, then retry.",
            )
        if dashscope is None:
            raise FriendlyCliError(
                "DashScope 依赖没装好，当前不能用这个转写路线。",
                code="dashscope_sdk_missing",
                fix='先运行 `pip install dashscope`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="DashScope SDK is unavailable.",
                fix_en="Run pip install dashscope, then retry.",
            )

        dashscope.api_key = self.api_key
        recognizer = getattr(getattr(dashscope, "audio", None), "asr", None)
        recognizer_cls = getattr(recognizer, "Recognizer", None)
        if recognizer_cls is None:
            raise FriendlyCliError(
                "DashScope 识别接口当前不可用。",
                code="dashscope_interface_missing",
                fix="先升级 dashscope 依赖，或者先换用别的转写路线。",
                doc_url=doc_url("语音转写"),
                message_en="DashScope ASR SDK interface is unavailable.",
                fix_en="Upgrade the dashscope package or switch to a different speech-to-text route.",
            )

        client = recognizer_cls(model=self.model)
        result = client.call(str(audio_path))
        output = getattr(result, "output", None) or {}
        text = str(output.get("text", "") or "").strip()
        if not text:
            raise FriendlyCliError(
                f"DashScope 没有返回这段音频的转写结果：{audio_path.name}",
                code="dashscope_empty_transcript",
                fix="先换一段更短、更清晰的音频试一次。",
                doc_url=doc_url("语音转写"),
                message_en=f"DashScope returned no transcript for {audio_path.name}.",
                fix_en="Try a shorter and clearer audio file, then retry.",
            )

        return TranscriptionResult(
            text=text,
            language="zh",
            duration_seconds=0.0,
            segments=[TranscriptionSegment(id="seg_0001", text=text)],
            provider_metadata={"provider": self.name, "model": self.model},
        )
