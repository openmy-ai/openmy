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

## Agent Behavior After Viewing Results

1. lead with the one-line summary
2. list key events and decisions
3. highlight open items from that day
4. if the day is incomplete, explain what is missing
5. if no data exists, ask whether the user has audio for that date
