#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from google import genai

from openmy.config import GEMINI_MODEL, DISTILL_TEMPERATURE, DISTILL_THINKING_LEVEL

def summarize_scene(text: str, api_key: str, model: str) -> str:
    client = genai.Client(api_key=api_key)
    prompt = (
        f'你是一个录音日志的摘要助手。请用自然语言概括以下录音片段，要求：\n'
        f'1. 用 2-5 句话完整概括这段录音的内容，不要只说一句话\n'
        f'2. 保留关键人物（谁在说话、提到了谁）\n'
        f'3. 保留具体事件和话题（聊了什么、做了什么、去了哪里）\n'
        f'4. 如果有有趣的观点或金句，用引号保留原话\n'
        f'5. 如果有待办事项或决定，明确写出来\n'
        f'6. 用大白话写，像跟朋友转述今天发生了什么一样\n'
        f'7. 总字数控制在 50-150 字之间\n\n'
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
        scene['summary'] = summarize_scene(text, api_key, model)
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