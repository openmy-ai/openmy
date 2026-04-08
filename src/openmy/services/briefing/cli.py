#!/usr/bin/env python3
"""Daily Briefing CLI."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_ROOT = ROOT / "data"


def main() -> None:
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = date.today().isoformat()

    scenes_path = DATA_ROOT / date_str / "scenes.json"
    output_path = DATA_ROOT / date_str / "daily_briefing.json"

    screenpipe = None
    try:
        from openmy.adapters.screenpipe.client import ScreenpipeClient

        client = ScreenpipeClient()
        if client.is_available():
            screenpipe = client
            print("🖥️ Screenpipe 已连接")
        else:
            print("🖥️ Screenpipe 未检测到（仅使用语音数据）")
    except Exception:
        print("🖥️ Screenpipe 未检测到（仅使用语音数据）")

    from openmy.services.briefing.generator import generate_briefing, save_briefing

    print(f"📅 生成 {date_str} 的 Daily Briefing...")
    briefing = generate_briefing(scenes_path, date_str, screenpipe)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_briefing(briefing, output_path)

    print(f"✅ 已生成: {output_path}")
    print(f"   📊 {briefing.total_scenes} 个场景 | {briefing.total_words} 字")
    print(f"   👥 互动: {', '.join(briefing.people_interaction_map.keys()) or '无'}")
    print(f"   📱 Screenpipe: {'已融合' if briefing.screenpipe_available else '未使用'}")
    if briefing.work_sessions:
        top_apps = list(briefing.work_sessions.items())[:3]
        print(f"   💻 Top Apps: {', '.join(f'{name}({duration})' for name, duration in top_apps)}")
    print(f"   📝 摘要: {briefing.summary}")


if __name__ == "__main__":
    main()
