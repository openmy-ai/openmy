#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from daytape.domain.models import SceneBlock


TIME_HEADER_RE = re.compile(r'^##\s+(\d{1,2}:\d{2})')


def parse_time_segments(markdown: str) -> list[dict]:
    """把带 ## HH:MM 的 markdown 切成时间段。"""
    segments = []
    current_time = None
    current_lines = []

    for line in markdown.split('\n'):
        match = TIME_HEADER_RE.match(line.strip())
        if match:
            if current_time is not None:
                text = '\n'.join(current_lines).strip()
                if text:
                    segments.append({"time": current_time, "text": text})
            current_time = match.group(1)
            current_lines = []
        elif current_time is not None:
            current_lines.append(line)

    if current_time is not None:
        text = '\n'.join(current_lines).strip()
        if text:
            segments.append({"time": current_time, "text": text})

    if not segments:
        text = markdown.strip()
        if text:
            segments.append({"time": "00:00", "text": text})

    return segments


def split_into_scenes(segments: list[dict]) -> list[SceneBlock]:
    """当前第一版：每个时间段就是一个场景块。"""
    scenes = []
    for index, seg in enumerate(segments):
        scenes.append(
            SceneBlock(
                scene_id=f"s{index + 1:02d}",
                time_start=seg["time"],
                time_end=seg["time"],
                text=seg["text"],
                preview=seg["text"][:100].replace('\n', ' '),
            )
        )

    for index in range(len(scenes) - 1):
        scenes[index].time_end = scenes[index + 1].time_start

    return scenes


def segment(markdown: str) -> list[SceneBlock]:
    return split_into_scenes(parse_time_segments(markdown))


def main() -> None:
    parser = argparse.ArgumentParser(description='Segment cleaned markdown into scene blocks.')
    parser.add_argument('input_file', help='Markdown transcript file')
    parser.add_argument('--output', '-o', help='Output JSON path')
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

    scenes = segment(markdown)
    output_path = Path(args.output) if args.output else input_path.with_suffix('.segments.json')
    output_path.write_text(
        json.dumps([asdict(scene) for scene in scenes], ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'✓ 输出: {output_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
