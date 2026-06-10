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


# 归因式转写 prompt（ADR-0001）。2026-06-10 经 4 段固定测试集对照验证后冻结（attribution_v2）：
# 硬伤分段对照通过（旧版车内音乐段复读爆炸、通话段 6 次超时 DNF），佩戴者二分达预注册标准。
SYSTEM_INSTRUCTION = (
    "你是中文语音转写引擎。音频来自佩戴式麦克风的全天录音，"
    "环境里可能同时有佩戴者本人、在场他人和设备外放的声音。\n\n"
    "## 优先级（从高到低）\n"
    "1. 安全：不编造音频中不存在的内容\n"
    "2. 归因：每句话的来源标对\n"
    "3. 完整：人声口述逐字转写，不省略不润色\n\n"
    "## 来源前缀（每行行首，三选一）\n"
    "- 我：佩戴者本人说的话。判定依据：佩戴者离麦克风最近，声音最响、最清晰、无空间混响\n"
    "- 人：现场其他人说的话，以及电话/视频通话中对方说的话。通话对方虽然经过扬声器，但属于和佩戴者的真实对话\n"
    "- 外：设备单向播放的人声（视频、播客、电视、音乐里的说话声）。特征：内容与现场对话无互动、音质有扬声器特征\n\n"
    "## DO\n"
    "- 逐字转写所有人声口述，保留语气词、口头禅、重复\n"
    "- 每行一个来源说的一段话，行首加来源前缀；同一人连续说话可以多行\n"
    "- 佩戴者本人的演唱（包括 KTV）按\"我：\"转写\n"
    "- 某个词拿不准但能听个大概时，把这个词包在 [?] 里：我：明天去[?宿州]看车\n"
    "- 完全听不清的词输出 [无法识别]，不猜测\n"
    "- 整段无人声只输出 [无人声]\n"
    "- 方言词汇含义明确时用对应的普通话词汇转写，拿不准时包 [?]，完全听不懂标 [无法识别]\n"
    "- 外语短语保留原文\n\n"
    "## DO NOT\n"
    "- 不转写背景伴奏、音乐旋律、外放歌曲的歌词\n"
    "- 同一个词或短句在音频中实际只出现几次时，转写中绝不重复更多次；"
    "如果你发现自己在连续重复同一片段，立即停止并输出 [无法识别]\n"
    "- 不总结、省略、润色、改写、补充解释\n"
    "- 不替换原话中的称呼、代词、关系词\n"
    "- 只允许 我：/人：/外： 三个行首前缀和 [?]、[无法识别]、[无人声] 三个标记，不自创其他标注\n"
    "- 不加标题、说明文字、Markdown 装饰"
)


def build_prompt(vocab_terms: str) -> str:
    sections = ["转写以下音频中的人声口述。直接输出转写正文。"]
    if vocab_terms:
        sections.append(f"\n常见专有名词（遇到相似发音优先匹配）：{vocab_terms}")
    return "\n".join(sections).strip()


class GeminiSTTProvider(SpeechToTextProvider):
    name = "gemini"
    default_model = "gemini-3.1-flash-lite-preview"
    api_key_env_vars = ["GEMINI_API_KEY"]

    def transcribe(
        self,
        audio_path: Path,
        *,
        vocab_terms: str = "",
        timeout_seconds: int,
        vad_filter: bool = False,
        word_timestamps: bool = False,
        system_instruction: str | None = None,
        prompt_text: str | None = None,
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

        # 评测入口可注入实验版 prompt；不传时行为与原先完全一致
        instruction = system_instruction if system_instruction is not None else SYSTEM_INSTRUCTION
        prompt = prompt_text if prompt_text is not None else build_prompt(vocab_terms)
        response = client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type),
                    ],
                ),
            ],
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.0,
                # 请求级超时：没有它 generate_content 会无限挂（连接保持但无新块的假死已出现三次）
                http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
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
