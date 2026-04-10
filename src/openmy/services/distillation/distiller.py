#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from google import genai

from openmy.config import GEMINI_MODEL, DISTILL_TEMPERATURE, DISTILL_THINKING_LEVEL

def summarize_scene(text: str, api_key: str, model: str, role_info: str = "") -> str:
    client = genai.Client(api_key=api_key)

    role_hint = ""
    if role_info:
        role_hint = f"说话人在跟{role_info}说话。用具体的称呼，不要写'大家''有人''说话人'。\n"

    prompt = (
        f'这是一段个人录音日记。帮我提炼要点，写给我自己看的。\n\n'
        f'{role_hint}'
        f'要求：\n'
        f'1. 只写干货，不写过渡句\n'
        f'2. 1-3 句话，每句话必须有具体信息\n'
        f'3. 用"我"做主语，不要用第三人称\n'
        f'4. 如果有金句或决定，用引号保留原话\n'
        f'5. 不要写"今天""首先""接着"这种过渡词\n'
        f'6. 总字数控制在 30-80 字\n\n'
        f'录音原文：\n{text}'
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "temperature": DISTILL_TEMPERATURE,
            "thinking_config": {"thinking_level": DISTILL_THINKING_LEVEL},
        },
    )
    return response.text.strip().replace('**', '').replace('\n', ' ')

def distill_scenes(scenes_path: Path, api_key: str, model: str) -> dict:
    data = json.loads(scenes_path.read_text(encoding='utf-8'))
    for scene in data.get('scenes', []):
        if scene.get('summary'):
            continue
        text = scene.get('text', '').strip()
        if not text:
            scene['summary'] = ''
            continue
        role = scene.get('role', {})
        addressed_to = role.get('addressed_to', '')
        scene['summary'] = summarize_scene(text, api_key, model, role_info=addressed_to)
    scenes_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data

def main() -> int:
    parser = argparse.ArgumentParser(description='Distill scene summaries with Gemini API.')
    parser.add_argument('scenes_json', help='Path to scenes.json')
    parser.add_argument('--model', default=GEMINI_MODEL)
    parser.add_argument('--api-key-env', default='GEMINI_API_KEY')
    args = parser.parse_args()

    api_key = os.getenv(args.api_key_env, '').strip()
    if not api_key:
        print(f'缺少环境变量: {args.api_key_env}', file=sys.stderr)
        return 1

    scenes_path = Path(args.scenes_json)
    if not scenes_path.exists():
        print(f'文件不存在: {scenes_path}', file=sys.stderr)
        return 1

    try:
        distill_scenes(scenes_path, api_key, args.model)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())