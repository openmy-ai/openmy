---
name: openmy-day-view
description: Use when reading one processed day without re-running anything
---

# OpenMy Day View

## Purpose

Read one processed day without re-running anything.

## Trigger

Use it when the user asks for:
- the briefing for a day
- the timeline for a day
- the scenes for a day
- the extracted results for a day
- confirmation that a day already has outputs

## Action

- `openmy skill day.get --date YYYY-MM-DD --json`

## Restrictions

- Do not auto re-run the day.
- Do not edit files inside the day folder.
- Do not turn a read into a write unless the user asks.

## Output

- lead with `human_summary`
- use `data.briefing`, `data.scenes`, and `data.status` for detail
- if outputs are missing, offer `openmy-day-run`

## `data.status` Values

| status | meaning | agent next step |
|--------|---------|-----------------|
| complete | all outputs exist | summarize the day |
| partial | some later outputs are still missing | explain what is missing |
| transcript_only | only early transcript data exists | suggest a re-run or follow-up processing |
| empty | no usable data exists | ask whether the user has audio for that date |

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - invalid date → rerun with `YYYY-MM-DD`
   - missing day data → ask whether audio exists for that date
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
