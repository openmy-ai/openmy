---
name: openmy-aggregate
description: Use when generating or refreshing weekly and monthly context summaries
---

# OpenMy Aggregate

## Purpose

手动生成或刷新周回顾、月回顾，给启动上下文和后续复盘用。

## Trigger

Use it when:
- the user asks for a weekly review
- the user asks for a monthly review
- aggregation data looks stale or missing
- you want to refresh startup context summaries

## Action

- `openmy skill aggregate --week 2026-W15 --json`
- `openmy skill aggregate --month 2026-04 --json`

## Restrictions

- Do not edit weekly or monthly review files directly.
- Do not call internal aggregation helpers outside the stable skill boundary.
- Do not mix `--week` and `--month` in one call.

## Output

- lead with `human_summary`
- confirm which week or month was refreshed
- summarize the main direction in plain language
- end with one concrete next step
