from __future__ import annotations

from openmy.config import (
    get_llm_api_key,
    get_llm_model,
    get_llm_provider_name,
    get_stage_llm_model,
    get_stt_api_key,
    get_stt_model,
    get_stt_provider_name,
)
from openmy.providers.llm.gemini import GeminiLLMProvider
from openmy.providers.stt.faster_whisper import FasterWhisperSTTProvider
from openmy.providers.stt.gemini import GeminiSTTProvider


STT_PROVIDERS = {
    "gemini": GeminiSTTProvider,
    "faster-whisper": FasterWhisperSTTProvider,
}

LLM_PROVIDERS = {
    "gemini": GeminiLLMProvider,
}


class ProviderRegistry:
    def __init__(self, *, stt_provider_name: str, llm_provider_name: str):
        self.stt_provider_name = stt_provider_name
        self.llm_provider_name = llm_provider_name

    @classmethod
    def from_env(cls) -> "ProviderRegistry":
        return cls(
            stt_provider_name=get_stt_provider_name(),
            llm_provider_name=get_llm_provider_name(),
        )

    def get_stt_provider(
        self,
        *,
        provider_name: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ):
        final_provider_name = (provider_name or self.stt_provider_name).lower()
        provider_cls = STT_PROVIDERS.get(final_provider_name)
        if provider_cls is None:
            raise ValueError(f"未知 STT provider: {final_provider_name}")
        return provider_cls(
            api_key=api_key if api_key is not None else get_stt_api_key(final_provider_name),
            model=model or get_stt_model(final_provider_name),
        )

    def get_llm_provider(
        self,
        *,
        stage: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ):
        provider_cls = LLM_PROVIDERS.get(self.llm_provider_name)
        if provider_cls is None:
            raise ValueError(f"未知 LLM provider: {self.llm_provider_name}")
        return provider_cls(
            api_key=api_key if api_key is not None else get_llm_api_key(stage),
            model=model or (get_stage_llm_model(stage) if stage else get_llm_model()),
        )
