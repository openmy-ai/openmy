#!/usr/bin/env python3
"""
extract.py — 从每日上下文转写中提取结构化摘要

读取带时间戳的清洗后 Markdown（YYYY-MM-DD.md），调 Gemini 提取：
  - 每日摘要（3句话）
  - 事件列表（时间+项目+摘要）
  - 决策记录
  - 待办事项
  - 灵感/想法

输出：
  - YYYY-MM-DD.meta.json  → 结构化数据（供外脑 UI 读取）
  - Vault 事件流 jsonl     → CC 启动自动读
  - Vault 日志 md          → 每日摘要
"""

import argparse
import json
import os
import re
import ssl
import sys
from datetime import datetime
from pathlib import Path

# ── Gemini API 配置 ──────────────────────────────────────

DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

EXTRACT_PROMPT = """你是一个个人助手，需要从用户一天的口述录音转写中提取结构化信息。

业务背景：这些转写文本来自一个"每日上下文归档系统"。说话人每天会在不同场景之间切换，常见场景包括：跟伴侣/老婆聊天、跟家人、跟朋友、跟商家、跟AI、跟宠物说话，以及自言自语的任务记录。

文本中的 ## HH:MM 是录制时间标记，代表该段内容的录制时间。

请从以下转写文本中提取：

1. **每日摘要**：用 3 句大白话总结这一天干了什么
2. **事件列表**：今天做了什么有意义的事，每个事件包含时间、关联项目（如有）、一句话摘要
3. **决策记录**：做了什么决定，包含项目名、决策内容、理由
4. **待办事项**：提到要做但还没做的事，包含任务描述、优先级(high/medium/low)、关联项目
5. **灵感/想法**：有价值的想法、观察、反思
6. **角色线索**：提取每个时间段的"说话场景"信息，包含：
   - scene_type（场景类型）：跟AI说 / 跟商家 / 跟宠物 / 自言自语 / 跟人聊 / 不确定
   - addressed_to（对谁说的）：具体对象，如"老婆""商家""AI助手""狗"等
   - about（在讲什么/谁）：这段话的主题
   - confidence（置信度）：0.0 到 1.0
   - source（判定依据类型）：亲口说的 / 一看就知道 / 接着上文 / 不确定
   - evidence（证据）：一句话说明
   - needs_review（是否要确认）：true/false

注意：
- 忽略纯闲聊、背景音乐、生活琐事（除非包含有意义的决策或待办）
- 项目名用简短中文，如"公众号"、"技能书"、"外脑"
- 如果无法判断项目，project 填空字符串
- 文本里出现“你”时，不要武断指定对象；只有上下文明确时才标注具体角色，否则标为“未确定”
- 角色判断优先做大类，不要过度细分到具体个人
- 明确区分“文本明确说出”与“根据上下文弱推断”

输出严格 JSON 格式（不要 markdown 代码块）：
{
  "daily_summary": "3句话总结",
  "events": [{"time": "HH:MM", "project": "项目名", "summary": "一句话"}],
  "decisions": [{"project": "项目名", "what": "决策内容", "why": "理由"}],
  "todos": [{"task": "任务描述", "priority": "high/medium/low", "project": "项目名"}],
  "insights": [{"topic": "主题", "content": "内容"}],
  "role_hints": [{"time": "HH:MM", "role": "伴侣|家人|朋友|商家|AI|宠物|自己|未确定", "basis": "explicit|inferred", "confidence": 0.0, "evidence": "一句话依据"}]
}
"""


def call_gemini(text: str, api_key: str, model: str = DEFAULT_MODEL) -> dict | None:
    """调 Gemini API 提取结构化数据"""
    import urllib.request
    import urllib.error
    import certifi

    url = f"{API_BASE}/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [{
            "parts": [
                {"text": EXTRACT_PROMPT},
                {"text": f"以下是今天的录音转写：\n\n{text}"}
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=120, context=ssl_context) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Gemini API 错误: {e.code} {e.reason}", file=sys.stderr)
        try:
            body = e.read().decode("utf-8")
            print(body[:500], file=sys.stderr)
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        return None

    # 解析响应
    try:
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
        # 去掉可能的 markdown 代码块包裹
        raw_text = re.sub(r'^```json\s*', '', raw_text.strip())
        raw_text = re.sub(r'\s*```$', '', raw_text.strip())
        return json.loads(raw_text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"解析 Gemini 响应失败: {e}", file=sys.stderr)
        print(f"原始响应: {json.dumps(result, ensure_ascii=False)[:500]}", file=sys.stderr)
        return None


def save_meta_json(data: dict, date: str, output_dir: str):
    """保存结构化数据为 .meta.json"""
    meta_path = Path(output_dir) / f"{date}.meta.json"
    meta_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"✓ 结构化数据: {meta_path}", file=sys.stderr)


def distribute_to_vault(data: dict, date: str, vault_path: str):
    """分发提取结果到 Obsidian Vault"""
    vault = Path(vault_path)

    # 1. 事件流 → 系统/事件流/YYYY-MM-DD/context.jsonl
    event_dir = vault / "系统" / "事件流" / date
    event_dir.mkdir(parents=True, exist_ok=True)
    event_file = event_dir / "context.jsonl"

    events = data.get("events", [])
    with open(event_file, "a", encoding="utf-8") as f:
        for event in events:
            entry = {
                "time": f"{date}T{event.get('time', '00:00')}:00+08:00",
                "actor": "context",
                "project": event.get("project", ""),
                "type": "口述记录",
                "summary": event.get("summary", "")
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if events:
        print(f"✓ 事件流: {len(events)} 条 → {event_file}", file=sys.stderr)

    # 2. 每日摘要 → 写入日志备注
    summary = data.get("daily_summary", "")
    if summary:
        log_dir = vault / "日志"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{date}-上下文.md"
        content = f"# {date} 上下文摘要\n\n{summary}\n"

        # 追加决策
        decisions = data.get("decisions", [])
        if decisions:
            content += "\n## 决策\n\n"
            for d in decisions:
                proj = f"【{d['project']}】" if d.get("project") else ""
                content += f"- {proj}{d.get('what', '')}"
                if d.get("why"):
                    content += f"（{d['why']}）"
                content += "\n"

        # 追加待办
        todos = data.get("todos", [])
        if todos:
            content += "\n## 待办\n\n"
            for t in todos:
                prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    t.get("priority", "medium"), "🟡"
                )
                proj = f"【{t['project']}】" if t.get("project") else ""
                content += f"- {prio} {proj}{t.get('task', '')}\n"

        # 追加灵感
        insights = data.get("insights", [])
        if insights:
            content += "\n## 灵感\n\n"
            for i in insights:
                content += f"- **{i.get('topic', '')}**: {i.get('content', '')}\n"

        log_file.write_text(content, encoding="utf-8")
        print(f"✓ 日志摘要: {log_file}", file=sys.stderr)

    # 3. 自动同步灵感和待办到收件箱
    inbox_file = vault / "收件箱" / "灵感速记.md"
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    inbox_appends = []
    
    todos = data.get("todos", [])
    if todos:
        for t in todos:
            prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.get("priority", "medium"), "🟡")
            proj = f"[{t['project']}] " if t.get("project") else ""
            inbox_appends.append(f"- [ ] {prio} {proj}{t.get('task', '')} _{date}_")
            
    insights = data.get("insights", [])
    if insights:
        for i in insights:
            inbox_appends.append(f"- 💡 **{i.get('topic', '')}**: {i.get('content', '')} _{date}_")
            
    if inbox_appends:
        with open(inbox_file, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(inbox_appends) + "\n")
        print(f"✓ 收件箱同步: {len(inbox_appends)} 条 → {inbox_file}", file=sys.stderr)

    # 4. 自动同步决策到复盘库
    decisions = data.get("decisions", [])
    if decisions:
        decision_file = vault / "日志" / "决策复盘库.md"
        decision_file.parent.mkdir(parents=True, exist_ok=True)
        if not decision_file.exists():
            decision_file.write_text("# 决策复盘库\n\n", encoding="utf-8")
            
        aesthetics_file = vault / "领域" / "个人IP" / "审美档案.md"
        
        with open(decision_file, "a", encoding="utf-8") as df:
            for d in decisions:
                proj = f"【{d['project']}】" if d.get("project") else ""
                entry = f"- **{date}** {proj}{d.get('what', '')} （{d.get('why', '')}）\n"
                df.write(entry)
                
                # 如果是设计相关的，同步到审美档案
                if d.get("project") in ["设计", "排版", "视觉", "小红书", "公众号", "配图", "审美", "封面"]:
                    if aesthetics_file.exists():
                        with open(aesthetics_file, "a", encoding="utf-8") as af:
                            af.write(f"\n- **{date} 视觉决策**：{d.get('what', '')} （{d.get('why', '')}）")
                            
        print(f"✓ 决策复盘同步: {len(decisions)} 条", file=sys.stderr)

    # 5. 终端输出待办清单
    if todos:
        print("\n📋 提取到的待办事项：", file=sys.stderr)
        for t in todos:
            prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                t.get("priority", "medium"), "🟡"
            )
            proj = f"[{t['project']}] " if t.get("project") else ""
            print(f"  {prio} {proj}{t.get('task', '')}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="从每日上下文转写中提取结构化摘要")
    parser.add_argument("input_file", help="清洗后的 Markdown 文件 (YYYY-MM-DD.md)")
    parser.add_argument("--date", help="日期 (YYYY-MM-DD)，默认从文件名推断")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini 模型 (默认: {DEFAULT_MODEL})")
    parser.add_argument("--vault-path", help="Obsidian Vault 路径，指定后自动分发到 Vault")
    parser.add_argument("--api-key", help="Gemini API key (或设置 GEMINI_API_KEY 环境变量)")
    parser.add_argument("--dry-run", action="store_true", help="只打印提取结果，不写入文件")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    # 推断日期
    date = args.date
    if not date:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', input_path.stem)
        if match:
            date = match.group(1)
        else:
            date = datetime.now().strftime("%Y-%m-%d")

    # API key
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("错误: 请设置 GEMINI_API_KEY 环境变量或使用 --api-key 参数", file=sys.stderr)
        sys.exit(1)

    # 读取输入
    text = input_path.read_text(encoding="utf-8")

    # 只取 --- 之后的正文（跳过 YAML 头部）
    if "---" in text:
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()
        elif len(parts) == 2:
            text = parts[1].strip()

    print(f"📖 读取 {input_path.name}: {len(text)} 字", file=sys.stderr)
    print(f"🤖 调用 Gemini ({args.model}) 提取结构化摘要...", file=sys.stderr)

    data = call_gemini(text, api_key, args.model)
    if not data:
        print("❌ 提取失败", file=sys.stderr)
        sys.exit(1)

    print(f"✓ 提取完成", file=sys.stderr)

    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    # 保存 meta.json
    output_dir = str(input_path.parent)
    save_meta_json(data, date, output_dir)

    # 分发到 Vault
    if args.vault_path:
        distribute_to_vault(data, date, args.vault_path)

    # 打印摘要
    print(f"\n📝 每日摘要: {data.get('daily_summary', '无')}", file=sys.stderr)
    print(f"📊 提取: {len(data.get('events', []))} 事件 | "
          f"{len(data.get('decisions', []))} 决策 | "
          f"{len(data.get('todos', []))} 待办 | "
          f"{len(data.get('insights', []))} 灵感", file=sys.stderr)


if __name__ == "__main__":
    main()
