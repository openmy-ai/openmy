from __future__ import annotations

import json
import re
from typing import Any

from openmy.providers.base import TextGenerationProvider
from openmy.utils.errors import FriendlyCliError, doc_url

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - exercised in environments without sdk
    class _GenAIStub:
        Client = None

    genai = _GenAIStub()
    types = None


def _strip_code_fences(text: str) -> str:
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```[\w-]*\n?", "", text)
    return re.sub(r"\n?```$", "", text).strip()


class GeminiLLMProvider(TextGenerationProvider):
    name = "gemini"

    def _client(self):
        if getattr(genai, "Client", None) is None:
            raise FriendlyCliError(
                "Gemini 依赖没装好，当前不能走这条整理路线。",
                code="gemini_llm_sdk_missing",
                fix='先运行 `pip install google-genai`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="Gemini SDK is unavailable.",
                fix_en="Run pip install google-genai, then retry.",
            )
        if not self.api_key:
            raise FriendlyCliError(
                "缺少 Gemini 的 API key（访问口令）。",
                code="missing_gemini_llm_key",
                fix='先把 `GEMINI_API_KEY` 写进项目的 `.env（环境文件）`，再重试。',
                doc_url=doc_url("语音转写"),
                message_en="Missing Gemini API key.",
                fix_en="Add GEMINI_API_KEY to the project .env file, then retry.",
            )
        return genai.Client(api_key=self.api_key)

    def generate_text(
        self,
        *,
        task: str,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        thinking_level: str | None = None,
    ) -> str:
        client = self._client()
        kwargs = {
            "model": model or self.model,
            "contents": prompt,
        }
        config: dict[str, Any] = {}
        if temperature is not None:
            config["temperature"] = temperature
        if thinking_level:
            config["thinking_config"] = {"thinking_level": thinking_level}
        if config:
            kwargs["config"] = config
        response = client.models.generate_content(**kwargs)
        # Detect safety filter refusal before checking text content.
        _blocked = False
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            finish = getattr(candidate, "finish_reason", None)
            if finish and str(finish).upper() in ("SAFETY", "BLOCKED", "RECITATION"):
                _blocked = True
        if _blocked:
            raise FriendlyCliError(
                f"Gemini 因安全过滤器跳过了 {task}（内容可能触发了审核规则）。",
                code="gemini_safety_refusal",
                fix="这段内容被自动跳过，不影响其他场景的处理。",
                doc_url=doc_url("语音转写"),
                message_en=f"Gemini refused {task} due to safety filters.",
                fix_en="This segment was skipped. Other segments are unaffected.",
            )
        text = response.text.strip() if response.text else ""
        if not text:
            raise FriendlyCliError(
                f"Gemini 没有返回 {task} 的文本结果。",
                code="gemini_text_empty",
                fix="先稍后再试；如果一直复现，就换一个模型。",
                doc_url=doc_url("语音转写"),
                message_en=f"Gemini returned no text for {task}.",
                fix_en="Retry later. If it keeps failing, switch to another model.",
            )
        return text

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
        client = self._client()
        if types is not None:
            config_kwargs: dict[str, Any] = {
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            }
            if temperature is not None:
                config_kwargs["temperature"] = temperature
            if thinking_level:
                config_kwargs["thinking_config"] = {"thinking_level": thinking_level}
            if timeout_seconds:
                config_kwargs["http_options"] = types.HttpOptions(timeout=timeout_seconds * 1000)
            config = types.GenerateContentConfig(**config_kwargs)
        else:  # pragma: no cover - defensive fallback
            config = {
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            }
            if temperature is not None:
                config["temperature"] = temperature
            if thinking_level:
                config["thinking_config"] = {"thinking_level": thinking_level}

        response = client.models.generate_content(
            model=model or self.model,
            contents=prompt,
            config=config,
        )
        text = _strip_code_fences(response.text.strip() if response.text else "")
        if not text:
            raise FriendlyCliError(
                f"Gemini 没有返回 {task} 的 JSON 结果。",
                code="gemini_json_empty",
                fix="先稍后再试；如果一直复现，就换一个模型。",
                doc_url=doc_url("语音转写"),
                message_en=f"Gemini returned no JSON for {task}.",
                fix_en="Retry later. If it keeps failing, switch to another model.",
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise FriendlyCliError(
                f"Gemini 返回的 {task} 结果不是合法 JSON。",
                code="gemini_json_invalid",
                fix="先重试一次；如果还是不对，就换模型再试。",
                doc_url=doc_url("语音转写"),
                message_en=f"Gemini returned invalid JSON for {task}.",
                fix_en="Retry once. If it still fails, switch to another model.",
            ) from exc
