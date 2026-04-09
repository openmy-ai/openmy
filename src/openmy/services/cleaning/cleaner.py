#!/usr/bin/env python3
"""
cleaner.py — 规则引擎清洗 + corrections.json 确定性纠错

设计原则：
- 纯本地处理，不调 API，零成本、秒完成
- 只降噪，不改语义
- 保留脏话（真实语气证据）、背景音标注、自然分段
- 保护时间头（## HH:MM）和角色信号词
"""

import json
import re
import sys
from pathlib import Path

from openmy.config import TIME_HEADER_LOSS_THRESHOLD

# ── 时间头保护 ────────────────────────────────────────────
TIME_HEADER_RE = re.compile(r'^##\s+\d{1,2}:\d{2}', re.MULTILINE)

# ── 废词/语气词模式（独立成行时删除）─────────────────────
FILLER_PATTERNS = [
    # 语气词（独立出现时删除）
    r'^[嗯啊呃哦哈嘿唉诶呢嘛吧呀哇噢额]+[，。、！？\s]*$',
    # 口头禅（独立出现时删除）
    r'^(那个|就是说|就是|然后|所以说|对对对|对对|是的是的|好的好的|OK|ok|嗯嗯|啊啊|哈哈|呵呵)[，。、！？\s]*$',
    # 无意义重复
    r'^(那那那|这这这|就就就|然后然后|所以所以)[，。、！？\s]*$',
]
COMPILED_FILLERS = [re.compile(p) for p in FILLER_PATTERNS]

# ── 句中废词（轻度清理，只处理最高频的）─────────────────
INLINE_FILLERS = [
    (r'嗯+[，、]', ''),           # "嗯，然后" → "然后"
    (r'啊+[，、]', ''),           # "啊，就是" → "就是"
    (r'那个[，、]+那个[，、]*', ''),  # "那个，那个，" → ""
    (r'[，、]*(嗯|啊|然后|那个)[，。、！？\s]*$', ''),  # 句尾残留废词
    (r'就是说[，、]+', ''),       # "就是说，" → ""
    (r'然后[，、]+然后[，、]*', '然后'),  # "然后，然后" → "然后"
]
COMPILED_INLINE = [(re.compile(p), r) for p, r in INLINE_FILLERS]

# ── AI 转写引擎前缀（整行删除）─────────────────────────
AI_PREAMBLE_PATTERNS = [
    re.compile(r'^.*为您.*转写.*$', re.MULTILINE),
    re.compile(r'^.*针对.*音频文件.*$', re.MULTILINE),
    re.compile(r'^.*转写如下.*$', re.MULTILINE),
    re.compile(r'^.*已经转写完成.*$', re.MULTILINE),
    re.compile(r'^.*sub_\d+\.wav.*$', re.MULTILINE),
    re.compile(r'`sub_\d+\.wav`'),
]

# ── [音乐] 标记 ────────────────────────────────────────
MUSIC_RE = re.compile(r'\[音乐\]')

# ── 段落切分阈值 ────────────────────────────────────────
MAX_PARAGRAPH_CHARS = 500
SENTENCE_SPLIT_RE = re.compile(r'(?<=[。！？!?.])\s*')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  清洗步骤
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_filler_line(line: str) -> bool:
    """整行是废词就返回 True"""
    stripped = line.strip()
    if not stripped:
        return False
    # 保护时间头
    if TIME_HEADER_RE.match(stripped):
        return False
    return any(p.match(stripped) for p in COMPILED_FILLERS)


def clean_inline(line: str) -> str:
    """句中废词清理"""
    stripped = line.strip()
    if not stripped or TIME_HEADER_RE.match(stripped) or stripped.startswith('#'):
        return line
    for pattern, replacement in COMPILED_INLINE:
        line = pattern.sub(replacement, line)
    return line


def remove_ai_preamble(text: str) -> str:
    """清除 AI 转写引擎的系统前缀"""
    for pattern in AI_PREAMBLE_PATTERNS:
        text = pattern.sub('', text)
    return text


def remove_music_markers(text: str) -> str:
    """清除 [音乐] 标记"""
    return MUSIC_RE.sub('', text)


def deduplicate_lines(lines: list[str]) -> list[str]:
    """去除连续重复行"""
    result: list[str] = []
    for line in lines:
        if result and line.strip() == result[-1].strip() and line.strip():
            continue
        result.append(line)
    return result


def merge_short_lines(lines: list[str], min_length: int = 3) -> list[str]:
    """合并过短的碎句到上一行（只合并 ≤min_length 字的碎片）"""
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        # 空行、时间头、标题不合并
        if not stripped or TIME_HEADER_RE.match(stripped) or stripped.startswith('#'):
            result.append(line)
            continue
        # 太短的碎句合并到上一行
        if len(stripped) < min_length and result and result[-1].strip():
            result[-1] = result[-1].rstrip() + stripped
        else:
            result.append(line)
    return result


def collapse_blank_lines(lines: list[str]) -> list[str]:
    """连续空行最多保留 1 个"""
    result: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    return result


def split_long_paragraphs(text: str) -> str:
    """长段落（>500字）在句号处强制切分"""
    lines = text.split('\n')
    result: list[str] = []
    for line in lines:
        if len(line) > MAX_PARAGRAPH_CHARS and not TIME_HEADER_RE.match(line.strip()):
            sentences = SENTENCE_SPLIT_RE.split(line)
            current = ''
            for sent in sentences:
                if len(current) + len(sent) > MAX_PARAGRAPH_CHARS and current:
                    result.append(current)
                    current = sent
                else:
                    current += sent
            if current:
                result.append(current)
        else:
            result.append(line)
    return '\n'.join(result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  纠错替换
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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


def apply_corrections(text: str) -> str:
    """从 corrections.json 读取纠错规则，强制替换。确定性兜底。"""
    corrections = load_corrections()
    if not corrections:
        return text

    replaced_count = 0
    corrected_lines: list[str] = []
    for line in text.splitlines():
        updated_line = line
        for c in corrections:
            wrong = c.get('wrong', '')
            right = c.get('right', '')
            if not wrong or not right or wrong not in updated_line:
                continue
            # 如果这一行已经同时出现了正确词，通常是在解释"错词 → 正词"，不要误伤原意。
            if right in updated_line:
                continue
            updated_line = updated_line.replace(wrong, right)
            replaced_count += 1
        corrected_lines.append(updated_line)

    if replaced_count > 0:
        print(f"  ✓ 纠错替换: {replaced_count} 处", file=sys.stderr)

    return "\n".join(corrected_lines)


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  主入口
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def clean_text(text: str, api_key: str | None = None) -> str:
    """完整清洗流程（纯规则引擎，不调 API）。

    设计原则：
    - 只降噪，不改语义
    - 不删脏话（真实语气是上下文证据）
    - 不加粗、不改词（除纠错词典）
    - 保留自然分段和对话节奏
    """
    # Step 1: 清除 AI 转写引擎的系统前缀
    text = remove_ai_preamble(text)

    # Step 2: 清除 [音乐] 标记
    text = remove_music_markers(text)

    lines = text.split('\n')

    # Step 3: 去除纯废词行
    lines = [l for l in lines if not is_filler_line(l)]

    # Step 4: 行内废词清理
    lines = [clean_inline(l) for l in lines]

    # Step 5: 去除连续重复行
    lines = deduplicate_lines(lines)

    # Step 6: 合并单字残句（只合并 ≤2 字的碎片，保留对话节奏）
    lines = merge_short_lines(lines, min_length=3)

    # Step 7: 合并连续空行
    lines = collapse_blank_lines(lines)

    # Step 8: 去除首尾空行
    result = '\n'.join(lines).strip()

    # Step 9: 长段强制切分（消灭文字墙）
    result = split_long_paragraphs(result)

    # Step 10: 纠错替换（从 corrections.json 强制修正错词）
    result = apply_corrections(result)

    return result


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
