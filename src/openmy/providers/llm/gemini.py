from __future__ import annotations

import json
import re
from typing import Any

from openmy.providers.base import TextGenerationProvider

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
            raise RuntimeError("Gemini SDK 不可用：缺少 google-genai")
        if not self.api_key:
            raise RuntimeError("缺少 Gemini API key")
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
        text = response.text.strip() if response.text else ""
        if not text:
            raise RuntimeError(f"Gemini 没有返回 {task} 文本结果")
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
            raise RuntimeError(f"Gemini 没有返回 {task} JSON 结果")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemini 返回的 {task} JSON 无法解析: {text[:200]}") from exc
