#!/usr/bin/env python3
"""一次性绕行脚本：长段被 Gemini 服务端持续超时，切短段逐个转写后拼接。

产物写到 data/eval/attribution-v1/{dialect,ktv}.md，头部注明分段拼接。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from openmy.adapters.transcription.gemini_cli import load_vocab_terms  # noqa: E402
from openmy.config import GEMINI_MODEL, get_stt_api_key  # noqa: E402
from openmy.providers.stt.gemini import GeminiSTTProvider  # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from transcribe_eval import load_project_env  # noqa: E402

from openmy.utils.paths import PROJECT_ENV_PATH  # noqa: E402

SEGMENTS = {
    "dialect": {"label": "方言段", "time_label": "19:03", "audio": "data/2026-06-05/stt_chunks/audio_003_sub_0000.mp3"},
    "ktv": {"label": "KTV 段", "time_label": "21:03", "audio": "data/2026-06-05/stt_chunks/audio_007_sub_0000.mp3"},
}
CHUNK_DIR = PROJECT_ROOT / "data" / "eval" / "_chunks"
OUT_DIR = PROJECT_ROOT / "data" / "eval" / "attribution-v1"
PROMPT_FILE = PROJECT_ROOT / "data" / "eval" / "prompts" / "attribution_v1.txt"


def main() -> None:
    load_project_env(PROJECT_ENV_PATH)
    api_key = get_stt_api_key("gemini")
    if not api_key:
        raise SystemExit("缺少 GEMINI_API_KEY")
    instruction = PROMPT_FILE.read_text(encoding="utf-8").strip()
    vocab = load_vocab_terms(PROJECT_ROOT / "src" / "openmy" / "resources" / "vocab.txt")
    provider = GeminiSTTProvider(api_key=api_key, model=GEMINI_MODEL)

    for seg_id, meta in SEGMENTS.items():
        out_path = OUT_DIR / f"{seg_id}.md"
        if out_path.exists():
            print(f"[skip] {seg_id} 已有产物")
            continue
        chunks = sorted(CHUNK_DIR.glob(f"{seg_id}_*.mp3"))
        if not chunks:
            raise SystemExit(f"找不到 {seg_id} 的切块")
        parts: list[str] = []
        for chunk in chunks:
            print(f"[run ] {chunk.name}")
            result = provider.transcribe(
                chunk, vocab_terms=vocab, timeout_seconds=240, system_instruction=instruction,
            )
            parts.append(result.text.strip())
            print(f"[done] {chunk.name}")
        body = "\n".join(parts)
        out_path.write_text(
            f"# {meta['label']}（{meta['time_label']}）\n\n"
            f"- run: attribution-v1\n- segment: {seg_id}\n- audio: {meta['audio']}\n"
            f"- note: 长段服务端持续超时，按 210 秒切 {len(chunks)} 块转写拼接（上下文少于整段，计分时注明）\n\n"
            f"## 转写正文\n\n{body}\n",
            encoding="utf-8",
        )
        print(f"[done] {seg_id} → {out_path}")


if __name__ == "__main__":
    main()
