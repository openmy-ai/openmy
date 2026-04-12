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

## Agent Behavior: Progress Reporting (CRITICAL)

**Users must never feel like they are staring at a black box.** Report progress at every stage.

### Before Starting

1. **Count and inspect first.** Before calling `day.run`, check how many audio files the user wants to process. Report:
   - "You have X audio files for this date, total duration is about Y minutes."
   - "Estimated processing time: ~Z minutes with [engine name]."
2. If there are many files (5+), suggest processing in batches and ask the user.

### During Processing

3. **Report each major step as it completes.** After calling `day.run`, immediately check `run_status.json` and tell the user which steps passed and which are still running:
   - "Transcription done (3 files, 45 minutes of audio)."
   - "Cleaning and segmentation done (12 scenes found)."
   - "Distillation done (all 12 scenes summarized)."
   - "Daily briefing generated."
4. **If a step fails or is skipped**, explain WHY immediately. Don't wait until the end.
   - "Transcription of file 3 failed: network timeout. The other 2 files are fine. Want me to retry?"
   - "Distillation paused: no LLM key configured. You have two options: ..."
5. **If the command is taking long** (over 2 minutes), check `run_status.json` mid-flight to give the user an update.

### After Completion

6. Call `day.get` for the same date.
7. Scan for obvious transcript errors.
8. Suggest corrections when names or terms look wrong.
9. If vocab is not initialized, suggest `vocab.init`.
10. Summarize the day in plain language.
11. If any step was skipped or failed, explain why and offer the next fix.
12. If the run pauses at distillation or extraction, present the two options (cheap Gemini API key vs agent token) and let the user choose.
