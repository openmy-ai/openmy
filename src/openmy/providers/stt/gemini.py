from __future__ import annotations

import time
from pathlib import Path

from openmy.providers.base import (
    SpeechToTextProvider,
    TranscriptionResult,
    TranscriptionSegment,
)

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
            raise RuntimeError("Gemini SDK 不可用：缺少 google-genai")
        if not self.api_key:
            raise RuntimeError("缺少 Gemini API key")

        client = genai.Client(api_key=self.api_key)
        uploaded = client.files.upload(file=audio_path)

        deadline = time.time() + timeout_seconds
        while uploaded.state == "PROCESSING":
            if time.time() > deadline:
                raise TimeoutError(f"音频文件处理超时 ({timeout_seconds}s): {audio_path.name}")
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)

        if uploaded.state == "FAILED":
            raise RuntimeError(f"音频文件处理失败: {audio_path.name}")

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
            raise RuntimeError(f"Gemini API 没有返回转写内容: {audio_path.name}")
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
