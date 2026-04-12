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
If the user mentions a recorder or microphone brand, first look for recordings that already exist on disk.
Do **not** assume the user wants to start a new live recording session.

The default STT engine (`faster-whisper`) runs locally and needs no API key.
If the user has not configured any keys, proceed with the local engine.
Do not block audio processing because an API key is missing.

### Intent Disambiguation For Audio Source

- "Find the DJI mic audio" = search for existing `.wav` / `.mp4` files from that device
- "Use today's voice memo" = search for today's saved recording files
- "Start recording now" / "turn on the mic" = live capture request

Unless the user explicitly says "start recording now", stay in the existing-file workflow.

## Agent Behavior: Progress Reporting (CRITICAL)

**Users must never feel like they are staring at a black box.** Report every single step as it happens.

### Anti-Silence Rules

- **NEVER go silent for more than 30 seconds.** If you are waiting for a command to finish, tell the user: "Still processing, currently on step X..."
- **If a command fails, report the failure IMMEDIATELY.** Do not silently retry without telling the user.
- **If a command takes longer than expected, say so.** "This is taking longer than expected. Checking status..."
- **All interaction happens in the chat.** Do not tell the user to open a terminal, check logs, or look at CLI output. YOU read the status and report back to the user in this conversation.

### Before Starting

1. **Count and inspect first.** Before calling `day.run`, list the audio files and report:
   - "Found X audio files for [date], total ~Y minutes."
   - "Using [engine name]. Estimated time: ~Z minutes."
2. If there are many files (5+), suggest processing in batches and ask the user.

### During Processing

3. **Report EVERY step as it completes.** After `day.run` finishes (or during long runs by checking `run_status.json`), report each step:
   - "Step 1/7 Transcription: done. 3 files processed, X minutes of audio."
   - "Step 2/7 Cleaning: done. Removed filler words and normalized formatting."
   - "Step 3/7 Scene segmentation: done. Found 8 scenes."
   - "Step 4/7 Distillation: done. All 8 scenes summarized."
   - "Step 5/7 Daily briefing: done."
   - "Step 6/7 Core extraction: done. Found 5 intents, 12 facts."
   - "Step 7/7 Context consolidation: done."
4. **If a step fails or is skipped**, explain WHY immediately.
   - "Step 1 Transcription FAILED: network timeout on file 3. Files 1-2 processed OK. Retry?"
   - "Step 4 Distillation PAUSED: no LLM key. Two options: ..."

### After Completion: Visual Progress Report

5. **Always output a progress table** after the run finishes. Read `run_status.json` and render this:

```
## [date] Processing Report

| Step | Status | Details |
|------|--------|---------|
| Transcription | ✅ Done | 3 files, 45 min audio, engine: faster-whisper |
| Cleaning | ✅ Done | Normalized transcript |
| Scene Segmentation | ✅ Done | 8 scenes found |
| Role Recognition | ⏭️ Skipped | Feature frozen |
| Distillation | ✅ Done | 8/8 scenes summarized |
| Daily Briefing | ✅ Done | Generated |
| Core Extraction | ✅ Done | 5 intents, 12 facts |
| Context Consolidation | ✅ Done | active_context updated |
| Enrichment | ✅ Done | Display fields populated |

**Total time:** 34 seconds
**Next step:** View results → `openmy view [date]`
```

Use these status icons:
- ✅ = completed
- ❌ = failed (explain error)
- ⏭️ = skipped (explain reason)
- ⏸️ = paused (explain what's needed)
- ⏳ = running

6. Scan for obvious transcript errors and suggest corrections.
7. If vocab is not initialized, suggest `vocab.init`.
8. Summarize what the user talked about that day in 2-3 sentences.
9. If the run pauses at distillation or extraction, present the two options (cheap Gemini API key vs agent token) and let the user choose.

## Required Reply When The Run Stops Midway

If `day.run` stops after audio processing because later AI steps are not ready, the reply must be simple and direct:

- First say what is already done:
  - "音频已经转完了。"
  - "清洗和场景切分也做完了。"
- Then say what is missing in plain language:
  - "现在只差后面两步整理。"
- Then tell the user the agent can help right now:
  - "我现在就可以直接替你做。"
- Then give the two choices without jargon:
  - "选项 A：我现在继续替你做完。"
  - "选项 B：你以后再配 Gemini key，让它自己自动做。"

Do **not** say only:
- "缺少 LLM API key"
- "结构化提取会停在等待状态"
- "当前唯一没配的是 LLM key"

Those lines are too tool-like and do not help a first-time user understand that audio has already been processed and the agent can continue for them.
