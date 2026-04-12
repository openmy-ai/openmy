# OpenMy CLI Main Menu

## Problem

Running `openmy` with no arguments shows a raw argparse help output.
Users need a clear, organized, scannable CLI menu.

## Goal

When user runs `openmy` (no args), show a beautiful Rich-powered main menu:

```
╭─ OpenMy — 你的个人上下文引擎 ───────────────────╮
│                                                  │
│  快速开始                                        │
│    openmy quick-start     首次使用，自动引导      │
│    openmy run --date 今天  处理今天的录音          │
│                                                  │
│  处理流程                                        │
│    openmy status          查看所有日期的处理状态   │
│    openmy view 2026-04-12 查看某天的概览          │
│    openmy run             全流程处理              │
│                                                  │
│  单步操作                                        │
│    openmy clean           清洗转写文本            │
│    openmy roles           场景切分 + 角色归因     │
│    openmy distill         蒸馏摘要               │
│    openmy briefing        生成日报               │
│    openmy extract         提取意图 / 事实         │
│                                                  │
│  上下文                                          │
│    openmy context         生成/查看活动上下文     │
│    openmy query           查询项目/人物/待办      │
│    openmy weekly          查看本周回顾            │
│    openmy monthly         查看本月回顾            │
│                                                  │
│  工具                                            │
│    openmy correct         纠正转写错误            │
│    openmy watch           监控录音文件夹          │
│    openmy screen on/off   开关屏幕识别            │
│                                                  │
│  Agent 接口                                      │
│    openmy skill ...       稳定 JSON 动作入口     │
│                                                  │
│  v0.x.x · https://github.com/openmy-ai/openmy   │
╰──────────────────────────────────────────────────╯
```

## Implementation

### [MODIFY] `src/openmy/cli.py`

1. Override the default no-args behavior: if `sys.argv` has no subcommand, call `_show_main_menu()` instead of `parser.print_help()`.
2. `_show_main_menu()` uses Rich Panel + Table to render the menu above.
3. Group commands by category (Quick Start, Processing, Steps, Context, Tools, Agent).
4. Show version number from `pyproject.toml` or `__version__`.

### [NEW] Add missing subcommands

Register these as actual subcommands:
- `openmy weekly` → show this week's review (generate if missing)
- `openmy monthly` → show this month's review (generate if missing)  
- `openmy watch [dir]` → start watcher (use OPENMY_AUDIO_SOURCE_DIR if no dir)
- `openmy screen on|off` → toggle screen recognition

### Implementation details for new commands

#### `openmy weekly`
```python
def cmd_weekly(args):
    from openmy.services.aggregation.weekly import generate_weekly_review, current_week_str
    week = getattr(args, "week", None) or current_week_str()
    review = generate_weekly_review(DATA_ROOT, week)
    # Pretty print with Rich
```

#### `openmy monthly`
```python
def cmd_monthly(args):
    from openmy.services.aggregation.monthly import generate_monthly_review, current_month_str
    month = getattr(args, "month", None) or current_month_str()
    review = generate_monthly_review(DATA_ROOT, month)
    # Pretty print with Rich
```

#### `openmy watch`
```python
def cmd_watch(args):
    from openmy.services.watcher import watch
    watch(getattr(args, "directory", None))
```

#### `openmy screen`
```python
def cmd_screen(args):
    action = args.action  # "on" or "off"
    # Update .env: SCREEN_RECOGNITION_ENABLED=true/false
    # Report: "屏幕识别已开启" / "屏幕识别已关闭"
```

## Verification

```bash
openmy            # should show pretty menu
openmy weekly     # should show this week's review
openmy monthly    # should show this month's review  
openmy watch      # should start watcher
openmy screen on  # should enable screen recognition
openmy screen off # should disable screen recognition
ruff check src/openmy/cli.py
python3 -m pytest tests/ -q
```

## Git Conventions

- `feat: add CLI main menu and missing subcommands`
- Run `ruff check .` before commit
