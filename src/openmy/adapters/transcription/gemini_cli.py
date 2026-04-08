#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REQUIRED_GEMINI_HOME_FILES = (
    "oauth_creds.json",
    "google_accounts.json",
    "state.json",
)


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


def build_prompt(audio_name: str, vocab_terms: str) -> str:
    return f"""请转写这段本地音频文件：@{audio_name}

要求：
1. 完整逐字转写为中文文字。
2. 不要总结、省略、润色、改写，也不要补充解释。
3. 如果有背景音乐，只忽略音乐本身，不要转歌词；只保留人声口述。
4. 保留原话里的称呼、关系词、语气词和代词，不要擅自把“你”替换成具体身份。
5. 如果说话对象无法从音频里明确判断，就保留原样，不要脑补。
6. 直接输出转写正文，不要加前缀，不要写说明。

业务背景：
这批语音会进入个人归档系统，里面会有对伴侣、家人、朋友、商家、AI、宠物说话，以及自言自语的任务记录。

常见专有名词：
{vocab_terms}
""".strip()


def prepare_isolated_home(source_home: Path, model: str) -> Path:
    isolated_root = Path(tempfile.mkdtemp(prefix="gemini-cli-home-"))
    isolated_gemini_dir = isolated_root / ".gemini"
    isolated_gemini_dir.mkdir(parents=True, exist_ok=True)

    for name in REQUIRED_GEMINI_HOME_FILES:
        src = source_home / name
        if not src.exists():
            raise FileNotFoundError(f"缺少 Gemini CLI 凭证文件: {src}")
        shutil.copy2(src, isolated_gemini_dir / name)

    settings = {
        "general": {
            "approvalMode": "yolo",
            "enablePromptCompletion": True,
        },
        "security": {
            "auth": {
                "selectedType": "oauth-personal",
            }
        },
        "model": {
            "name": model,
        },
    }
    (isolated_gemini_dir / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return isolated_root


def run_gemini_cli(
    audio_path: Path,
    model: str,
    vocab_terms: str,
    timeout_seconds: int,
    gemini_home: Path,
) -> str:
    isolated_home = prepare_isolated_home(gemini_home, model)
    try:
        env = os.environ.copy()
        env["HOME"] = str(isolated_home)
        env["NO_COLOR"] = "1"
        env.pop("GEMINI_API_KEY", None)

        prompt = build_prompt(audio_path.name, vocab_terms)
        cmd = [
            "gemini",
            "-m",
            model,
            "--output-format",
            "text",
            "--include-directories",
            str(audio_path.parent),
            "-p",
            prompt,
        ]

        proc = subprocess.run(
            cmd,
            cwd=str(audio_path.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    finally:
        shutil.rmtree(isolated_home, ignore_errors=True)

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if proc.returncode != 0:
        raise RuntimeError(
            f"Gemini CLI 返回非零退出码 {proc.returncode}\nSTDERR:\n{stderr[:2000]}"
        )
    if not stdout:
        raise RuntimeError(
            "Gemini CLI 没有返回正文输出\n"
            f"STDERR:\n{stderr[:2000]}"
        )

    return stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Use Gemini CLI to transcribe a local audio file.")
    parser.add_argument("audio_path", help="Local audio file path.")
    parser.add_argument("--model", default="gemini-3-flash-preview")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--vocab-file", default="")
    parser.add_argument("--gemini-home", default=str(Path.home() / ".gemini"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audio_path = Path(args.audio_path).expanduser().resolve()
    if not audio_path.is_file():
        print(f"音频文件不存在: {audio_path}", file=sys.stderr)
        return 1

    gemini_home = Path(args.gemini_home).expanduser().resolve()
    vocab_terms = load_vocab_terms(Path(args.vocab_file).expanduser()) if args.vocab_file else ""

    try:
        transcript = run_gemini_cli(
            audio_path=audio_path,
            model=args.model,
            vocab_terms=vocab_terms,
            timeout_seconds=args.timeout_seconds,
            gemini_home=gemini_home,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
