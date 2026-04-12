---
name: openmy-export
description: Use when configuring automatic export of daily summaries to the user's note system
---

# OpenMy Export

## Purpose

Explain and configure automatic export so processed daily summaries can be saved into the user's note system.

## Trigger

Use it when:
- the user wants daily summaries saved automatically
- the user asks for Obsidian export
- the user asks for Notion export
- export is configured but not ready

## Action

- `openmy skill health.check --json`
- `openmy skill day.run --date YYYY-MM-DD --audio path/to/audio.wav --json`

## Restrictions

- Do not guess the user's vault path or Notion database ID.
- Do not enable export silently.
- Do not block the main audio pipeline if export fails.

## Output

- explain which export target is selected
- explain whether it is configured and ready
- end with one next setup step if anything is missing

## Agent Behavior

1. Ask whether the user wants Obsidian or Notion.
2. For Obsidian, ask for the vault folder path.
3. For Notion, ask for the API key and database ID.
4. After setup, run `health.check` to confirm readiness.
5. If export fails later, explain that the daily processing still finished and only the export part failed.
