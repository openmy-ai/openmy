---
name: openmy-context-read
description: Use when answering read-only questions about what the user is working on, what is pending, or what changed recently
---

# OpenMy Context Read

## Purpose

Answer read-only questions about what the user is working on, what is pending, and what changed recently.

## Trigger

Use it when the user asks things like:
- what am I working on
- what is pending
- what happened recently
- who have I been talking to
- what is my current state

## Action

- `openmy skill context.get --level 1 --json`

## Restrictions

- Do not write corrections.
- Do not edit context files directly.
- Do not switch into day processing unless the user asks for it.

## Output

- start with `human_summary`
- then pull only the parts of `data.snapshot` that match the question
- if the user starts correcting facts or loops, route to `openmy-correction-apply`

## How to Read the Snapshot

- current focus → `rolling_context.project_cards`
- pending work → `rolling_context.open_loops`
- recent activity → `rolling_context.recent_events`
- decisions → `rolling_context.decisions`
- people → `rolling_context.entity_rollups`
- current state → `realtime_context.today_state`

## Pattern Checks

- projects repeated across 3 or more days usually mean core focus
- loops that keep reappearing probably need attention
- people who show up often are important contacts

## Error Handling

If `context.get` fails:
1. Read `error_code` and `message`.
2. If the context snapshot is missing, say so plainly and route to `openmy-status-review` or `openmy-day-run` depending on the question.
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
