---
name: openmy-aggregate
description: Use when generating or refreshing weekly and monthly context summaries
---

# OpenMy Aggregate

## Purpose

Generate or refresh weekly and monthly summaries for startup context and later review.

## Trigger

Use it when:
- the user asks for a weekly review
- the user asks for a monthly review
- aggregation data looks stale or missing
- you want to refresh startup context summaries

## Action

- `openmy skill aggregate --week 2026-W15 --json`
- `openmy skill aggregate --month 2026-04 --json`
- `openmy skill status.get --json`

## Restrictions

- Do not edit weekly or monthly review files directly.
- Do not call internal aggregation helpers outside the stable skill boundary.
- Do not mix `--week` and `--month` in one call.

## Output

- lead with `human_summary`
- confirm which week or month was refreshed
- summarize the main direction in plain language
- end with one concrete next step

## Staleness Check

1. Run `status.get --json` first.
2. If `data.weekly_summary_date` or `data.monthly_summary_date` is missing, aggregation is stale.
3. If the returned week or month is older than the user asked for, refresh it immediately.

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - invalid week or month → rerun with normalized `YYYY-Www` or `YYYY-MM`
   - conflicting target → split week and month into separate calls
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
