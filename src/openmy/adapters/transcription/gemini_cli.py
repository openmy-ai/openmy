"""Gemini STT backward-compatibility shim.

The only public symbol still imported by other modules is
``load_vocab_terms``, which now lives in ``openmy.utils.io``.
This module re-exports it so that existing callers (including tests)
continue to work without changes.
"""
from __future__ import annotations

from openmy.utils.io import load_vocab_terms  # re-export
from openmy.providers.stt.gemini import build_prompt as build_gemini_stt_prompt


def build_prompt(vocab_terms: str) -> str:
    return build_gemini_stt_prompt(vocab_terms)


__all__ = ["load_vocab_terms", "build_prompt"]
