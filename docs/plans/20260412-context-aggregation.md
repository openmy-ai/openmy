# OpenMy Context Aggregation & Startup Enhancement

## Overview

Build a three-layer context aggregation pipeline (daily → weekly → monthly) and integrate it
with the startup context injection system. The agent should know what the user is working on
across day, week, and month timescales — without the user doing anything.

All code must pass `ruff check .` and existing tests.

---

## Task 1: Weekly Aggregation Engine

### Goal

Read the last 7 daily briefings and produce one `weekly_review.json`.

### Implementation

#### [NEW] `src/openmy/services/aggregation/__init__.py`
Empty init.

#### [NEW] `src/openmy/services/aggregation/weekly.py`

```python
def generate_weekly_review(data_root: Path, week_str: str | None = None) -> dict:
    """
    Read up to 7 daily_briefing.json files for the given ISO week.
    If week_str is None, use the current week.
    
    Output format:
    {
        "week": "2026-W15",
        "date_range": "2026-04-07 ~ 2026-04-13",
        "summary": "本周主要...",
        "projects": ["project1", "project2"],
        "wins": ["...", "..."],
        "challenges": ["..."],
        "open_items": ["..."],
        "decisions": ["..."],
        "next_week_focus": "..."
    }
    """
```

Key rules:
- Read `data/{date}/daily_briefing.json` for each day in the ISO week
- Extract and merge: key_events, decisions, todos_open, insights from each daily briefing
- The `summary` field should be a 2-3 sentence synthesis, not a concatenation
- If a day has no briefing, skip it silently
- Store output at `data/weekly/{week_str}.json`
- **Do NOT call any LLM.** This is pure deterministic aggregation (merge + deduplicate). LLM summarization is a future enhancement.

#### [NEW] `src/openmy/services/aggregation/monthly.py`

```python
def generate_monthly_review(data_root: Path, month_str: str | None = None) -> dict:
    """
    Read weekly_review.json files for the given month.
    If month_str is None, use the current month.
    
    Output format:
    {
        "month": "2026-04",
        "summary": "本月...",
        "projects": ["..."],
        "key_decisions": ["..."],
        "open_items": ["..."],
        "direction": "..."
    }
    """
```

Key rules:
- Read `data/weekly/{week}.json` for weeks that overlap with the target month
- Same deterministic merge approach, no LLM
- Store output at `data/monthly/{month_str}.json`

### Tests

#### [NEW] `tests/test_weekly_aggregation.py`

Test with mock daily briefing data:
- 7 days of data → produces valid weekly review
- 3 days of data → still works, skips missing days
- 0 days → returns empty/minimal structure
- Verify no duplicate entries in merged lists

#### [NEW] `tests/test_monthly_aggregation.py`

Test with mock weekly review data:
- 4 weeks → valid monthly review
- 1 week → still works
- 0 weeks → empty/minimal structure

---

## Task 2: Auto-Trigger After day.run

### Goal

After `day.run` completes successfully, check if a weekly review should be generated.

### Implementation

#### [MODIFY] `src/openmy/services/ingest/audio_pipeline.py` (or the day.run completion handler)

After the last step of `day.run` succeeds:
1. Check if today is the last day of the ISO week (Sunday), OR if this is the 7th daily briefing for the current week
2. If yes, call `generate_weekly_review(data_root)`
3. Similarly, if this is the last week of the month, call `generate_monthly_review(data_root)`
4. Log the aggregation result in `run_status.json` as an extra step

### Rules
- Aggregation failure must NOT fail the day.run pipeline. Wrap in try/except, log the error, continue.
- Add a `--skip-aggregate` flag to day.run for cases where the user doesn't want it.

---

## Task 3: Integrate Aggregation Into compact Output

### Goal

`context.get --compact` should include weekly and monthly summaries when available.

### Implementation

#### [MODIFY] `src/openmy/services/context/renderer.py`

Update `render_compact_md()` to:
1. Check if `data/monthly/{current_month}.json` exists → add "## 本月方向" section
2. Check if `data/weekly/{current_week}.json` exists → add "## 本周进展" section
3. Keep existing daily sections

Target output format:
```markdown
# Active Context

## 当前状态
...

用户：周瑟夫（zh，Asia/Shanghai）

## 本月方向
跨境电商 AI 服务 + OpenMy 产品化

## 本周进展
完成了跨平台 skill 安装，正在优化 Agent 通信规范

## 最近项目
- OpenMy：完成 skill 标准化部署
- 跨境 AI 服务：准备客户 demo

## 今天重点
- ...

## 待处理
- ...
```

### Rules
- Monthly and weekly sections are OPTIONAL — only show if the file exists
- Each section should be 1-3 lines max
- Total compact output should stay under 2000 tokens

---

## Task 4: Aggregation Skill

### Goal

Create a skill so agents can manually trigger aggregation.

#### [NEW] `skills/openmy-aggregate/SKILL.md`

```yaml
---
name: openmy-aggregate
description: Use when generating or refreshing weekly/monthly context summaries
---
```

Trigger: user asks for a weekly/monthly review, or agent detects stale aggregation data.

Action: `openmy skill aggregate --week 2026-W15 --json` or `openmy skill aggregate --month 2026-04 --json`

#### [MODIFY] `src/openmy/skill_dispatch.py`

Add handlers:
- `aggregate.weekly` → calls `generate_weekly_review()`
- `aggregate.monthly` → calls `generate_monthly_review()`

Register them in `ACTION_HANDLERS`.

---

## Task 5: CLI Entry Points

#### [MODIFY] `src/openmy/cli.py` (or equivalent)

Add convenience commands:
- `openmy weekly` → show this week's review (generate if missing)
- `openmy monthly` → show this month's review (generate if missing)

---

## Task 6: Export Integration

#### [MODIFY] `src/openmy/providers/export/obsidian.py`

Add `export_weekly_review(week, review)` — writes to Obsidian vault as a weekly note.

#### [MODIFY] `src/openmy/providers/export/notion.py`

Add `export_weekly_review(week, review)` — creates a Notion page for the weekly review.

---

## Verification Plan

### Automated
```bash
python3 -m pytest tests/test_weekly_aggregation.py tests/test_monthly_aggregation.py -v
ruff check src/openmy/services/aggregation/
```

### Manual
1. Run `openmy skill aggregate --week $(date +%G-W%V) --json` and verify output
2. Run `openmy skill context.get --compact --json` and verify weekly section appears
3. Run `openmy skill day.run` and verify weekly aggregation triggers automatically after completion

---

## Priority Order

1. **Task 1** (weekly + monthly engine) — foundation, do this first
2. **Task 3** (compact integration) — makes startup context richer
3. **Task 2** (auto-trigger) — automates the aggregation
4. **Task 4** (skill) — allows manual triggering
5. **Task 5** (CLI) — convenience
6. **Task 6** (export) — nice to have

## Git Conventions

- Commit messages in English, Conventional Commits format
- One commit per task (e.g., `feat: add weekly aggregation engine`)
- Run `ruff check .` before each commit
