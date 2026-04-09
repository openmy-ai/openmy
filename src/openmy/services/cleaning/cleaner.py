#!/usr/bin/env python3
"""
clean.py — 每日上下文转写文本轻度清洗
用法: python3 clean.py <input.txt> <output.txt>

清洗规则:
1. 去除常见中文口语废词（嗯、啊、那个、就是说...）
2. 去除疑似歌词/音乐口播段（高比例英文歌词、重复副歌）
3. 过滤脏话/粗口（我操、他妈、傻逼...）
4. 合并过短的碎句（<5 字的独立行合并到上一行）
5. 去除重复行（Whisper 偶尔会重复输出）
6. 去除纯空白行堆叠（最多保留 1 个空行）
7. 长段落强制切分（>500 字在句号处断行）
8. 关键词自动加粗（英文专有名词 + 高频中文术语）
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# ── 时间头保护 ────────────────────────────────────────────
TIME_HEADER_RE = re.compile(r'^##\s+\d{1,2}:\d{2}')

# ── 角色信号词保护 ────────────────────────────────────────
# 这些词对角色识别至关重要，清洗时不能误删
try:
    from openmy.services.roles.resolver import ROLE_SIGNAL_WORDS
except ImportError:
    try:
        from ..roles.resolver import ROLE_SIGNAL_WORDS
    except ImportError:
        ROLE_SIGNAL_WORDS = {
        "老婆", "老公", "宝贝", "亲爱的", "好女", "爸", "妈",
        "爷", "奶", "姥", "姥爷", "师傅", "老板", "客服",
        "服务员", "兄弟", "哥", "姐", "大爷", "大妈",
        "乖", "坐下", "别叫", "过来", "小狗", "小猫", "青维",
        "小小得", "主家你好",
        "回来", "记一下", "报告", "给你", "帮我", "买单",
        "结账", "谢谢", "你好", "再见",
    }

# ── 废词/语气词模式 ──────────────────────────────────────（独立出现时删除，嵌在句中时保留上下文）
FILLER_PATTERNS = [
    # 语气词（独立出现时删除）
    r'^[嗯啊呃哦哈嘿唉诶呢嘛吧呀哇噢额]+[，。、！？\s]*$',
    # 口头禅（独立出现时删除）
    r'^(那个|就是说|就是|然后|所以说|对对对|对对|是的是的|好的好的|OK|ok|嗯嗯|啊啊|哈哈|呵呵)[，。、！？\s]*$',
    # 无意义重复
    r'^(那那那|这这这|就就就|然后然后|所以所以)[，。、！？\s]*$',
]

# 句中废词（轻度清理，只处理最高频的）
INLINE_FILLERS = [
    (r'嗯+[，、]', ''),           # "嗯，然后" → "然后"
    (r'啊+[，、]', ''),           # "啊，就是" → "就是"
    (r'那个[，、]+那个[，、]*', ''),  # "那个，那个，" → ""
    (r'[，、]*(嗯|啊|然后|那个)[，。、！？\s]*$', ''),  # 句尾残留废词
    (r'就是说[，、]+', ''),       # "就是说，" → ""
    (r'然后[，、]+然后[，、]*', '然后'),  # "然后，然后" → "然后"
]

COMPILED_FILLERS = [re.compile(p) for p in FILLER_PATTERNS]
COMPILED_INLINE = [(re.compile(p), r) for p, r in INLINE_FILLERS]
SENTENCE_SPLIT_RE = re.compile(r'(?<=[。！？!?\.])\s*')

# ── 脏话/粗口过滤 ────────────────────────────────────────
# 行内替换：把脏话从句子中删除
PROFANITY_INLINE = [
    (r'我操[他她]妈[的]?', ''),      # 我操他妈 / 我操他妈的
    (r'[你他她它]妈[的]?[，。！？、\s]*', ''),  # 他妈的 / 你妈的
    (r'妈[的]?[，。！？、\s]*', ''),   # 妈的
    (r'我[操艹草靠](?![作为纵控])', ''),  # 我操（排除"操作""操为"等正常词）
    (r'[操艹草]你[妈娘]?', ''),        # 操你妈
    (r'傻[逼屄比BbⅠ]', ''),           # 傻逼 / 傻B
    (r'牛[逼屄比BbⅠ]', ''),           # 牛逼 / 牛B
    (r'(?<![操作])操[，。！？、\s]+', ''),  # 独立的 操，（排除"操作"）
    (r'[艹草][，。！？、\s]+', ''),     # 草！
    (r'卧[槽草]', ''),                 # 卧槽
    (r'我[去勒]', ''),                 # 我去
    (r'[T他t][M妈m][D的d]', ''),       # TMD / tmd
    (r'[Ss][Bb]', ''),                 # SB / sb
    (r'[Nn][Bb]', ''),                 # NB / nb
    (r'什么玩意儿?', ''),              # 什么玩意
    (r'狗[日屁]的?', ''),              # 狗日的
    (r'尼[玛马]', ''),                 # 尼玛
    (r'他[妈嘛]太', ''),               # 他妈太
]
COMPILED_PROFANITY = [(re.compile(p), r) for p, r in PROFANITY_INLINE]

# 纯脏话行（整行只有骂人的，直接删）
PROFANITY_LINE_RE = re.compile(
    r'^[\s，。！？、]*(我[操艹草靠]|[操艹草]|傻[逼屄比]|卧[槽草]|妈[的]?|[你他她]妈[的]?|TMD|tmd)[\s，。！？、]*$'
)

# ── 段落切分阈值 ────────────────────────────────────────
MAX_PARAGRAPH_CHARS = 500

# ── Gemini/AI 转写系统前缀清理 ───────────────────────
# Gemini 转写时经常在每段音频前加一句系统前缀，必须整行删除
AI_PREAMBLE_PATTERNS = [
    # 整行匹配：包含"为您"+"转写"的行
    re.compile(r'^.*为您.*转写.*$', re.MULTILINE),
    # 整行匹配：包含"针对"+"音频文件"的行
    re.compile(r'^.*针对.*音频文件.*$', re.MULTILINE),
    # 整行匹配：包含"转写如下"的行
    re.compile(r'^.*转写如下.*$', re.MULTILINE),
    # 整行匹配："已经转写完成"
    re.compile(r'^.*已经转写完成.*$', re.MULTILINE),
    # 整行匹配：包含 sub_XXXX.wav 的系统描述行
    re.compile(r'^.*sub_\d+\.wav.*$', re.MULTILINE),
    # 反引号包裹的文件名残留
    re.compile(r'`sub_\d+\.wav`'),
]

# ── 关键词加粗：保护列表（不加粗的常见英文词）────────────
COMMON_ENGLISH_SKIP = {
    'a', 'an', 'the', 'of', 'in', 'on', 'at', 'to', 'for', 'is', 'it',
    'and', 'or', 'but', 'not', 'no', 'yes', 'ok', 'so', 'up', 'my',
    'me', 'he', 'she', 'we', 'they', 'you', 'your', 'his', 'her',
    'this', 'that', 'what', 'how', 'why', 'when', 'where', 'who',
    'with', 'from', 'by', 'as', 'if', 'be', 'do', 'am', 'are', 'was',
    'were', 'been', 'have', 'has', 'had', 'will', 'can', 'may', 'just',
    'very', 'too', 'like', 'look', 'go', 'got', 'get', 'let', 'say',
    'see', 'come', 'going', 'well', 'good', 'bad', 'one', 'two',
    'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'than', 'then', 'them', 'some', 'all', 'only', 'also', 'about',
    'out', 'over', 'still', 'back', 'into', 'here', 'there',
}


def split_sentences(text: str) -> list[str]:
    """按句号/问号/感叹号粗分句"""
    parts = SENTENCE_SPLIT_RE.split(text.strip())
    return [part.strip() for part in parts if part.strip()]


def is_probable_lyric_sentence(sentence: str) -> bool:
    """判断一句是否更像歌词/音乐口播，而不是日常中文口述"""
    stripped = sentence.strip()
    if not stripped:
        return False

    english_words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", stripped)
    english_word_count = len(english_words)
    alpha_chars = sum(ch.isascii() and ch.isalpha() for ch in stripped)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', stripped))

    # 明显的长英文歌词句
    if chinese_chars <= 2 and (english_word_count >= 8 or alpha_chars >= 35):
        return True

    # 中英夹杂但几乎被英文淹没，通常是歌词混入
    if english_word_count >= 12 and alpha_chars > chinese_chars * 4:
        return True

    # 副歌型重复：词汇重复率很高，且几乎都是英文
    words = [w.lower() for w in english_words]
    if len(words) >= 8:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio <= 0.6 and chinese_chars <= 4:
            return True

    return False


def is_probable_lyric_fragment(sentence: str) -> bool:
    """在已判定为歌词段的上下文里，进一步清理英文碎片/副歌残句"""
    stripped = sentence.strip()
    if not stripped:
        return False

    english_words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", stripped)
    english_word_count = len(english_words)
    alpha_chars = sum(ch.isascii() and ch.isalpha() for ch in stripped)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', stripped))

    if chinese_chars == 0 and english_word_count >= 1 and alpha_chars >= 2:
        return True
    if chinese_chars <= 2 and english_word_count >= 3:
        return True
    if chinese_chars <= 4 and english_word_count >= 2:
        return True
    return False


MUSIC_MARKER_RE = re.compile(r'\[音乐\]')


def remove_ai_preamble(text: str) -> str:
    """清除 Gemini/AI 转写引擎的系统前缀和机械回复文本。

    这些文本是转写引擎在每段音频开头/结尾自动添加的：
    - "我这就为您转写音频文件 sub_0001.wav 的内容。"
    - "针对音频文件 `sub_0002.wav` 的转写如下："
    - "已经转写完成"
    """
    # 先用正则模式批量清理
    for pattern in AI_PREAMBLE_PATTERNS:
        text = pattern.sub('', text)

    # 逐行清理：删除只剩标点/空白的残行
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # 跳过被清理后只剩标点的残行
        if stripped and all(c in '，。、！？：:；;…—' for c in stripped):
            continue
        # 保护时间头
        if TIME_HEADER_RE.match(stripped):
            cleaned.append(line)
            continue
        cleaned.append(line)

    return '\n'.join(cleaned)


def remove_music_markers(text: str) -> str:
    """清除 Gemini 输出的 [音乐] 标记及其前后碎片残句"""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue
        # 如果整行只有 [音乐] 标记（可能重复），直接丢弃
        if re.fullmatch(r'[\s\[音乐\]。，、！？\s]*', stripped):
            continue
        # 去掉行内的 [音乐] 标记
        cleaned_line = MUSIC_MARKER_RE.sub('', line).strip()
        if cleaned_line:
            cleaned.append(cleaned_line)
    return '\n'.join(cleaned)


def remove_lyric_sentences(text: str) -> str:
    """逐段去掉疑似歌词句，保留前后中文口述。保护 ## HH:MM 时间头。"""
    # 先按行扫描，把时间头行独立出来，把非时间头内容分段处理
    lines = text.split('\n')
    blocks = []     # 每个元素是 ('time', '## HH:MM') 或 ('para', '段落文本')
    current_para_lines = []

    def flush_para():
        if current_para_lines:
            para_text = '\n'.join(current_para_lines).strip()
            if para_text:
                blocks.append(('para', para_text))
            current_para_lines.clear()

    for line in lines:
        stripped = line.strip()
        if TIME_HEADER_RE.match(stripped):
            flush_para()
            blocks.append(('time', stripped))
        elif not stripped:
            # 空行 = 段落边界
            flush_para()
        else:
            current_para_lines.append(line)
    flush_para()

    # 对每个 para 块做歌词过滤，time 块直接保留
    result_parts = []
    for block_type, block_text in blocks:
        if block_type == 'time':
            result_parts.append(block_text)
            continue

        sentences = split_sentences(block_text)
        if not sentences:
            continue

        paragraph_has_lyrics = any(is_probable_lyric_sentence(s) for s in sentences)
        kept = []
        for sentence in sentences:
            if is_probable_lyric_sentence(sentence):
                continue
            if paragraph_has_lyrics and is_probable_lyric_fragment(sentence):
                continue
            kept.append(sentence)
        if not kept:
            continue

        kept_text = ' '.join(kept).strip()
        kept_chinese = len(re.findall(r'[\u4e00-\u9fff]', kept_text))
        kept_english_words = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", kept_text))

        if kept_chinese < 6 and kept_english_words >= 6:
            continue

        result_parts.append(kept_text)

    return '\n\n'.join(result_parts)


def remove_profanity(text: str) -> str:
    """过滤脏话/粗口。
    - 整行纯脏话 → 删除
    - 句中脏话 → 替换为空
    - 保护时间头
    """
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # 保护时间头和空行
        if not stripped or TIME_HEADER_RE.match(stripped):
            cleaned.append(line)
            continue
        # 整行纯脏话，直接删
        if PROFANITY_LINE_RE.match(stripped):
            continue
        # 行内脏话替换
        result = line
        for pat, repl in COMPILED_PROFANITY:
            result = pat.sub(repl, result)
        # 清理替换后可能留下的多余标点/空格
        result = re.sub(r'[\s，、]{3,}', '，', result)
        result = result.strip()
        if result:
            cleaned.append(result)
    return '\n'.join(cleaned)


def is_filler_line(line: str) -> bool:
    """判断是否为纯废词行"""
    stripped = line.strip()
    if not stripped:
        return False
    # 保护时间头
    if TIME_HEADER_RE.match(stripped):
        return False
    # 保护含角色信号词的行（对角色识别至关重要）
    if any(w in stripped for w in ROLE_SIGNAL_WORDS):
        return False
    return any(pat.match(stripped) for pat in COMPILED_FILLERS)


def clean_inline(text: str) -> str:
    """清理行内废词"""
    for pat, repl in COMPILED_INLINE:
        text = pat.sub(repl, text)
    return text


def merge_short_lines(lines: list[str], min_length: int = 5) -> list[str]:
    """合并过短的碎行到上一行"""
    if not lines:
        return []

    result = [lines[0]]
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue

        # 保护时间头，不合并
        if TIME_HEADER_RE.match(stripped):
            result.append(line)
            continue

        # 保护含角色信号词的短行（如"乖""老婆""谢谢"）
        if any(w in stripped for w in ROLE_SIGNAL_WORDS):
            result.append(line)
            continue

        # 如果当前行太短且上一行非空，合并
        if len(stripped) < min_length and result and result[-1].strip():
            result[-1] = result[-1].rstrip() + stripped
        else:
            result.append(line)

    return result


def deduplicate_lines(lines: list[str]) -> list[str]:
    """去除重复行（Whisper 转写时偶尔会重复，可能不连续）"""
    if not lines:
        return []

    seen = set()
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        if stripped not in seen:
            seen.add(stripped)
            result.append(line)
    return result



def collapse_blank_lines(lines: list[str]) -> list[str]:
    """合并连续空行（最多保留 1 个）"""
    result = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank:
            if not prev_blank:
                result.append("")
            prev_blank = True
        else:
            prev_blank = False
            result.append(line)
    return result


def split_long_paragraphs(text: str, max_chars: int = MAX_PARAGRAPH_CHARS) -> str:
    """超过 max_chars 的段落在句号处强制换段，消灭文字墙。保护时间头。"""
    blocks = text.split('\n\n')
    result = []
    for block in blocks:
        stripped = block.strip()
        # 保护时间头和短段落
        if TIME_HEADER_RE.match(stripped) or len(stripped) <= max_chars:
            result.append(block)
            continue
        # 按句号切分，重新组段
        sentences = SENTENCE_SPLIT_RE.split(stripped)
        sentences = [s.strip() for s in sentences if s.strip()]
        current_para = []
        current_len = 0
        sub_paras = []
        for sent in sentences:
            if current_len + len(sent) > max_chars and current_para:
                sub_paras.append(''.join(current_para))
                current_para = []
                current_len = 0
            current_para.append(sent)
            current_len += len(sent)
        if current_para:
            sub_paras.append(''.join(current_para))
        result.append('\n\n'.join(sub_paras))
    return '\n\n'.join(result)


def bold_keywords(text: str) -> str:
    """自动加粗英文专有名词和高频中文术语，提升扫读效率。

    策略：
    - 英文：2+ 字母的非常见词、驼峰/全大写词、产品名模式
    - 中文：全文出现 3+ 次的 2-4 字术语（通过简单频率统计）
    """
    lines = text.split('\n')
    result_lines = []

    # 第一步：提取英文专有名词候选
    # 匹配：首字母大写词、全大写词、驼峰词、带连字符的产品名
    english_proper_re = re.compile(
        r'\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*'  # CamelCase 或 Title Case
        r'|[A-Z]{2,}'                                  # 全大写（API, MCP, AI）
        r'|[a-zA-Z]+(?:[-\.][a-zA-Z]+)+)\b'           # 连字符/点分（stream-deck, server.py）
    )

    # 第二步：用 n-gram 滑动窗口统计中文高频术语（2-4字）
    chinese_chars_only = re.sub(r'[^\u4e00-\u9fff]', ' ', text)
    all_chinese_terms = []
    for segment in chinese_chars_only.split():
        for n in range(2, 5):  # 2字、3字、4字
            for i in range(len(segment) - n + 1):
                all_chinese_terms.append(segment[i:i+n])
    term_counts = Counter(all_chinese_terms)
    # 过滤：出现 3+ 次、排除太常见的词
    common_chinese_skip = {
        '然后', '但是', '因为', '所以', '就是', '还是', '这个', '那个',
        '什么', '怎么', '可以', '没有', '不是', '我们', '他们', '你们',
        '一个', '这样', '那样', '知道', '觉得', '应该', '现在', '的话',
        '比如', '比如说', '东西', '还有', '而且', '已经', '不要', '需要',
        '问题', '时候', '地方', '意思', '明白', '为什么', '怎么样',
        '好用', '好的', '不好', '很好', '喜欢', '功能', '核心',
    }
    # 取 3+ 次出现的，但去掉子串被更长术语覆盖的情况
    freq_terms = [
        (term, count) for term, count in term_counts.items()
        if count >= 3 and term not in common_chinese_skip and len(term) >= 2
    ]
    # 按长度降序排，长词优先
    freq_terms.sort(key=lambda x: (-len(x[0]), -x[1]))
    high_freq_terms = set()
    for term, _ in freq_terms:
        # 如果这个词已被一个更长的已选词完全包含，则跳过
        if any(term in longer for longer in high_freq_terms if len(longer) > len(term)):
            continue
        high_freq_terms.add(term)

    for line in lines:
        stripped = line.strip()
        # 保护时间头、空行、已有加粗
        if not stripped or TIME_HEADER_RE.match(stripped) or stripped.startswith('#'):
            result_lines.append(line)
            continue

        # 加粗英文专有名词
        def bold_english(match):
            word = match.group(0)
            if word.lower() in COMMON_ENGLISH_SKIP:
                return word
            if len(word) < 2:
                return word
            return f'**{word}**'

        line = english_proper_re.sub(bold_english, line)

        # 加粗高频中文术语（只加粗首次出现在本行的）
        for term in high_freq_terms:
            if term in line and f'**{term}**' not in line:
                line = line.replace(term, f'**{term}**', 1)

        # 清理可能的双重加粗 ****term****
        line = re.sub(r'\*{4,}', '**', line)

        result_lines.append(line)

    return '\n'.join(result_lines)


# ── 纠错替换 ─────────────────────────────────────────────
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
    """Step 9: 从 corrections.json 读取纠错规则，强制替换。
    
    不管转写引擎怎么写，到这一步一律改对。
    保护时间头（## HH:MM）行不被替换。
    """
    corrections = load_corrections()
    if not corrections:
        return text
    
    lines = text.split('\n')
    result = []
    replaced_count = 0
    
    for line in lines:
        # 保护时间头
        if TIME_HEADER_RE.match(line.strip()):
            result.append(line)
            continue
        
        for c in corrections:
            wrong = c.get('wrong', '')
            right = c.get('right', '')
            if wrong and right and wrong in line:
                line = line.replace(wrong, right)
                replaced_count += 1
        
        result.append(line)
    
    if replaced_count > 0:
        print(f"  ✓ 纠错替换: {replaced_count} 处", file=sys.stderr)
    
    return '\n'.join(result)


def sync_correction_to_vocab(wrong: str, right: str, context: str = ''):
    """将纠正同步写入 vocab.txt（事前预防层）"""
    vocab_file = Path(__file__).resolve().parent.parent.parent / 'resources' / 'vocab.txt'
    if not vocab_file.exists():
        return
    
    existing = vocab_file.read_text(encoding='utf-8')
    
    # 避免重复添加
    if right in existing:
        return
    
    desc = f"不是\"{wrong}\"" + (f"，{context}" if context else "")
    entry = f"{right} | {desc}\n"
    
    # 追加到 "常见音近易错词" 部分
    if '# ── 常见音近易错词' in existing:
        existing = existing.rstrip() + '\n' + entry
    else:
        existing = existing.rstrip() + '\n\n# ── 常见音近易错词（自动添加）──────────────────────────────────\n' + entry
    
    vocab_file.write_text(existing, encoding='utf-8')


def clean_text(text: str) -> str:
    """完整清洗流程。

    设计原则：
    - 只降噪，不改语义
    - 不加粗、不改词（除纠错词典）、不删脏话（真实语气是上下文证据）
    - 保留自然分段和对话节奏
    """
    # Step 0: 先按段剔除明显歌词/音乐口播
    text = remove_lyric_sentences(text)

    # Step 1: 清除 Gemini 系统前缀/机械回复
    text = remove_ai_preamble(text)

    # Step 2: 清除 Gemini 输出的 [音乐] 标记及其前后碎片
    text = remove_music_markers(text)

    # 注意：不过滤脏话。脏话是真实语气证据，对理解用户情绪和场景有价值。

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

    # 注意：不加粗关键词。** 标记会干扰下游场景切分和 intent 提取。

    return result


def main():
    if len(sys.argv) not in {2, 3}:
        print("用法: python3 clean.py <input.txt> [output.txt]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) == 3 else None

    if not input_path.exists():
        print(f"文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding='utf-8')

    # 统计清洗前
    before_chars = len(text.replace('\n', '').replace(' ', ''))

    cleaned = clean_text(text)

    # 统计清洗后
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
