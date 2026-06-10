#!/usr/bin/env python3
"""转写评测入口：对固定测试集运行任意版本的转写 prompt，产出并排对比产物。

用法：
    python3 scripts/transcribe_eval.py <run_name>                       # 用当前内置 prompt 跑
    python3 scripts/transcribe_eval.py <run_name> --system-instruction-file prompts/v2.txt
    python3 scripts/transcribe_eval.py <run_name> --compare baseline-6b23cd6   # 跑完后与已有 run 并排
    python3 scripts/transcribe_eval.py --compare-only run_a run_b       # 只做并排，不跑转写

产物落 data/eval/<run_name>/：每段一个 <segment_id>.md，并排产物 side_by_side_<a>_vs_<b>.md。
硬伤计数由人/agent 对照原音频完成，本脚本不做自动评分（见 scripts/eval_testset.json 的 scoring）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DEFAULT_MANIFEST = PROJECT_ROOT / "scripts" / "eval_testset.json"
EVAL_ROOT = PROJECT_ROOT / "data" / "eval"


def load_project_env(env_path: Path) -> None:
    """把项目 .env 中尚未出现在环境里的 KEY=VALUE 写入 os.environ。"""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_manifest(manifest_path: Path, *, require_audio: bool = True) -> dict:
    """加载并校验测试集清单。音频缺失时报告缺哪段，不留堆栈。"""
    if not manifest_path.exists():
        raise SystemExit(f"测试集清单不存在：{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    segments = manifest.get("segments", [])
    if not segments:
        raise SystemExit(f"测试集清单没有任何测试段：{manifest_path}")
    for segment in segments:
        for field in ("id", "label", "audio", "time_label"):
            if not segment.get(field):
                raise SystemExit(f"测试段缺少字段 {field}：{segment}")
    if require_audio:
        missing = [
            f"{segment['id']}（{segment['audio']}）"
            for segment in segments
            if not (PROJECT_ROOT / segment["audio"]).exists()
        ]
        if missing:
            raise SystemExit(
                "以下测试段的音频不在本地磁盘（外置盘未挂载或 data/ 被清理）：\n  "
                + "\n  ".join(missing)
            )
    return manifest


def render_segment_md(run_name: str, segment: dict, text: str) -> str:
    return (
        f"# {segment['label']}（{segment['time_label']}）\n\n"
        f"- run: {run_name}\n"
        f"- segment: {segment['id']}\n"
        f"- audio: {segment['audio']}\n"
        f"- source: {segment.get('source', '')}\n\n"
        f"## 转写正文\n\n{text}\n"
    )


def render_side_by_side(manifest: dict, run_a: str, dir_a: Path, run_b: str, dir_b: Path) -> str:
    """按段对齐两个 run 的转写正文，供硬伤计数对照。"""
    parts = [f"# 并排对比：{run_a} vs {run_b}\n"]
    categories = "、".join(manifest.get("hard_error_categories", []))
    if categories:
        parts.append(f"硬伤四类：{categories}。逐段对照原音频计数，分段计分见清单 scoring。\n")
    for segment in manifest["segments"]:
        seg_id = segment["id"]
        text_a = _read_run_text(dir_a / f"{seg_id}.md")
        text_b = _read_run_text(dir_b / f"{seg_id}.md")
        parts.append(f"\n---\n\n## {segment['label']}（{segment['time_label']}）\n")
        parts.append(f"### {run_a}\n\n{text_a}\n")
        parts.append(f"### {run_b}\n\n{text_b}\n")
    return "\n".join(parts)


def _read_run_text(path: Path) -> str:
    if not path.exists():
        return "[该 run 缺少本段产物]"
    content = path.read_text(encoding="utf-8")
    marker = "## 转写正文\n\n"
    index = content.find(marker)
    return content[index + len(marker):].strip() if index >= 0 else content.strip()


def run_transcription(manifest: dict, run_name: str, *, system_instruction: str | None,
                      timeout_seconds: int, segment_ids: list[str] | None = None) -> Path:
    from openmy.adapters.transcription.gemini_cli import load_vocab_terms
    from openmy.config import GEMINI_MODEL, get_stt_api_key
    from openmy.providers.stt.gemini import GeminiSTTProvider
    from openmy.utils.paths import PROJECT_ENV_PATH

    load_project_env(PROJECT_ENV_PATH)
    api_key = get_stt_api_key("gemini")
    if not api_key:
        raise SystemExit("缺少 GEMINI_API_KEY，评测无法运行。")

    vocab_path = PROJECT_ROOT / "src" / "openmy" / "resources" / "vocab.txt"
    vocab_terms = load_vocab_terms(vocab_path) if vocab_path.exists() else ""

    provider = GeminiSTTProvider(api_key=api_key, model=GEMINI_MODEL)
    out_dir = EVAL_ROOT / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    segments = manifest["segments"]
    if segment_ids:
        segments = [segment for segment in segments if segment["id"] in segment_ids]
    for segment in segments:
        out_path = out_dir / f"{segment['id']}.md"
        if out_path.exists():
            print(f"[skip] {segment['id']} 已有产物：{out_path}")
            continue
        audio_path = PROJECT_ROOT / segment["audio"]
        print(f"[run ] {segment['id']} ← {audio_path.name}")
        result = provider.transcribe(
            audio_path,
            vocab_terms=vocab_terms,
            timeout_seconds=timeout_seconds,
            system_instruction=system_instruction,
        )
        out_path.write_text(render_segment_md(run_name, segment, result.text), encoding="utf-8")
        print(f"[done] {segment['id']} → {out_path}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="固定测试集转写评测")
    parser.add_argument("run_name", nargs="?", help="本次 run 的名字（产物目录名）")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--system-instruction-file", help="实验版 system instruction 文本文件；不传用内置 prompt")
    parser.add_argument("--segments", nargs="*", help="只跑这些 segment id")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--compare", help="跑完后与该 run 做并排对比")
    parser.add_argument("--compare-only", nargs=2, metavar=("RUN_A", "RUN_B"), help="只生成并排对比")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if args.compare_only:
        manifest = load_manifest(manifest_path, require_audio=False)
        run_a, run_b = args.compare_only
        output = render_side_by_side(manifest, run_a, EVAL_ROOT / run_a, run_b, EVAL_ROOT / run_b)
        out_path = EVAL_ROOT / f"side_by_side_{run_a}_vs_{run_b}.md"
        out_path.write_text(output, encoding="utf-8")
        print(f"[done] 并排对比 → {out_path}")
        return

    if not args.run_name:
        parser.error("需要 run_name（或使用 --compare-only）")

    system_instruction = None
    if args.system_instruction_file:
        system_instruction = Path(args.system_instruction_file).read_text(encoding="utf-8").strip()

    manifest = load_manifest(manifest_path)
    run_transcription(
        manifest,
        args.run_name,
        system_instruction=system_instruction,
        timeout_seconds=args.timeout,
        segment_ids=args.segments,
    )
    if args.compare:
        output = render_side_by_side(
            manifest, args.compare, EVAL_ROOT / args.compare, args.run_name, EVAL_ROOT / args.run_name
        )
        out_path = EVAL_ROOT / f"side_by_side_{args.compare}_vs_{args.run_name}.md"
        out_path.write_text(output, encoding="utf-8")
        print(f"[done] 并排对比 → {out_path}")


if __name__ == "__main__":
    main()
