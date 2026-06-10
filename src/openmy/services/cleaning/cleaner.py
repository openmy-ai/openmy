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
import shutil
import sys
from pathlib import Path

from openmy.services.markers import (
    ATTRIBUTION_PREFIXES,
    SOURCE_PLAYBACK,
    parse_attribution,
)


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

# ── 句中废词（轻度清理，只处理最高频的中性填充词）─────
# Fix 5: 不删"啊"，它在中文口语里承载语气和句法连接
INLINE_FILLERS = [
    (r'嗯+[，、]', ''),           # "嗯，然后" → "然后"
    (r'那个[，、]+那个[，、]*', ''),  # "那个，那个，" → ""
    (r'[，、]*(呃|那个)[，。、！？\s]*$', ''),  # 句尾残留废词（不含 啊/嗯）
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

# ── Fix 3: 环境噪音独立行（括号包裹的声音描述）────────
ENV_NOISE_RE = re.compile(
    r'^\s*[（\(【\[](背景|音乐|狗吠|电梯|金属|机器|重物|打火机|吐气|拍手|哨|惊呼|'
    r'车|风|雨|水|门|铃|警报|喇叭|敲|摩擦|碰撞|脚步|咳嗽|笑|哭|叹气|呻吟|'
    r'鸟|猫|鸡|虫|蝉|雷|钟|手机|电话|广播|喊|嘈杂|对话|谈话|聊天|歌|唱|哼)'
    r'[^）\)\]】]*[）\)\]】]\s*$',
    re.MULTILINE,
)

# ── 段落切分阈值 ────────────────────────────────────────
MAX_PARAGRAPH_CHARS = 500
SENTENCE_SPLIT_RE = re.compile(r'(?<=[。！？!?.])\s*')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  清洗步骤
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Fix 2: 上下文相关的答复词——前一行是问句时不删
CONTEXT_REPLY_WORDS = {'嗯', '哦', '对', '是', '好', '行', '嗯嗯', '对对', '是的', '好的', '行的'}


def is_filler_line(line: str, prev_line: str = '') -> bool:
    """整行是废词就返回 True。
    Fix 2: 如果前一行以问号结尾，"嗯"/"哦"/"对"等短答复保留。

    判定在去归因前缀后的净文本上进行——^-anchored filler patterns
    对 "我：嗯嗯。" 形式的行只有先剥前缀才匹配得到。
    """
    stripped = line.strip()
    if not stripped:
        return False
    # 保护时间头
    if TIME_HEADER_RE.match(stripped):
        return False
    # 剥离归因前缀，在净文本上做废词判定
    _, net = parse_attribution(stripped)
    net = net.strip()
    if not net:
        return False
    # Fix 2: 去掉标点后看是不是答复词
    bare = re.sub(r'[，。、！？!?\s]+$', '', net)
    if bare in CONTEXT_REPLY_WORDS:
        prev_stripped = prev_line.strip()
        if prev_stripped and prev_stripped.endswith(('？', '?', '吗', '呢', '吧')):
            return False  # 前面是问句，这是回答，保留
    return any(p.match(net) for p in COMPILED_FILLERS)


def clean_inline(line: str) -> str:
    """句中废词清理。对带归因前缀的行，只清理净文本部分后再拼回前缀。"""
    stripped = line.strip()
    if not stripped or TIME_HEADER_RE.match(stripped) or stripped.startswith('#'):
        return line
    # 提取归因前缀，只对净文本做行内清理
    prefix = ''
    for pfx in ATTRIBUTION_PREFIXES:
        if stripped.startswith(pfx):
            prefix = pfx
            break
    body = stripped[len(prefix):] if prefix else line
    for pattern, replacement in COMPILED_INLINE:
        body = pattern.sub(replacement, body)
    if prefix:
        return prefix + body
    return body


def remove_ai_preamble(text: str) -> str:
    """清除 AI 转写引擎的系统前缀"""
    for pattern in AI_PREAMBLE_PATTERNS:
        text = pattern.sub('', text)
    return text


def remove_music_markers(text: str) -> str:
    """清除 [音乐] 标记——按净文本判定，避免误删归因前缀内容。"""
    out_lines: list[str] = []
    for line in text.split('\n'):
        source, net = parse_attribution(line)
        if MUSIC_RE.search(net):
            # 只在净文本部分替换 [音乐]，再拼回原前缀
            prefix = ''
            for pfx in ATTRIBUTION_PREFIXES:
                if line.lstrip().startswith(pfx):
                    prefix = pfx
                    break
            cleaned_net = MUSIC_RE.sub('', net)
            out_lines.append(prefix + cleaned_net if prefix else cleaned_net)
        else:
            out_lines.append(line)
    return '\n'.join(out_lines)


def deduplicate_lines(lines: list[str]) -> list[str]:
    """去除连续重复行。

    带归因前缀的行按 (来源, 净文本) 去重——相同净文本但前缀不同的
    相邻行不去重（"我：好的" 紧跟 "人：好的" 是真实应答）。
    """
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        if result and result[-1].strip():
            src_cur, net_cur = parse_attribution(stripped)
            src_prev, net_prev = parse_attribution(result[-1].strip())
            if net_cur == net_prev and src_cur == src_prev:
                continue
        result.append(line)
    return result


# Fix 1: 只合并句尾附着词，不合并完整回合词
SUFFIX_PARTICLES = {'啊', '呀', '呢', '嘛', '吧', '了', '哇', '噢'}
REPLY_WORDS = {'对', '是', '行', '好', '嗯', '哦', '对啊', '是啊', '行啊', '好的',
               '谢谢', '拜拜', '小心', '没事', '不是', '不行', '不好', '不对',
               '可以', '知道', '明白', '懂了', '收到'}


def merge_short_lines(lines: list[str], min_length: int = 3) -> list[str]:
    """Fix 1: 只合并句尾附着词到上一行，保留完整回合词的独立性。

    带归因前缀的行：判短用净文本长度，附着词只并入同前缀的上一行，
    纯标记行（净文本为空）不并入上一行。
    """
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        # 空行、时间头、标题不合并
        if not stripped or TIME_HEADER_RE.match(stripped) or stripped.startswith('#'):
            result.append(line)
            continue
        # 用净文本判断短行
        src_cur, net_cur = parse_attribution(stripped)
        net_cur = net_cur.strip()
        # 纯标记行（只有前缀，净文本为空）不合并
        if not net_cur:
            result.append(line)
            continue
        bare = re.sub(r'[，。、！？!?\s]+$', '', net_cur)
        if len(net_cur) < min_length and result and result[-1].strip():
            # 要求前缀一致才合并
            src_prev, _ = parse_attribution(result[-1].strip())
            if bare in SUFFIX_PARTICLES and src_cur == src_prev:
                # 句尾附着词 → 合并到上一行
                result[-1] = result[-1].rstrip() + net_cur
            else:
                # 回合词、不同前缀或其他短句 → 保持独立
                result.append(line)
        else:
            result.append(line)
    return result


# Fix 4: 助手回复检测关键词
ASSISTANT_REPLY_CUES = re.compile(
    r'(首先|其次|另一方面|从.*角度来看|你可以采用|本质是|'
    r'建议.*方案|这里.*架构|总结来说|综上所述|'
    r'我来.*解释|让我.*分析|具体来说)',
)
QUESTION_COMMAND_RE = re.compile(r'[？?]$|你先|帮我|给我|说中文|看一下|演示')


def mark_assistant_replies(lines: list[str], min_length: int = 80) -> list[str]:
    """Fix 4: 给疑似助手回复打标签，不删除。
    条件：前一行是提问/命令 + 当前行较长 + 有讲解式句型。

    外放行（外：前缀）跳过——归因标记已声明来源。
    """
    result: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or TIME_HEADER_RE.match(stripped) or stripped.startswith('#'):
            result.append(line)
            continue
        # 外：行已标归因，跳过助手回复检测
        source, net = parse_attribution(stripped)
        if source == SOURCE_PLAYBACK:
            result.append(line)
            continue
        # 检测助手回复特征——用净文本判断长度和内容
        if len(net) >= min_length and ASSISTANT_REPLY_CUES.search(net):
            prev = lines[i - 1].strip() if i > 0 else ''
            if prev and QUESTION_COMMAND_RE.search(prev):
                result.append(f'[助手回复] {line}')
                continue
        result.append(line)
    return result


def mark_suspicious_crosstalk(lines: list[str], min_length: int = 40) -> list[str]:
    """给明显像外放/串台的长行打标签，不直接删除。

    外：前缀的行已通过归因标记声明来源，不再打 [疑似串台]。
    """
    from openmy.services.scene_quality import inspect_scene_text

    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or TIME_HEADER_RE.match(stripped) or stripped.startswith('#'):
            result.append(line)
            continue
        # 外：行已标归因，跳过串台检测
        source, _ = parse_attribution(stripped)
        if source == SOURCE_PLAYBACK:
            result.append(line)
            continue
        quality = inspect_scene_text(stripped)
        if quality["suspicious_content"] and len(stripped) >= min_length and not stripped.startswith('[疑似串台]'):
            result.append(f'[疑似串台] {line}')
            continue
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
    """长段落（>500字）在句号处强制切分。

    带归因前缀的长行：切分后每个片段重新加上原前缀，
    避免续段全部失去来源标记。
    """
    lines = text.split('\n')
    result: list[str] = []
    for line in lines:
        if len(line) > MAX_PARAGRAPH_CHARS and not TIME_HEADER_RE.match(line.strip()):
            # 提取归因前缀
            prefix = ''
            for pfx in ATTRIBUTION_PREFIXES:
                if line.lstrip().startswith(pfx):
                    prefix = pfx
                    break
            body = line.lstrip()[len(prefix):] if prefix else line
            sentences = SENTENCE_SPLIT_RE.split(body)
            current = ''
            for sent in sentences:
                if len(current) + len(sent) > MAX_PARAGRAPH_CHARS and current:
                    result.append(prefix + current)
                    current = sent
                else:
                    current += sent
            if current:
                result.append(prefix + current)
        else:
            result.append(line)
    return '\n'.join(result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  纠错替换
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESOURCES_DIR = Path(__file__).resolve().parent.parent.parent / 'resources'
CORRECTIONS_FILE = RESOURCES_DIR / 'corrections.json'
CORRECTIONS_EXAMPLE_FILE = RESOURCES_DIR / 'corrections.example.json'
VOCAB_FILE = RESOURCES_DIR / 'vocab.txt'
VOCAB_EXAMPLE_FILE = RESOURCES_DIR / 'vocab.example.txt'


def resolve_resource_path(primary: Path, fallback: Path, *, auto_init: bool = False) -> Path | None:
    if primary.exists():
        return primary
    if fallback.exists():
        if auto_init:
            primary.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fallback, primary)
            return primary
        return fallback
    return None


def load_corrections() -> list[dict]:
    """加载纠错词典"""
    final_path = resolve_resource_path(CORRECTIONS_FILE, CORRECTIONS_EXAMPLE_FILE, auto_init=True)
    if not final_path:
        return []
    try:
        data = json.loads(final_path.read_text(encoding='utf-8'))
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


def _load_vocab_for_correction() -> str:
    """读取 vocab.txt 用于 LLM 纠错 prompt。"""
    vocab_file = resolve_resource_path(VOCAB_FILE, VOCAB_EXAMPLE_FILE)
    if not vocab_file:
        return ""
    entries: list[str] = []
    for raw_line in vocab_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 1)
        term = parts[0].strip()
        if not term:
            continue
        if len(parts) > 1:
            entries.append(f"{term}（{parts[1].strip()}）")
        else:
            entries.append(term)
    return "、".join(entries)


def llm_correction(text: str, api_key: str) -> str:
    """用 Gemini Flash 做一轮上下文纠错。只修正明显错误，不改语义。"""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return text

    if not api_key:
        return text

    from openmy.config import get_llm_model
    model = get_llm_model()

    vocab = _load_vocab_for_correction()
    prompt_parts = [
        "你是语音转写纠错助手。下面是一段语音转写文本，可能存在同音字错误（尤其是人名）、方言误识别、噪音被误转为文字等问题。",
        "",
        "规则：",
        "1. 只修正明显的转写错误（同音字、人名、术语），不改语义、不润色、不删内容。",
        "2. 保留所有时间头（## HH:MM）、标签（[助手回复]、[疑似串台]）和格式。",
        "3. 保留所有归因前缀（我：、人：、外：）和存疑记号（[?内容]），不得删除、改写或移动。",
        "4. 繁体字统一为简体。",
        "5. 如果不确定是否错误，保持原样。宁可漏改也不要改错。",
        "6. 直接输出修正后的完整文本，不加任何说明或前缀。",
    ]
    if vocab:
        prompt_parts.extend(["", "词库（正确写法和提示）：", vocab])
    prompt_parts.extend(["", "---", "", "待纠错文本：", "", text])
    prompt = "\n".join(prompt_parts)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.1),
        )
        corrected = response.text.strip() if response.text else ""
    except Exception as e:
        print(f"  ⚠ LLM 纠错失败，保留原文: {e}", file=sys.stderr)
        return text

    if not corrected:
        return text

    orig_len = len(text.replace("\n", "").replace(" ", ""))
    new_len = len(corrected.replace("\n", "").replace(" ", ""))
    if orig_len > 0 and abs(new_len - orig_len) / orig_len > 0.15:
        print("  ⚠ LLM 纠错改动过大(>15%)，丢弃，保留原文", file=sys.stderr)
        return text

    diff_count = sum(1 for a, b in zip(text, corrected) if a != b)
    print(f"  ✓ LLM 纠错: {diff_count} 处字符变更", file=sys.stderr)
    return corrected


def sync_correction_to_vocab(wrong: str, right: str, context: str = ''):
    """将纠正同步写入 vocab.txt（事前预防层）"""
    vocab_file = resolve_resource_path(VOCAB_FILE, VOCAB_EXAMPLE_FILE, auto_init=True)
    if not vocab_file:
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

    # Step 2.5 (Fix 3): 清除环境噪音行——外：行已声明归因来源，
    # 不删除；其余行对净文本做判定
    env_filtered: list[str] = []
    for env_line in text.split('\n'):
        source, env_net = parse_attribution(env_line)
        if source == SOURCE_PLAYBACK:
            env_filtered.append(env_line)  # 外：行不删
            continue
        net_stripped = env_net.strip()
        if net_stripped and ENV_NOISE_RE.match(net_stripped):
            continue  # 净文本是环境噪音，删除整行
        env_filtered.append(env_line)
    text = '\n'.join(env_filtered)

    lines = text.split('\n')

    # Step 3 (Fix 2): 去除纯废词行（上下文感知）
    filtered: list[str] = []
    for i, line in enumerate(lines):
        prev = lines[i - 1] if i > 0 else ''
        if not is_filler_line(line, prev):
            filtered.append(line)
    lines = filtered

    # Step 4: 行内废词清理
    lines = [clean_inline(l) for l in lines]

    # Step 4.5 (Fix 4): 给助手回复打标签
    lines = mark_assistant_replies(lines)

    # Step 4.6: 给明显串台的长段打标签
    lines = mark_suspicious_crosstalk(lines)

    # Step 5: 去除连续重复行
    lines = deduplicate_lines(lines)

    # Step 6 (Fix 1): 合并句尾附着词（不合并回合词）
    lines = merge_short_lines(lines, min_length=3)

    # Step 7: 合并连续空行
    lines = collapse_blank_lines(lines)

    # Step 8: 去除首尾空行
    result = '\n'.join(lines).strip()

    # Step 9: 长段强制切分（消灭文字墙）
    result = split_long_paragraphs(result)

    # Step 10: 纠错替换（从 corrections.json 强制修正错词）
    result = apply_corrections(result)

    # Step 11: LLM 上下文纠错（可选，需要 api_key）
    if api_key:
        result = llm_correction(result, api_key)

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
