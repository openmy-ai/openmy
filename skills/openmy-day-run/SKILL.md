---
name: openmy-day-run
description: Use when processing new audio, re-running one day, or finishing missing outputs for a date
---

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
- `openmy skill day.run --date YYYY-MM-DD --skip-transcribe --json`

## Restrictions

- Do not call internal modules directly.
- Do not ask the user to assemble commands manually.
- Do not change raw evidence files by hand.
- Do not go silent for more than 30 seconds during long work.

## Output

- start with `human_summary`
- then inspect `data.run_status`
- if a step is skipped, explain `skip_reason`
- if the user only wants to inspect results, route to `openmy-day-view`

## Audio Input Guide

- OpenMy accepts normal audio files from wireless mics, phones, meetings, and screen recorders.
- If the user mentions a device, first look for files already saved on disk.
- Do **not** start live recording unless the user explicitly says they want to record now.
- If audio is on external storage, copy it into the local day folder first, then process the local copy.

## Progress Reporting

1. Before `day.run`, report how many files were found, which engine will be used, and the rough estimate.
2. If a cloud engine is used, split big batches automatically.
3. After the run, summarize each major step and what happened.
4. Always mention the local page if results are ready.

## Web UI Support

- The local page at `localhost:8420` can accept dragged audio files directly.
- The page shows the 4-stage progress panel: transcribe → clean → segment → distill.
- The page can pause, cancel, or skip the current step when the job allows it.
- The agent does not need to call the web endpoints manually for normal runs, but should tell the user they can open the page to watch progress.

## Autonomous Distillation Default

If audio processing finishes but later AI steps are still missing:
1. Lead with what is already done.
2. If the user has **not** expressed a preference, continue with the agent-side distillation and extraction path immediately.
3. Only stop and ask first if the user explicitly said they prefer configuring a key instead.
4. After the agent-side path finishes, tell the user that the audio part was already done and you finished the later two steps for them.

## 自检规则

发回复前检查：
- 不要把“因为没配 Gemini key”当成主句。
- 不要把“缺少 LLM API key”当成主句。
- 可以提到“后面两步整理我可以直接替你做，要继续吗？”这句旧口径，但默认动作现在是直接继续，不再把它当成必停问题。
- 主句必须先说“音频已经跑完了”或者“我已经继续把后面两步做完了”。

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message` first.
2. Common recovery:
   - `missing_audio` → find the saved recordings or ask the user where they are.
   - `missing_profile` → route to `openmy-profile-init`.
   - `missing_engine` → route to `openmy-health-check`.
   - `missing_reusable_data` → rerun without `--skip-transcribe`.
   - `permission_denied` → explain which folder could not be read or written.
3. Never silently swallow errors.
4. Never retry the same failing step more than once without telling the user.
