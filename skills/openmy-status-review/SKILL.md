---
name: openmy-status-review
description: Use when reviewing overall OpenMy state before choosing the next workflow
---

# OpenMy Status Review

## Purpose

Review the overall OpenMy state before choosing the next workflow.

## Trigger

Use it when:
- the task is still vague
- you need to see which days are complete or partial
- you need to decide the next highest-value action

## Action

- `openmy skill status.get --json`

## Web Pipeline Status API

- `GET /api/pipeline/jobs` returns the current pipeline job list.
- `GET /api/pipeline/jobs/{id}` returns one job with `steps`, `progress_pct`, and `eta_seconds`.
- If the user asks about the live web progress panel, these endpoints are the source of truth.

## Restrictions

- Do not start day processing automatically.
- Do not write corrections from this skill.
- Do not let this skill turn into a long product discussion.

## Output

- start with `human_summary`
- categorize days into complete, partial, and empty
- end with one recommendation

## `data.status` Values

| status | meaning | agent next step |
|--------|---------|-----------------|
| complete | the day is fully processed | suggest viewing or reviewing |
| partial | the day stopped halfway | suggest finishing that day first |
| transcript_only | only transcript-level data exists | suggest rerunning the remaining steps |
| empty | no usable day data exists | suggest finding or importing audio |

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - missing profile → route to `openmy-profile-init`
   - missing vocab → route to `openmy-vocab-init`
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
