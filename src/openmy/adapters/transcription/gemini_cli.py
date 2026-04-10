#!/usr/bin/env python3
"""Gemini STT 兼容壳。

旧模块路径继续保留，内部已转调 providers 层。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from openmy.config import GEMINI_MODEL, TRANSCRIBE_TIMEOUT, get_stt_api_key, get_stt_model
from openmy.providers.registry import ProviderRegistry
from openmy.providers.stt.gemini import build_prompt as build_gemini_stt_prompt


def load_vocab_terms(vocab_file: Path) -> str:
    if not vocab_file.exists():
        return ""
    terms: list[str] = []
    for raw_line in vocab_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line.split("|", 1)[0].strip())
    return "、".join(t for t in terms if t)


def build_prompt(vocab_terms: str) -> str:
    return build_gemini_stt_prompt(vocab_terms)


def transcribe_audio(
    audio_path: Path,
    api_key: str,
    model: str = GEMINI_MODEL,
    vocab_terms: str = "",
    timeout_seconds: int = TRANSCRIBE_TIMEOUT,
) -> str:
    """向后兼容旧函数签名，内部走 provider registry。"""
    provider = ProviderRegistry.from_env().get_stt_provider(model=model, api_key=api_key)
    return provider.transcribe(
        audio_path,
        vocab_terms=vocab_terms,
        timeout_seconds=timeout_seconds,
    )


# ---- 向后兼容旧接口 ----

def run_gemini_cli(
    audio_path: Path,
    model: str,
    vocab_terms: str,
    timeout_seconds: int,
    gemini_home: Path | None = None,
) -> str:
    """向后兼容旧接口。内部已改用 SDK。"""
    api_key = get_stt_api_key()
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY 环境变量")
    return transcribe_audio(
        audio_path=audio_path,
        api_key=api_key,
        model=model,
        vocab_terms=vocab_terms,
        timeout_seconds=timeout_seconds,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Use the configured STT provider to transcribe a local audio file.")
    parser.add_argument("audio_path", help="Local audio file path.")
    parser.add_argument("--model", default=get_stt_model() or GEMINI_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=TRANSCRIBE_TIMEOUT)
    parser.add_argument("--vocab-file", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audio_path = Path(args.audio_path).expanduser().resolve()
    if not audio_path.is_file():
        print(f"音频文件不存在: {audio_path}", file=sys.stderr)
        return 1

    api_key = get_stt_api_key()
    if not api_key:
        print("❌ 缺少 GEMINI_API_KEY 环境变量", file=sys.stderr)
        return 1

    vocab_terms = load_vocab_terms(Path(args.vocab_file).expanduser()) if args.vocab_file else ""

    try:
        transcript = transcribe_audio(
            audio_path=audio_path,
            api_key=api_key,
            model=args.model,
            vocab_terms=vocab_terms,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
