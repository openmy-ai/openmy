# OpenMy CLI 统一命令行 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 OpenMy 的完整处理管线包装成一个美观的 CLI 工具，支持一条命令跑完全流程，也支持分步执行，终端输出带颜色、表格、进度条和图表。

**Architecture:** 新增 `src/openmy/cli.py` 作为统一入口，使用 `argparse` 做子命令路由，使用 `rich` 库做终端美化。每个子命令对应一个已有的 service 模块。不改动已有 service 层的逻辑，只做 CLI 包装。

**Tech Stack:** Python 3.10+, argparse（CLI 框架）, rich（终端美化：表格/面板/进度条/配色）

---

## 文件结构

| 文件 | 职责 |
|------|------|
| **[NEW]** `src/openmy/cli.py` | 统一 CLI 入口，子命令路由 + rich 格式化输出 |
| **[NEW]** `src/openmy/__main__.py` | `python -m openmy` 入口 |
| **[MODIFY]** `pyproject.toml` | 添加 `rich` 依赖 + `console_scripts` 入口 |
| **[NEW]** `tests/unit/test_cli.py` | CLI 单元测试 |

## 子命令设计

```
openmy run <date> [--audio <files...>]   # 全流程：转写→清洗→角色→蒸馏→日报
openmy clean <date>                      # 只清洗
openmy roles <date>                      # 切场景 + 角色归因
openmy distill <date>                    # 蒸馏摘要
openmy briefing <date>                   # 生成日报
openmy view <date>                       # 终端查看一天的概览
openmy status                            # 列出所有日期及处理状态
openmy correct <date> <错词> <正确写法>  # 终端纠错
```

## 美化要求（使用 rich）

- **进度条**：长任务（转写、蒸馏）用 `rich.progress.Progress` 显示进度
- **表格**：`openmy status` 输出 `rich.table.Table`，列：日期/场景数/字数/角色分布/处理阶段
- **面板**：`openmy view <date>` 用 `rich.panel.Panel` 展示每个时段的摘要卡片
- **颜色**：角色用不同颜色标识（AI=cyan, 商家=yellow, 老婆=magenta, 宠物=green, 自己=blue, 未识别=dim）
- **条形图**：角色分布用 `rich.columns` + 彩色方块 `█` 绘制横向条形图
- **Markdown 渲染**：`rich.markdown.Markdown` 渲染摘要文本
- **错误处理**：用 `rich.console.Console().print_exception()` 美化错误输出

---

## Chunk 1: 基础框架

### Task 1: 安装 rich 依赖 + 创建入口文件

**Files:**
- Modify: `pyproject.toml`
- Create: `src/openmy/__main__.py`

- [ ] **Step 1: 添加 rich 依赖到 pyproject.toml**

```toml
# pyproject.toml 的 dependencies 部分
dependencies = ["rich>=13.0"]
```

- [ ] **Step 2: 创建 __main__.py**

```python
from openmy.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 安装依赖**

Run: `cd ~/Desktop/周瑟夫的上下文 && pip install -e .`
Expected: 成功安装，rich 可用

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/openmy/__main__.py
git commit -m "feat: add rich dependency and __main__ entry point"
```

---

### Task 2: CLI 骨架 + status 子命令

**Files:**
- Create: `src/openmy/cli.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: 写 status 子命令的测试**

```python
# tests/unit/test_cli.py
import subprocess
import sys

def test_cli_status_runs():
    """openmy status 应该能跑通不报错"""
    result = subprocess.run(
        [sys.executable, "-m", "openmy", "status"],
        capture_output=True, text=True, timeout=10,
        cwd="项目根目录路径"
    )
    assert result.returncode == 0
    assert "日期" in result.stdout or "📅" in result.stdout

def test_cli_help():
    """openmy --help 应该输出帮助"""
    result = subprocess.run(
        [sys.executable, "-m", "openmy", "--help"],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0
    assert "openmy" in result.stdout.lower() or "OpenMy" in result.stdout
```

- [ ] **Step 2: 跑测试看失败**

Run: `pytest tests/unit/test_cli.py -v`
Expected: FAIL（cli.py 不存在）

- [ ] **Step 3: 实现 CLI 骨架 + status 命令**

```python
# src/openmy/cli.py
#!/usr/bin/env python3
"""OpenMy — 个人上下文引擎 CLI"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_ROOT = ROOT_DIR / "data"
LEGACY_ROOT = ROOT_DIR

# 角色颜色映射
ROLE_COLORS = {
    "AI助手": "cyan",
    "商家": "yellow",
    "老婆": "magenta",
    "宠物": "green",
    "自己": "blue",
    "朋友": "bright_blue",
    "未识别": "dim",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def find_all_dates() -> list[str]:
    """扫描所有可用日期"""
    dates: set[str] = set()
    if DATA_ROOT.exists():
        for child in DATA_ROOT.iterdir():
            if child.is_dir() and DATE_RE.match(child.name):
                dates.add(child.name)
    for path in LEGACY_ROOT.glob("*.md"):
        if path.name.endswith(".raw.md"):
            continue
        m = DATE_MD_RE.match(path.name)
        if m:
            dates.add(m.group(1))
    return sorted(dates, reverse=True)


def get_date_status(date: str) -> dict:
    """获取某一天的处理阶段"""
    day_dir = DATA_ROOT / date
    legacy = LEGACY_ROOT / f"{date}.md"

    status = {
        "date": date,
        "has_transcript": (day_dir / "transcript.md").exists() or legacy.exists(),
        "has_raw": (day_dir / "transcript.raw.md").exists() or (LEGACY_ROOT / f"{date}.raw.md").exists(),
        "has_scenes": (day_dir / "scenes.json").exists() or (LEGACY_ROOT / f"{date}.scenes.json").exists(),
        "has_briefing": (day_dir / "daily_briefing.json").exists(),
        "word_count": 0,
        "scene_count": 0,
        "role_distribution": {},
    }

    # 读字数
    transcript = day_dir / "transcript.md"
    if not transcript.exists():
        transcript = legacy
    if transcript.exists():
        content = transcript.read_text(encoding="utf-8")
        status["word_count"] = len(re.sub(r"\s+", "", content))

    # 读场景数据
    scenes_path = day_dir / "scenes.json"
    if not scenes_path.exists():
        scenes_path = LEGACY_ROOT / f"{date}.scenes.json"
    if scenes_path.exists():
        try:
            data = json.loads(scenes_path.read_text(encoding="utf-8"))
            status["scene_count"] = len(data.get("scenes", []))
            status["role_distribution"] = data.get("stats", {}).get("role_distribution", {})
        except Exception:
            pass

    return status


def stage_label(status: dict) -> str:
    """根据处理阶段返回状态标签"""
    if status["has_briefing"]:
        return "[green]✅ 完成[/green]"
    if status["has_scenes"]:
        return "[yellow]📊 已归因[/yellow]"
    if status["has_transcript"]:
        return "[blue]📝 已转写[/blue]"
    if status["has_raw"]:
        return "[dim]🎙️ 已录入[/dim]"
    return "[dim]❌ 无数据[/dim]"


def role_bar(distribution: dict, width: int = 20) -> str:
    """用彩色方块画角色分布条"""
    total = sum(distribution.values())
    if total == 0:
        return "[dim]—[/dim]"
    parts = []
    for role, count in sorted(distribution.items(), key=lambda x: -x[1]):
        color = ROLE_COLORS.get(role, "white")
        bar_len = max(1, round(count / total * width))
        parts.append(f"[{color}]{'█' * bar_len}[/{color}]")
    return "".join(parts)


def cmd_status(args: argparse.Namespace) -> int:
    """列出所有日期及处理状态"""
    dates = find_all_dates()
    if not dates:
        console.print("[dim]没有找到任何数据[/dim]")
        return 0

    table = Table(
        title="📅 OpenMy 数据总览",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("日期", style="bold")
    table.add_column("状态", justify="center")
    table.add_column("字数", justify="right")
    table.add_column("场景", justify="right")
    table.add_column("角色分布", min_width=20)

    for date in dates:
        s = get_date_status(date)
        table.add_row(
            date,
            stage_label(s),
            f"{s['word_count']:,}" if s["word_count"] else "—",
            str(s["scene_count"]) if s["scene_count"] else "—",
            role_bar(s["role_distribution"]),
        )

    console.print(table)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openmy",
        description="🎙️ OpenMy — 个人上下文引擎",
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # status
    sub.add_parser("status", help="列出所有日期及处理状态")

    # view
    p_view = sub.add_parser("view", help="终端查看某天的概览")
    p_view.add_argument("date", help="日期 YYYY-MM-DD")

    # clean
    p_clean = sub.add_parser("clean", help="清洗转写文本")
    p_clean.add_argument("date", help="日期 YYYY-MM-DD")

    # roles
    p_roles = sub.add_parser("roles", help="切场景 + 角色归因")
    p_roles.add_argument("date", help="日期 YYYY-MM-DD")

    # distill
    p_distill = sub.add_parser("distill", help="蒸馏摘要（需要 GEMINI_API_KEY）")
    p_distill.add_argument("date", help="日期 YYYY-MM-DD")

    # briefing
    p_brief = sub.add_parser("briefing", help="生成日报")
    p_brief.add_argument("date", help="日期 YYYY-MM-DD")

    # run (全流程)
    p_run = sub.add_parser("run", help="全流程处理")
    p_run.add_argument("date", help="日期 YYYY-MM-DD")
    p_run.add_argument("--audio", nargs="+", help="音频文件路径")
    p_run.add_argument("--skip-transcribe", action="store_true", help="跳过转写（使用已有 raw）")

    # correct
    p_correct = sub.add_parser("correct", help="纠正转写错词")
    p_correct.add_argument("date", help="日期 YYYY-MM-DD")
    p_correct.add_argument("wrong", help="错误写法")
    p_correct.add_argument("right", help="正确写法")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "status": cmd_status,
        # 其他命令在后续 Task 中实现
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    console.print(f"[yellow]命令 '{args.command}' 尚未实现[/yellow]")
    return 1
```

- [ ] **Step 4: 跑测试看通过**

Run: `pytest tests/unit/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: 手动验证 status 输出效果**

Run: `cd ~/Desktop/周瑟夫的上下文 && python -m openmy status`
Expected: 彩色表格，显示所有日期、状态、字数、角色分布条

- [ ] **Step 6: Commit**

```bash
git add src/openmy/cli.py tests/unit/test_cli.py
git commit -m "feat: openmy CLI skeleton with rich status command"
```

---

## Chunk 2: view 命令（终端美化核心）

### Task 3: view 子命令 — 终端查看某天概览

**Files:**
- Modify: `src/openmy/cli.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: 写 view 命令的测试**

```python
def test_cli_view_existing_date():
    """openmy view 2026-04-06 应该输出场景概览"""
    result = subprocess.run(
        [sys.executable, "-m", "openmy", "view", "2026-04-06"],
        capture_output=True, text=True, timeout=10,
        cwd="项目根目录路径"
    )
    assert result.returncode == 0
    # 应该包含时间信息
    assert "12:" in result.stdout or "13:" in result.stdout

def test_cli_view_nonexistent_date():
    """不存在的日期应该友好报错"""
    result = subprocess.run(
        [sys.executable, "-m", "openmy", "view", "1999-01-01"],
        capture_output=True, text=True, timeout=10,
        cwd="项目根目录路径"
    )
    assert result.returncode == 1
```

- [ ] **Step 2: 跑测试看失败**

Run: `pytest tests/unit/test_cli.py::test_cli_view_existing_date -v`
Expected: FAIL

- [ ] **Step 3: 实现 view 命令**

`cmd_view` 函数应该：
1. 读取 `scenes.json`，如果没有就读 `transcript.md` 直接按时间段展示
2. 每个场景用 `rich.panel.Panel` 展示：
   - 标题：时间 + 角色标签（带颜色）
   - 内容：摘要（如果有）+ 原文前 100 字预览（dim 色）
3. 底部用条形图展示角色分布
4. 如果有 `daily_briefing.json`，在顶部展示日报面板

```python
def cmd_view(args: argparse.Namespace) -> int:
    """终端查看某天概览"""
    date = args.date
    status = get_date_status(date)
    if not status["has_transcript"]:
        console.print(f"[red]❌ {date} 没有数据[/red]")
        return 1

    # 日报面板（如果有）
    briefing_path = DATA_ROOT / date / "daily_briefing.json"
    if briefing_path.exists():
        briefing = json.loads(briefing_path.read_text(encoding="utf-8"))
        console.print(Panel(
            briefing.get("summary", "无摘要"),
            title=f"📋 {date} 日报",
            border_style="magenta",
            padding=(1, 2),
        ))
        console.print()

    # 场景列表
    scenes_path = DATA_ROOT / date / "scenes.json"
    if not scenes_path.exists():
        scenes_path = LEGACY_ROOT / f"{date}.scenes.json"

    if scenes_path.exists():
        data = json.loads(scenes_path.read_text(encoding="utf-8"))
        scenes = data.get("scenes", [])
        for scene in scenes:
            time_start = scene.get("time_start", "")
            role = scene.get("role", {})
            role_label = role.get("addressed_to", "") or role.get("scene_type_label", "未识别")
            color = ROLE_COLORS.get(role_label, "white")
            summary = scene.get("summary", "")
            preview = scene.get("preview", scene.get("text", "")[:100])

            content_parts = []
            if summary:
                content_parts.append(summary)
            content_parts.append(f"[dim]{preview}[/dim]")

            console.print(Panel(
                "\n".join(content_parts),
                title=f"🕐 {time_start}  [{color}]{role_label}[/{color}]",
                title_align="left",
                border_style=color,
                padding=(0, 1),
            ))

        # 角色分布条形图
        dist = data.get("stats", {}).get("role_distribution", {})
        if dist:
            console.print()
            console.print("[bold]📊 角色分布[/bold]")
            total = sum(dist.values())
            max_bar = 30
            for role_name, count in sorted(dist.items(), key=lambda x: -x[1]):
                color = ROLE_COLORS.get(role_name, "white")
                bar_len = max(1, round(count / total * max_bar))
                pct = count / total * 100
                console.print(
                    f"  [{color}]{'█' * bar_len}[/{color}] "
                    f"{role_name} {count}段 ({pct:.0f}%)"
                )
    else:
        # 没有 scenes.json，直接显示转写文本
        transcript = DATA_ROOT / date / "transcript.md"
        if not transcript.exists():
            transcript = LEGACY_ROOT / f"{date}.md"
        content = transcript.read_text(encoding="utf-8")
        from rich.markdown import Markdown
        console.print(Panel(Markdown(content[:2000]), title=f"📝 {date} 转写文本"))

    return 0
```

- [ ] **Step 4: 跑测试看通过**

Run: `pytest tests/unit/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: 手动验证美化效果**

Run: `python -m openmy view 2026-04-06`
Expected: 彩色面板卡片 + 角色分布条形图

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: openmy view command with rich panels and role chart"
```

---

## Chunk 3: 处理命令（clean / roles / distill / briefing）

### Task 4: clean 子命令

**Files:**
- Modify: `src/openmy/cli.py`

- [ ] **Step 1: 写测试**

```python
def test_cli_clean_needs_date():
    result = subprocess.run(
        [sys.executable, "-m", "openmy", "clean"],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode != 0  # 缺少 date 参数
```

- [ ] **Step 2: 实现 clean 命令**

```python
def cmd_clean(args: argparse.Namespace) -> int:
    """清洗转写文本"""
    date = args.date
    day_dir = DATA_ROOT / date
    raw_path = day_dir / "transcript.raw.md"
    # 也查找旧格式
    if not raw_path.exists():
        raw_path = LEGACY_ROOT / f"{date}.raw.md"
    if not raw_path.exists():
        console.print(f"[red]❌ 找不到 {date} 的原始转写[/red]")
        return 1

    from openmy.services.cleaning.cleaner import clean_text

    with console.status("[bold green]🧹 清洗中..."):
        raw_text = raw_path.read_text(encoding="utf-8")
        cleaned = clean_text(raw_text)

    output_path = day_dir / "transcript.md"
    if not day_dir.exists():
        # 旧格式
        output_path = LEGACY_ROOT / f"{date}.md"
    output_path.write_text(cleaned, encoding="utf-8")

    before = len(re.sub(r"\s+", "", raw_text))
    after = len(re.sub(r"\s+", "", cleaned))
    console.print(f"[green]✅ 清洗完成[/green]: {before:,} → {after:,} 字 (去除 {before - after:,} 字)")
    return 0
```

- [ ] **Step 3: 跑测试 → Commit**

---

### Task 5: roles 子命令

**Files:**
- Modify: `src/openmy/cli.py`

- [ ] **Step 1: 实现 roles 命令**

```python
def cmd_roles(args: argparse.Namespace) -> int:
    """切场景 + 角色归因"""
    date = args.date
    # 找到 transcript.md
    transcript = DATA_ROOT / date / "transcript.md"
    if not transcript.exists():
        transcript = LEGACY_ROOT / f"{date}.md"
    if not transcript.exists():
        console.print(f"[red]❌ 找不到 {date} 的清洗后文本，先运行 openmy clean {date}[/red]")
        return 1

    from openmy.services.segmentation.segmenter import segment
    from openmy.services.roles.resolver import resolve_roles, scenes_to_dict

    with console.status("[bold cyan]🏷️ 场景切分 + 角色归因..."):
        markdown = transcript.read_text(encoding="utf-8")
        # 跳过文件头
        if "---" in markdown:
            parts = markdown.split("---", 2)
            if len(parts) >= 3:
                markdown = parts[2].strip()
        scenes = resolve_roles(segment(markdown), date_str=date)
        result = scenes_to_dict(scenes)

    # 输出到 scenes.json
    output_dir = DATA_ROOT / date
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "scenes.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = result["stats"]
    console.print(f"[green]✅ 角色归因完成[/green]: {stats['total_scenes']} 个场景")
    # 打印分布
    for role, count in sorted(stats["role_distribution"].items(), key=lambda x: -x[1]):
        color = ROLE_COLORS.get(role, "white")
        console.print(f"  [{color}]■[/{color}] {role}: {count} 段")
    if stats["needs_review_count"]:
        console.print(f"  [yellow]⚠️ {stats['needs_review_count']} 段需要人工确认[/yellow]")
    return 0
```

- [ ] **Step 2: 跑测试 → Commit**

---

### Task 6: distill 子命令

**Files:**
- Modify: `src/openmy/cli.py`

- [ ] **Step 1: 实现 distill 命令**

```python
def cmd_distill(args: argparse.Namespace) -> int:
    """蒸馏摘要"""
    import os
    date = args.date
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        console.print("[red]❌ 缺少 GEMINI_API_KEY 环境变量[/red]")
        return 1

    scenes_path = DATA_ROOT / date / "scenes.json"
    if not scenes_path.exists():
        console.print(f"[red]❌ 找不到 {date}/scenes.json，先运行 openmy roles {date}[/red]")
        return 1

    from openmy.services.distillation.distiller import distill_scenes
    from rich.progress import Progress

    data = json.loads(scenes_path.read_text(encoding="utf-8"))
    total = len([s for s in data.get("scenes", []) if not s.get("summary")])

    if total == 0:
        console.print(f"[green]✅ {date} 所有场景已有摘要，跳过[/green]")
        return 0

    console.print(f"[cyan]🧪 蒸馏 {total} 个场景...[/cyan]")
    with Progress() as progress:
        task = progress.add_task("蒸馏中...", total=total)
        for scene in data.get("scenes", []):
            if scene.get("summary"):
                continue
            text = scene.get("text", "").strip()
            if not text:
                scene["summary"] = ""
                progress.advance(task)
                continue
            from openmy.services.distillation.distiller import summarize_scene
            scene["summary"] = summarize_scene(text, api_key, "gemini-2.5-flash")
            progress.advance(task)

    scenes_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]✅ 蒸馏完成，{total} 个摘要已写入[/green]")
    return 0
```

- [ ] **Step 2: 跑测试 → Commit**

---

### Task 7: briefing 子命令

**Files:**
- Modify: `src/openmy/cli.py`

- [ ] **Step 1: 实现 briefing 命令**

包装已有的 `briefing/cli.py` 逻辑，但用 rich 美化输出。

- [ ] **Step 2: 跑测试 → Commit**

---

### Task 8: correct 子命令

**Files:**
- Modify: `src/openmy/cli.py`

- [ ] **Step 1: 实现 correct 命令**

```python
def cmd_correct(args: argparse.Namespace) -> int:
    """终端纠错"""
    from openmy.services.cleaning.cleaner import sync_correction_to_vocab
    # 1. 写入 corrections.json
    # 2. 替换 transcript.md 中的错词
    # 3. 同步到 vocab.txt
    # 4. 用 rich 展示替换了多少处
```

- [ ] **Step 2: 跑测试 → Commit**

---

## Chunk 4: 全流程 run 命令

### Task 9: run 全流程子命令

**Files:**
- Modify: `src/openmy/cli.py`

- [ ] **Step 1: 实现 run 命令**

```python
def cmd_run(args: argparse.Namespace) -> int:
    """全流程：转写 → 清洗 → 角色 → 蒸馏 → 日报"""
    date = args.date

    console.print(Panel(
        f"🎙️ OpenMy 全流程处理\n📅 日期: {date}",
        border_style="bright_blue",
    ))

    steps = [
        ("🧹 清洗", cmd_clean),
        ("🏷️ 角色归因", cmd_roles),
        ("🧪 蒸馏", cmd_distill),
        ("📋 日报", cmd_briefing),
    ]

    # 如果有音频文件且没有 --skip-transcribe，先转写
    if args.audio and not args.skip_transcribe:
        # 调用 gemini_cli 转写
        console.print("[bold]Step 0: 🎙️ 转写音频...[/bold]")
        # ... 转写逻辑

    for name, handler in steps:
        console.print(f"\n[bold]{name}[/bold]")
        result = handler(args)
        if result != 0:
            console.print(f"[red]❌ {name} 失败，终止[/red]")
            return result

    console.print(Panel(
        f"[green]✅ {date} 处理完成！[/green]\n"
        f"运行 [bold]openmy view {date}[/bold] 查看结果",
        border_style="green",
    ))
    return 0
```

- [ ] **Step 2: 跑全量测试**

Run: `pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: openmy run - full pipeline command"
```

---

## Chunk 5: pyproject.toml console_scripts

### Task 10: 注册全局命令

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 添加 console_scripts**

```toml
[project.scripts]
openmy = "openmy.cli:main"
```

- [ ] **Step 2: 重装**

Run: `pip install -e .`
Expected: `openmy status` 可以直接在终端跑

- [ ] **Step 3: 验证所有命令**

```bash
openmy status
openmy view 2026-04-06
openmy --help
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: register openmy as global CLI command"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-04-08-cli-pipeline.md`. Ready to execute?
