---
name: openmy-screen-recognition
description: Use when explaining or managing screen recognition that matches speech with on-screen activity
---

# OpenMy Screen Recognition

## Purpose

Explain and manage the screen-recognition switch that helps OpenMy match spoken moments with on-screen activity.

## Trigger

Use it when:
- the user asks what screen recognition does
- the user wants to enable or disable screen recognition
- the user wants richer context from screen activity
- screen recognition is enabled but the local service is not reachable

## Action

- `openmy skill health.check --json`
- `openmy skill profile.set --screen-recognition on --json`
- `openmy skill profile.set --screen-recognition off --json`

## Restrictions

- Never enable it without explicit user intent.
- Explain it in plain language before turning it on.
- Do not hide the fact that it is local-only and optional.

## Output

- explain what the feature does in plain language
- explain whether it is enabled
- if it is enabled but not running, say that plainly
- end with one clear next step

## How it works

1. A background capture loop stores periodic screen context on this machine.
2. OpenMy lines that screen activity up with nearby speech.
3. This helps the daily summary remember what the user was actually doing.

## Agent Behavior

1. If the user only asks what it is, explain it and stop.
2. If the user clearly wants it on, run `profile.set --screen-recognition on --json`.
3. If the user clearly wants it off, run `profile.set --screen-recognition off --json`.
4. After either change, run `health.check` to confirm the current state.
5. If it is enabled but the background loop is not running, say so once and route to `openmy-health-check`.

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - `invalid_screen_recognition` → rerun with `on` or `off`.
   - service unavailable → explain that the setting changed but the local capture loop is not running yet.
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
