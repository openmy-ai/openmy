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


SYSTEM_INSTRUCTION = (
    "你是中文语音转写引擎。\n\n"
    "## 优先级（从高到低）\n"
    "1. 安全：不编造音频中不存在的内容\n"
    "2. 过滤：不转写非人声口述的背景声（伴奏、铃声、设备提示音）\n"
    "3. 完整：人声口述逐字转写，不省略不润色\n\n"
    "## DO\n"
    "- 逐字转写所有人声口述，保留语气词、口头禅、重复\n"
    "- 用户本人的演唱（包括 KTV）视为人声口述，正常转写\n"
    "- 听不清的词输出 [无法识别]，不猜测\n"
    "- 整段无人声只输出 [无人声]\n"
    "- 方言词汇含义明确时用对应的普通话词汇转写，不确定时标 [无法识别]\n"
    "- 外语短语保留原文\n\n"
    "## DO NOT\n"
    "- 不转写背景伴奏和音乐旋律\n"
    "- 如果能明确判断某段语音来自外放设备而非说话人，不转写该段；无法判断时按人声转写\n"
    "- 不总结、省略、润色、改写、补充解释\n"
    "- 不替换原话中的称呼、代词、关系词\n"
    "- 不添加说话人标注\n"
    "- 只允许使用 [无法识别] 和 [无人声] 两个标签，不自创其他方括号标记\n"
    "- 不加前缀、标题、说明文字"
)


def build_prompt(vocab_terms: str) -> str:
    sections = ["转写以下音频中的人声口述。直接输出转写正文。"]
    if vocab_terms:
        sections.append(f"\n常见专有名词（遇到相似发音优先匹配）：{vocab_terms}")
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
                fix='先运行 `pip install "openmy[cloud]"`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="Gemini SDK is unavailable.",
                fix_en='Run pip install "openmy[cloud]", then retry.',
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
                        types.Part.from_text(text=build_prompt(vocab_terms)),
                        types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type),
                    ],
                ),
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.0,
            ),
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
