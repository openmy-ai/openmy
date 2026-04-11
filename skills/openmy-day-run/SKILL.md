# OpenMy Day Run

## Purpose

Process new audio, re-run one day, or finish missing outputs for a date.

## Trigger

Use it when:
- the user gives audio
- the user wants to process one day
- the user wants to re-run one day
- the user wants to complete missing outputs for a day

## Action

- `openmy skill day.run --date YYYY-MM-DD --audio path/to/audio.wav --json`

## Restrictions

- Do not call internal modules directly.
- Do not ask the user to assemble commands manually.
- Do not change raw evidence files by hand.

## Output

- start with `human_summary`
- then inspect `data.run_status`
- if a step is skipped, explain `skip_reason`
- if the user only wants to inspect results, route to `openmy-day-view`

## Audio Input Guide

OpenMy accepts any normal audio file.
It is not tied to one device.

- wireless mic recordings
- phone voice memos
- meeting recordings
- screen recorder exports
- any `ffmpeg`-compatible audio file

If the file date is unclear, ask the user before choosing a date.

The default STT engine (`faster-whisper`) runs locally and needs no API key.
If the user has not configured any keys, proceed with the local engine.
Do not block audio processing because an API key is missing.

## Agent Behavior After Successful Run

1. Call `day.get` for the same date.
2. Scan for obvious transcript errors.
3. Suggest corrections when names or terms look wrong.
4. If vocab is not initialized, suggest `vocab.init`.
5. Summarize the day in plain language.
6. If any step was skipped or failed, explain why and offer the next fix.
7. If the run pauses at distillation or core extraction because no LLM key is configured, route to `distill.pending` / `distill.submit` or `extract.core.pending` / `extract.core.submit` instead of asking the user for a key first.
