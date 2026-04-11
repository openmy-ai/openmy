#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from openmy.config import get_llm_api_key, get_stage_llm_model
from openmy.domain.models import RoleTag, SceneBlock, ScreenContext
from openmy.providers.registry import ProviderRegistry
from openmy.services.segmentation.segmenter import segment


ROLE_LABELS = {
    'ai': '跟AI说',
    'merchant': '跟商家',
    'pet': '跟宠物',
    'self': '自言自语',
    'interpersonal': '跟人聊',
    'uncertain': '不确定',
}

SOURCE_LABELS = {
    'declared': '亲口说的',
    'inherited': '接着上文',
    'rule_matched': '一看就知道',
    'model_inferred': 'AI判断',
    'human_confirmed': '你确认的',
}

DECLARATION_PATTERNS = [
    (r'(报告老婆|给老婆|跟老婆|老婆[，,]|宝贝[，,]|亲爱的|好女)', 'interpersonal', '亲口说了老婆/伴侣', '老婆'),
    (r'(报告老公|给老公|跟老公|老公[，,])', 'interpersonal', '亲口说了老公/伴侣', '老公'),
    (r'(妈[，,]|给我妈|跟我妈)', 'interpersonal', '亲口说了妈妈', '妈妈'),
    (r'(爸[，,]|给我爸|跟我爸)', 'interpersonal', '亲口说了爸爸', '爸爸'),
    (r'(兄弟[，,]|哥[，,]|姐[，,])', 'interpersonal', '亲口叫了朋友称呼', '朋友'),
    (r'(对\s*AI|跟\s*AI|告诉\s*AI|备忘|小小得|主家你好)', 'ai', '亲口对AI说话', 'AI助手'),
    (r'(跟商家|给商家|跟客服|找客服|老板[，,]\s*来|服务员|你好.*点[菜餐单]|买单|结[账帐])', 'merchant', '亲口提到商家/服务员', '商家'),
    (r'(乖[，,]\s*[坐别过来]|别叫[了啦]?[，。]|[狗猫][，,]\s*[来过坐]|嗨[，,]\s*小狗)', 'pet', '亲口跟宠物说话', '宠物'),
]
COMPILED_DECLARATIONS = [
    (re.compile(pattern, re.IGNORECASE), role, evidence, addr)
    for pattern, role, evidence, addr in DECLARATION_PATTERNS
]

KEYWORD_RULES = {
    'ai': [
        'Claude', 'GPT', 'ChatGPT', 'Gemini', 'Codex',
        'prompt', '模型', '代码', '上下文', 'API', 'token', '总结一下',
        '改一下代码', '跑一下', 'skill', 'MCP', 'Antigravity', 'StreamDeck', 'Stream Deck',
    ],
    'merchant': [
        '下单', '退款', '发票', '物流', '快递', '预约', '多少钱',
        '几折', '打折', '结账', '买单', '扫码', '付款', '外卖',
        '配送', '收货', '退货', '售后', '差评', '好评', '你这边', '你们店', '你们家',
    ],
    'pet': ['遛狗', '狗粮', '猫粮', '铲屎'],
    'self': ['待会儿', '我得', '先把这个', '备忘', '反思', '我的判断是'],
}

ROLE_SIGNAL_WORDS = {
    '老婆', '老公', '宝贝', '亲爱的', '好女', '爸', '妈',
    '爷', '奶', '姥', '姥爷', '师傅', '老板', '客服',
    '服务员', '兄弟', '哥', '姐', '大爷', '大妈',
    '乖', '坐下', '别叫', '过来', '小狗', '小猫', '毛孩子',
    '小小得', '主家你好', '回来', '记一下', '报告', '给你', '帮我', '买单',
    '结账', '谢谢', '你好', '再见',
}


def check_declarations(text: str) -> Optional[tuple[str, float, str, str]]:
    for pattern, role, evidence, addr in COMPILED_DECLARATIONS:
        if pattern.search(text):
            return (role, 0.95, evidence, addr)
    return None


def check_keyword_rules(text: str) -> Optional[tuple[str, float, str, list[str]]]:
    scores: dict[str, tuple[int, list[str]]] = {}
    for role, keywords in KEYWORD_RULES.items():
        matched = []
        for keyword in keywords:
            if re.search(re.escape(keyword), text, re.IGNORECASE):
                matched.append(keyword)
        if matched:
            scores[role] = (len(matched), matched)

    if not scores:
        return None

    best_role = max(scores, key=lambda key: scores[key][0])
    count, matched = scores[best_role]
    if len(scores) > 1:
        confidence = min(0.6, 0.4 + count * 0.05)
    else:
        confidence = min(0.85, 0.5 + count * 0.1)
    evidence = f"命中关键词：{', '.join(matched[:5])}"
    return (best_role, confidence, evidence, matched)


def tag_scene_role(scene: SceneBlock, prev_role: Optional[RoleTag] = None) -> SceneBlock:
    text = scene.text
    ai_system_patterns = [
        re.compile(r'这就.*?为您.*?转写', re.IGNORECASE),
        re.compile(r'将为您.*?转写', re.IGNORECASE),
        re.compile(r'针对.*?音频文件.*?转写', re.IGNORECASE),
        re.compile(r'为你转写音频', re.IGNORECASE),
        re.compile(r'已经转写完成', re.IGNORECASE),
    ]
    normalized = text.replace('*', '').replace('`', '').replace('_', '')
    for pattern in ai_system_patterns:
        if pattern.search(normalized):
            scene.role = RoleTag(
                category='ai',
                scene_type='ai',
                scene_type_label=ROLE_LABELS['ai'],
                confidence=0.99,
                source='rule_matched',
                source_label='一看就知道',
                evidence='拦截到系统机械回复特征词',
                evidence_chain=['拦截到系统机械回复特征词'],
                needs_review=False,
            )
            return scene

    declared = check_declarations(text)
    if declared:
        role_key, confidence, evidence, addr = declared
        scene.role = RoleTag(
            category=role_key,
            entity_id=addr,
            relation_label=addr,
            scene_type=role_key,
            scene_type_label=ROLE_LABELS[role_key],
            addressed_to=addr,
            confidence=confidence,
            source='declared',
            source_label='亲口说的',
            evidence=evidence,
            evidence_chain=[evidence],
        )
        return scene

    ruled = check_keyword_rules(text)

    if prev_role and prev_role.scene_type != 'uncertain' and prev_role.confidence >= 0.7:
        keyword_can_override = False
        if ruled:
            rule_role, _rule_conf, _rule_evidence, rule_matched = ruled
            if len(rule_matched) >= 3 and rule_role != prev_role.scene_type:
                keyword_can_override = True

        if not keyword_can_override:
            inherited_confidence = max(0.4, prev_role.confidence - 0.15)
            scene.role = RoleTag(
                category=prev_role.scene_type,
                entity_id=prev_role.addressed_to,
                relation_label=prev_role.addressed_to,
                scene_type=prev_role.scene_type,
                scene_type_label=prev_role.scene_type_label,
                addressed_to=prev_role.addressed_to,
                confidence=inherited_confidence,
                source='inherited',
                source_label='接着上文',
                evidence=f"从前一段({prev_role.source_label})继承",
                evidence_chain=[f"从前一段({prev_role.source_label})继承"],
                needs_review=False,
            )
            return scene

    if ruled:
        role_key, confidence, evidence, matched = ruled
        addr_map = {'ai': 'AI助手', 'merchant': '商家', 'pet': '宠物', 'self': '自己'}
        addressed_to = addr_map.get(role_key, '')
        scene.role = RoleTag(
            category=role_key,
            entity_id=addressed_to,
            relation_label=addressed_to,
            scene_type=role_key,
            scene_type_label=ROLE_LABELS[role_key],
            addressed_to=addressed_to,
            confidence=confidence,
            source='rule_matched',
            source_label='一看就知道',
            evidence=evidence,
            evidence_chain=[evidence],
        )
        scene.keywords_matched = matched
        return scene

    if prev_role and prev_role.scene_type != 'uncertain' and prev_role.confidence >= 0.4:
        inherited_confidence = max(0.3, prev_role.confidence - 0.2)
        scene.role = RoleTag(
            category=prev_role.scene_type,
            entity_id=prev_role.addressed_to,
            relation_label=prev_role.addressed_to,
            scene_type=prev_role.scene_type,
            scene_type_label=prev_role.scene_type_label,
            addressed_to=prev_role.addressed_to,
            confidence=inherited_confidence,
            source='inherited',
            source_label='接着上文',
            evidence=f"从前一段({prev_role.source_label})继承",
            evidence_chain=[f"从前一段({prev_role.source_label})继承"],
            needs_review=inherited_confidence < 0.5,
        )
        return scene

    # ── 模型 fallback：规则都搞不定时，交给大模型判断 ──
    api_key = get_llm_api_key("roles")
    if api_key:
        model_result = infer_role_with_model(text, api_key)
        if model_result:
            cat = model_result.get('category', 'uncertain')
            addr = model_result.get('addressed_to', '')
            conf = min(0.75, max(0.2, model_result.get('confidence', 0.5)))
            if cat in ROLE_LABELS and cat != 'uncertain':
                scene.role = RoleTag(
                    category=cat,
                    entity_id=addr,
                    relation_label=addr,
                    scene_type=cat,
                    scene_type_label=ROLE_LABELS.get(cat, '不确定'),
                    addressed_to=addr,
                    confidence=conf,
                    source='model_inferred',
                    source_label='AI判断',
                    evidence=f"模型推断: {cat} → {addr}",
                    evidence_chain=[f"模型推断: {cat} → {addr}"],
                    needs_review=conf < 0.5,
                )
                return scene

    scene.role = RoleTag(
        category='uncertain',
        scene_type='uncertain',
        scene_type_label='不确定',
        confidence=0.0,
        source='uncertain',
        source_label='不确定',
        evidence='没有足够线索判断',
        evidence_chain=['没有足够线索判断'],
        needs_review=True,
    )
    return scene


def infer_role_with_model(text: str, api_key: str, model: str | None = None) -> dict | None:
    """调当前默认 LLM provider 判断这段话在跟谁说。只在规则层全部失败时调用。"""
    prompt = f"""分析下面这段语音转写文本，判断说话人在跟谁说话。

返回一个 JSON 对象，格式：
{{"category": "...", "addressed_to": "...", "confidence": 0.0-1.0}}

category 只能是以下之一：
- "ai" — 在跟 AI 助手说话（Claude、GPT、Gemini 等）
- "merchant" — 在跟商家/服务员/客服说话
- "pet" — 在跟宠物说话
- "self" — 自言自语、备忘、录任务记录
- "interpersonal" — 在跟人聊天（朋友、家人、同事）

addressed_to 填具体对象，比如"朋友"、"二哥"、"老婆"、"AI助手"。如果不确定是谁，填最合理的猜测。

confidence 表示你多确定，0.0 完全不确定，1.0 非常确定。

只返回 JSON，不要加其他内容。

---

{text[:2000]}"""

    try:
        provider = ProviderRegistry.from_env().get_llm_provider(
            stage="roles",
            api_key=api_key,
            model=model or get_stage_llm_model("roles"),
        )
        raw = provider.generate_text(
            task="role inference",
            prompt=prompt,
            model=model,
        ).strip()
        # 清理 markdown 代码块包裹
        if raw.startswith('```'):
            raw = re.sub(r'^```\w*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
        return json.loads(raw)
    except Exception:
        return None


def tag_all_scenes(scenes: list[SceneBlock]) -> list[SceneBlock]:
    prev_role: Optional[RoleTag] = None
    for scene in scenes:
        tag_scene_role(scene, prev_role)
        prev_role = scene.role
    return scenes


def apply_screen_context_role_adjustments(scene: SceneBlock) -> SceneBlock:
    context = getattr(scene, "screen_context", None)
    if not context or not context.aligned:
        return scene

    tags = set(context.tags or [])
    role = scene.role
    summary = context.summary or context.primary_app or "屏幕上下文"

    def _set_role(role_key: str, confidence: float, evidence: str) -> None:
        role.category = role_key
        role.scene_type = role_key
        role.scene_type_label = ROLE_LABELS.get(role_key, "不确定")
        role.confidence = confidence
        role.source = "screen_hint"
        role.source_label = "屏幕语境"
        role.evidence = evidence
        role.evidence_chain = [evidence]
        role.needs_review = confidence < 0.6

    if role.scene_type == "uncertain":
        if "development" in tags:
            _set_role("self", 0.55, f"屏幕语境显示开发语境：{summary}")
        elif "communication" in tags:
            _set_role("interpersonal", 0.55, f"屏幕语境显示人与人沟通：{summary}")
        elif {"merchant", "shopping", "payment"} & tags:
            _set_role("merchant", 0.55, f"屏幕语境显示交易或商家场景：{summary}")
        return scene

    if role.scene_type == "self" and "development" in tags:
        role.confidence = min(0.9, max(role.confidence, 0.65))
        role.evidence_chain.append(f"屏幕语境验证：{summary}")
        return scene

    if role.scene_type == "interpersonal" and "communication" in tags:
        role.confidence = min(0.9, max(role.confidence, 0.7))
        role.evidence_chain.append(f"屏幕语境验证：{summary}")
        return scene

    if role.scene_type == "merchant" and {"merchant", "shopping", "payment"} & tags:
        role.confidence = min(0.9, max(role.confidence, 0.7))
        role.evidence_chain.append(f"屏幕语境验证：{summary}")
        return scene

    conflict = False
    if role.scene_type == "interpersonal" and {"merchant", "shopping", "payment"} & tags:
        conflict = True
    elif role.scene_type == "merchant" and "communication" in tags:
        conflict = True
    elif role.scene_type == "ai" and {"merchant", "communication"} & tags:
        conflict = True

    if conflict:
        role.needs_review = True
        role.evidence_chain.append(f"⚠️ 屏幕语境冲突：{summary}")
        context.evidence_conflict = True
    return scene


def resolve_roles(
    scenes: list[SceneBlock],
    date_str: str | None = None,
    screen_client=None,
) -> list[SceneBlock]:
    scenes = tag_all_scenes(scenes)
    for scene in scenes:
        scene.screen_sessions = []
        scene.screen_context = ScreenContext()
    if screen_client:
        try:
            from openmy.services.screen_recognition.enrich import enrich_scenes_with_screen_context
            from openmy.services.screen_recognition.provider import ScreenContextProvider
            from openmy.services.screen_recognition.settings import load_screen_context_settings

            provider = ScreenContextProvider(
                client=screen_client,
                settings=load_screen_context_settings(),
            )
            scenes = enrich_scenes_with_screen_context(scenes, provider, date_str)
            scenes = [apply_screen_context_role_adjustments(scene) for scene in scenes]
        except Exception:
            pass
    return scenes


def compute_stats(scenes: list[SceneBlock]) -> dict:
    distribution: dict[str, int] = {}
    review_count = 0
    for scene in scenes:
        addressed_to = scene.role.addressed_to or '未识别'
        distribution[addressed_to] = distribution.get(addressed_to, 0) + 1
        if scene.role.needs_review:
            review_count += 1
    return {
        'total_scenes': len(scenes),
        'role_distribution': distribution,
        'needs_review_count': review_count,
    }


def scenes_to_dict(scenes: list[SceneBlock]) -> dict:
    return {
        'scenes': [asdict(scene) for scene in scenes],
        'stats': compute_stats(scenes),
        'role_labels': ROLE_LABELS,
        'source_labels': SOURCE_LABELS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='场景切分 + 混合角色归因')
    parser.add_argument('input_file', help='清洗后的 Markdown (YYYY-MM-DD.md)')
    parser.add_argument('--output', '-o', help='输出 scenes.json 路径（默认同目录）')
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f'文件不存在: {input_path}', file=sys.stderr)
        raise SystemExit(1)

    markdown = input_path.read_text(encoding='utf-8')
    if '---' in markdown:
        parts = markdown.split('---', 2)
        if len(parts) >= 3:
            markdown = parts[2].strip()

    scenes = resolve_roles(segment(markdown))
    if args.output:
        output_path = Path(args.output)
    else:
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', input_path.stem)
        date_str = date_match.group(1) if date_match else 'unknown'
        output_path = input_path.parent / f'{date_str}.scenes.json'

    result = scenes_to_dict(scenes)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    stats = result['stats']
    print(f"✓ 场景切分: {stats['total_scenes']} 个场景块", file=sys.stderr)
    print(f"✓ 角色分布: {json.dumps(stats['role_distribution'], ensure_ascii=False)}", file=sys.stderr)
    if stats['needs_review_count'] > 0:
        print(f"⚠️ 待确认: {stats['needs_review_count']} 个场景需要你过一眼", file=sys.stderr)
    print(f'✓ 输出: {output_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
