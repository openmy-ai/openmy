from __future__ import annotations

import time
from pathlib import Path

from openmy.providers.base import (
    SpeechToTextProvider,
    TranscriptionResult,
    TranscriptionSegment,
)
from openmy.utils.errors import FriendlyCliError, doc_url

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - exercised in environments without sdk
    class _GenAIStub:
        Client = None

    genai = _GenAIStub()
    types = None


def build_prompt(vocab_terms: str) -> str:
    sections = [
        "请转写这段音频文件。",
        "",
        "要求：",
        "1. 完整逐字转写为中文文字。",
        "2. 不要总结、省略、润色、改写，也不要补充解释。",
        "3. 如果有背景音乐，只忽略音乐本身，不要转歌词；只保留人声口述。",
        '4. 保留原话里的称呼、关系词、语气词和代词，不要擅自把"你"替换成具体身份。',
        "5. 如果说话对象无法从音频里明确判断，就保留原样，不要脑补。",
        "6. 直接输出转写正文，不要加前缀，不要写说明。",
        "7. 如果某一段听不清或无法辨认，输出 [无法识别]，绝对不要自己编造内容填充。",
        "8. 如果整段音频都是静音或噪音、没有人声，只输出 [无人声]，不要输出任何其他文字。",
        "9. 只转写音频中实际存在的人声。不要生成音频中不存在的内容。这是最重要的规则。",
    ]
    if vocab_terms:
        sections.extend(["", "常见专有名词：", vocab_terms])
    return "\n".join(sections).strip()


class GeminiSTTProvider(SpeechToTextProvider):
    name = "gemini"

    def transcribe(
        self,
        audio_path: Path,
        *,
        vocab_terms: str = "",
        timeout_seconds: int,
        vad_filter: bool = False,
        word_timestamps: bool = False,
    ) -> TranscriptionResult:
        if getattr(genai, "Client", None) is None:
            raise FriendlyCliError(
                "Gemini 依赖没装好，当前不能走这条云端转写路线。",
                code="gemini_sdk_missing",
                fix='先运行 `pip install google-genai`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="Gemini SDK is unavailable.",
                fix_en="Run pip install google-genai, then retry.",
            )
        if not self.api_key:
            raise FriendlyCliError(
                "缺少 Gemini 的 API key（访问口令）。",
                code="missing_gemini_key",
                fix='先把 `GEMINI_API_KEY` 写进项目的 `.env（环境文件）`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="Missing Gemini API key.",
                fix_en="Add GEMINI_API_KEY to the project .env file, then retry.",
            )

        client = genai.Client(api_key=self.api_key)
        uploaded = client.files.upload(file=audio_path)

        deadline = time.time() + timeout_seconds
        while uploaded.state == "PROCESSING":
            if time.time() > deadline:
                raise FriendlyCliError(
                    f"Gemini 处理音频超时了：{audio_path.name}",
                    code="gemini_audio_timeout",
                    fix="先换一段更短的音频，或者稍后再试。",
                    doc_url=doc_url("语音转写"),
                    message_en=f"Gemini audio processing timed out for {audio_path.name}.",
                    fix_en="Try a shorter audio file or retry later.",
                )
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)

        if uploaded.state == "FAILED":
            raise FriendlyCliError(
                f"Gemini 没能处理这段音频：{audio_path.name}",
                code="gemini_audio_failed",
                fix="先检查音频格式，再换一段更短的文件重试。",
                doc_url=doc_url("语音转写"),
                message_en=f"Gemini failed to process {audio_path.name}.",
                fix_en="Check the audio format, then retry with a shorter file.",
            )

        response = client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type),
                        types.Part.from_text(text=build_prompt(vocab_terms)),
                    ],
                ),
            ],
        )
        text = response.text.strip() if response.text else ""
        if not text:
            raise FriendlyCliError(
                f"Gemini 没有返回这段音频的转写结果：{audio_path.name}",
                code="gemini_empty_transcript",
                fix="先确认音频里真的有人声，再重试。",
                doc_url=doc_url("语音转写"),
                message_en=f"Gemini returned no transcript for {audio_path.name}.",
                fix_en="Make sure the audio contains speech, then retry.",
            )
        return TranscriptionResult(
            text=text,
            language="zh",
            duration_seconds=0.0,
            segments=[
                TranscriptionSegment(
                    id="seg_0001",
                    text=text,
                )
            ],
            provider_metadata={
                "provider": self.name,
                "model": self.model,
                "vad_filter": vad_filter,
                "word_timestamps": word_timestamps,
            },
        )
