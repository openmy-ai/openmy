#!/usr/bin/env python3
"""
cleaner.py — 用 Gemini CLI 对转写文本做语义级清洗

设计原则：
- 清洗全部交给大模型，不用正则硬编码
- 只降噪，不改语义
- 保留脏话（真实语气证据）、背景音标注、自然分段
"""

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

DEFAULT_MODEL = "gemini-2.5-flash"

CLEAN_PROMPT = """你是一个录音转写文本的清洗助手。下面是一段语音转写的原始文本，请帮我清洗。

## 你要做的事

1. **修正明显的转写错误**：音近字、同音替换（例如"寄养费"应该是"降费"，"阿加塔"应该是"阿维塔"）
2. **去掉 AI 转写引擎的系统前缀**：如"我这就为您转写..."、"针对音频文件..."、"转写如下"等机械文本
3. **去掉纯语气废词行**：整行只有"嗯"、"啊"、"哦"的行直接删掉
4. **去掉重复行**：连续出现的完全相同的行只保留一次
5. **去掉 [音乐] 标记**

## 你绝对不能做的事

1. **不要加任何格式标记**：不加粗（**）、不加引号、不加列表符号
2. **不要删脏话**：脏话是真实语气，必须保留
3. **不要改写/润色/总结**：保留原话，不要把口语改成书面语
4. **不要删背景音标注**：（打火机声）（狗吠声）（背景粤语对话）这些全部保留
5. **不要合并段落**：保留原始的分行和分段结构
6. **不要删时间头**：## HH:MM 格式的行必须原封不动保留
7. **不要加任何说明文字**：直接输出清洗后的文本，不要写"以下是清洗结果"之类的前缀

## 输出要求

直接输出清洗后的纯文本，格式与输入完全一致。

---

原始转写文本：

{text}"""


def prepare_isolated_home(source_home: Path, model: str) -> Path:
    """给 Gemini CLI 准备隔离的 HOME 目录"""
    isolated_root = Path(tempfile.mkdtemp(prefix="gemini-cli-clean-"))
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


def clean_with_gemini_cli(
    text: str,
    model: str = DEFAULT_MODEL,
    gemini_home: Path | None = None,
    timeout_seconds: int = 300,
) -> str:
    """调 Gemini CLI 做语义级清洗"""
    if gemini_home is None:
        gemini_home = Path.home() / ".gemini"

    isolated_home = prepare_isolated_home(gemini_home, model)
    try:
        env = os.environ.copy()
        env["HOME"] = str(isolated_home)
        env["NO_COLOR"] = "1"
        env.pop("GEMINI_API_KEY", None)

        prompt = CLEAN_PROMPT.format(text=text)

        cmd = [
            "gemini",
            "-m", model,
            "--output-format", "text",
            "-p", prompt,
        ]

        proc = subprocess.run(
            cmd,
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
            f"Gemini CLI 清洗失败，退出码 {proc.returncode}\nSTDERR:\n{stderr[:2000]}"
        )
    if not stdout:
        raise RuntimeError(
            f"Gemini CLI 清洗没有返回内容\nSTDERR:\n{stderr[:2000]}"
        )

    return stdout


def clean_text(text: str) -> str:
    """清洗入口：调 Gemini CLI 做语义级清洗"""
    return clean_with_gemini_cli(text)


# ── 纠错相关工具（保留，供 correct 命令使用）────────────────

CORRECTIONS_FILE = Path(__file__).resolve().parent.parent.parent / 'resources' / 'corrections.json'


def load_corrections() -> list[dict]:
    """加载纠错词典"""
    if not CORRECTIONS_FILE.exists():
        return []
    try:
        data = json.loads(CORRECTIONS_FILE.read_text(encoding='utf-8'))
        return data.get('corrections', [])
    except Exception:
        return []


def sync_correction_to_vocab(wrong: str, right: str, context: str = ''):
    """将纠正同步写入 vocab.txt（事前预防层）"""
    vocab_file = Path(__file__).resolve().parent.parent.parent / 'resources' / 'vocab.txt'
    if not vocab_file.exists():
        return

    existing = vocab_file.read_text(encoding='utf-8')

    if right in existing:
        return

    desc = f"不是\"{wrong}\"" + (f"，{context}" if context else "")
    entry = f"{right} | {desc}\n"

    if '# ── 常见音近易错词' in existing:
        existing = existing.rstrip() + '\n' + entry
    else:
        existing = existing.rstrip() + '\n\n# ── 常见音近易错词（自动添加）──────────────────────────────────\n' + entry

    vocab_file.write_text(existing, encoding='utf-8')


def main():
    if len(sys.argv) not in {2, 3}:
        print("用法: python3 cleaner.py <input.txt> [output.txt]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) == 3 else None

    if not input_path.exists():
        print(f"文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding='utf-8')

    before_chars = len(text.replace('\n', '').replace(' ', ''))

    cleaned = clean_text(text)

    after_chars = len(cleaned.replace('\n', '').replace(' ', ''))
    removed = before_chars - after_chars
    pct = (removed / before_chars * 100) if before_chars > 0 else 0

    if output_path is not None:
        output_path.write_text(cleaned, encoding='utf-8')
    else:
        print(cleaned)

    print(f"清洗完成: {before_chars} → {after_chars} 字 (去除 {removed} 字, {pct:.1f}%)",
          file=sys.stderr)


if __name__ == '__main__':
    main()
