#!/usr/bin/env python3
"""Gemini API 音频转写模块。

使用 google-genai SDK 的 Files API 上传音频文件并转写。
替代原来的 Gemini CLI subprocess 方案。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

from openmy.config import GEMINI_MODEL, TRANSCRIBE_TIMEOUT


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
    return f"""请转写这段音频文件。

要求：
1. 完整逐字转写为中文文字。
2. 不要总结、省略、润色、改写，也不要补充解释。
3. 如果有背景音乐，只忽略音乐本身，不要转歌词；只保留人声口述。
4. 保留原话里的称呼、关系词、语气词和代词，不要擅自把"你"替换成具体身份。
5. 如果说话对象无法从音频里明确判断，就保留原样，不要脑补。
6. 直接输出转写正文，不要加前缀，不要写说明。

业务背景：
这批语音会进入个人归档系统，里面会有对伴侣、家人、朋友、商家、AI、宠物说话，以及自言自语的任务记录。

常见专有名词：
{vocab_terms}
""".strip()


def transcribe_audio(
    audio_path: Path,
    api_key: str,
    model: str = GEMINI_MODEL,
    vocab_terms: str = "",
    timeout_seconds: int = TRANSCRIBE_TIMEOUT,
) -> str:
    """用 Gemini Files API 上传音频并转写。"""
    client = genai.Client(api_key=api_key)

    # 上传音频文件
    uploaded = client.files.upload(file=audio_path)

    # 等待文件处理完成
    deadline = time.time() + timeout_seconds
    while uploaded.state == "PROCESSING":
        if time.time() > deadline:
            raise TimeoutError(f"音频文件处理超时 ({timeout_seconds}s): {audio_path.name}")
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state == "FAILED":
        raise RuntimeError(f"音频文件处理失败: {audio_path.name}")

    # 转写
    prompt = build_prompt(vocab_terms)
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type),
                    types.Part.from_text(text=prompt),
                ],
            ),
        ],
    )

    text = response.text.strip() if response.text else ""
    if not text:
        raise RuntimeError(f"Gemini API 没有返回转写内容: {audio_path.name}")

    return text


# ---- 向后兼容旧接口 ----

def run_gemini_cli(
    audio_path: Path,
    model: str,
    vocab_terms: str,
    timeout_seconds: int,
    gemini_home: Path | None = None,
) -> str:
    """向后兼容旧接口。内部已改用 SDK。"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
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
    parser = argparse.ArgumentParser(description="Use Gemini API to transcribe a local audio file.")
    parser.add_argument("audio_path", help="Local audio file path.")
    parser.add_argument("--model", default=GEMINI_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=TRANSCRIBE_TIMEOUT)
    parser.add_argument("--vocab-file", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audio_path = Path(args.audio_path).expanduser().resolve()
    if not audio_path.is_file():
        print(f"音频文件不存在: {audio_path}", file=sys.stderr)
        return 1

    api_key = os.environ.get("GEMINI_API_KEY", "")
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
