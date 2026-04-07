#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from daytape.domain.models import RoleTag, SceneBlock
from daytape.services.segmentation.segmenter import segment


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
        'Claude', 'GPT', 'ChatGPT', 'Gemini', 'Codex', 'Screenpipe',
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
    '乖', '坐下', '别叫', '过来', '小狗', '小猫', '青维',
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


def tag_all_scenes(scenes: list[SceneBlock]) -> list[SceneBlock]:
    prev_role: Optional[RoleTag] = None
    for scene in scenes:
        tag_scene_role(scene, prev_role)
        prev_role = scene.role
    return scenes


def resolve_roles(
    scenes: list[SceneBlock],
    date_str: str | None = None,
    screenpipe_client=None,
) -> list[SceneBlock]:
    scenes = tag_all_scenes(scenes)
    if screenpipe_client:
        try:
            from daytape.services.screenpipe.hints import enrich_with_hints

            scenes = enrich_with_hints(scenes, screenpipe_client, date_str)
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
