#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from google import genai

DEFAULT_MODEL = 'gemini-2.5-flash'

def summarize_scene(text: str, api_key: str, model: str) -> str:
    client = genai.Client(api_key=api_key)
    prompt = f'请用一句大白话（不超过20个字）总结以下录音片段的核心语义：\n\n{text}'
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(temperature=0.2)
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
    parser.add_argument('--model', default=DEFAULT_MODEL)
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