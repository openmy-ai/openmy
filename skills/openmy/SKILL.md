---
name: openmy
description: >
  Use when the task involves OpenMy data, audio processing, transcription,
  daily context, corrections, vocabulary, profile setup, onboarding, or
  first-time setup. Routes to the correct sub-skill and enforces
  communication style (plain language, no jargon, no file paths).
---

# OpenMy Router Skill

OpenMy is a personal context engine.
It is **not** an MCP server, not a note app, and not a generic chat wrapper.

The fixed stack is:

- personal context engine
- router skill layer
- sub-skill workflow layer
- CLI execution layer
- frontend display layer

Reference files:
- `skills/openmy/references/architecture.md`
- `skills/openmy/references/action-contracts.md`
- `skills/openmy/references/routing-rules.md`

## When to use this skill

Use this skill when:
- the task is about OpenMy data, processing, corrections, status, or onboarding
- you need to choose the right sub-skill before acting
- you need to enforce the stable command boundary

## Routing map

- startup context → `openmy-startup-context`
- context snapshot reading → `openmy-context-read`
- structured context search → `openmy-context-query`
- day processing / re-run → `openmy-day-run`
- single-day result reading → `openmy-day-view`
- correction write-back → `openmy-correction-apply`
- overall status review → `openmy-status-review`
- vocabulary initialization → `openmy-vocab-init`
- profile onboarding → `openmy-profile-init`
- environment and engine check → `openmy-health-check`
- **change / switch STT engine** → `openmy-health-check` (run health.check, show engines, let user pick, update `.env`)
- agent-side scene distillation handoff → `openmy-distill`
- agent-side core extraction handoff → `openmy-extract`
- weekly / monthly summary refresh → `openmy-aggregate`
- export setup → `openmy-export`
- screen recognition setup → `openmy-screen-recognition`

## Global rules

- Do not ask the user to type commands manually.
- Do not bypass `openmy skill <action> --json` to call internal modules.
- Do not edit `active_context.json`, `corrections.jsonl`, `scenes.json`, `meta.json`, or `profile.json` directly.
- Do not treat the frontend as the execution surface.
- Do not describe OpenMy as an MCP-first product.
- When the user mentions a device or source such as DJI Mic, phone voice memos, meeting recorder, or screen recording, assume they mean **existing recordings already saved on disk**.
- Do **not** start live recording, open the microphone, or switch into realtime transcription unless the user explicitly says they want to record **now**.
- Default interpretation:
  - "去找大疆麦克风录音" = find the recorded audio files
  - "打开麦克风开始录" = start live recording

## Critical: API Keys Are Optional

OpenMy works out of the box with local speech-to-text engines.
No API key is needed to process audio.
- `faster-whisper` and `funasr` run locally and are always ready.
- API-based engines (`gemini`, `groq`, `dashscope`, `deepgram`) need keys, but they are optional upgrades.
- LLM keys (`GEMINI_API_KEY`) are needed for distillation and extraction, but there are TWO ways to handle this — let the user choose.
**Never tell the user they must configure an API key before processing audio.**
Run `health.check` first. It shows which engines are already ready.

### Distillation & Extraction: Two Options

When `llm_available` is false, **always present both options and let the user decide:**

| Option | How | Cost | Speed |
|--------|-----|------|-------|
| **A. Configure a Gemini API key** | Add `GEMINI_API_KEY` to `.env`. OpenMy calls `gemini-flash-lite` directly. | Very cheap (~$0.01/day, free tier available) | Fast, fully automated |
| **B. Let me (the agent) do it** | Agent reads scenes via `distill.pending`, writes summaries with its own LLM, submits via `distill.submit`. | Uses YOUR agent token budget (Claude/GPT tokens are expensive) | Slower, but zero config |

**Present both options clearly. Do NOT decide for the user.**
If the user picks A, help them get a Gemini API key and add it to `.env`.
If the user picks B, proceed with `distill.pending` → `distill.submit` and `extract.core.pending` → `extract.core.submit` immediately.

## Communication Style

When presenting results to users:
- Talk like a human assistant, not a developer tool.
- Use plain Chinese. Avoid tool jargon like "LLM", "structure extraction", "provider", "pending", or "API" unless you immediately explain them in normal language.
- Never show raw file paths. Say "your profile is saved" instead of a full path.
- Never dump JSON. Read it and summarize it in plain language.
- Never ask users to type terminal commands. Run the commands yourself.
- **Never tell users to open a terminal or check logs.** All status updates happen right here in the chat.
- **Never go silent.** If a command takes more than 30 seconds, give an update. Users should never wonder "is it still working?"
- Use short paragraphs, not long bullet lists.
- Lead with what matters first.
- Use emoji sparingly for visual hierarchy.
- When listing items, prefer one compact sentence over a long list.
- End with a question or suggestion, not a status dump.
- **Never say or imply:** "You must configure Gemini before audio can run."
- When audio is already processed and only the later AI steps are missing, say it plainly:
  - "音频已经跑完了。现在只差后面两步整理。"
  - "你有两个选项：我现在直接替你做；或者你以后再配 Gemini key。"
  - "如果你想省事，我现在就继续帮你做。"

## First-Time Setup Flow

If this looks like a first-time setup:

1. **Always start with `openmy-health-check`** — this tells you what is ready and what is missing.
2. **Auto-setup profile** — if `health.check` says profile is missing or still has defaults (`name=User`, `timezone=UTC`), detect the system timezone and conversation language, then run `profile.set` immediately. Do NOT ask the user — just set it and tell them what you did.
3. **Ask which STT engine to use** — present the available engines from `health.check` results and ask the user to choose. This is the ONE question you must ask during first setup. After the user picks, set `OPENMY_STT_PROVIDER` in the project `.env` file.
4. Route to `openmy-vocab-init` if vocab is missing.
5. Help the user locate the first audio file.
6. Route to `openmy-day-run`.
7. Review the result with the user.
8. Suggest corrections if the transcript clearly has errors.
9. Route back to `openmy-vocab-init` if you discover more names or terms.
10. **If `day.run` returns `partial` because of missing LLM key** — present the two distillation options (A: configure cheap Gemini API key vs B: agent does it with its own expensive tokens). Let the user choose. See the "Distillation & Extraction: Two Options" section above.

### First-Run Reply Shape

For a first-time user, the reply should feel like this:
1. confirm what is already ready
2. say there is only one decision left right now: choose the speech-to-text engine
3. if audio already ran, say "音频已经跑完了"
4. if later AI steps are blocked, say "我也可以直接替你做后面两步"
5. end with one clear next question or next action

## Typical Daily Workflow

1. user records audio during the day
2. route to `openmy-day-run`
3. route to `openmy-day-view`
4. route to `openmy-correction-apply` for any fixes
5. route to `openmy-context-read` or `openmy-status-review` for follow-up

When the next step is unclear, start with `openmy-status-review`.

## Proactive Patterns

Always apply these checks:

- if words look like transcription errors, suggest corrections
- if open loops keep piling up, ask which ones should be closed
- if several recent days have no data, ask whether recordings exist
- if a new proper noun appears, suggest adding it to vocab
- if setup looks broken, route to `openmy-health-check`

## Feature Discovery

After basic setup is done, proactively ask about optional features.

### Export Integration

Ask: "Would you like your daily summaries automatically saved to a note-taking app?"
- If yes, ask which one: Obsidian or Notion.
- For Obsidian, ask for the vault folder path.
- For Notion, guide the user to get an API key and database ID.
- Run `health.check` afterward to confirm the setup.

### Screen Recognition

Ask: "OpenMy can also capture what is on your screen to give richer context. This needs a local screen recognition service running in the background. Would you like to enable it?"
- Explain clearly: "Screen data stays on your machine. It helps match what you said with what you were doing on screen."
- If yes, check whether the local service is reachable at `localhost:3030`.
- If no, set `SCREEN_RECOGNITION_ENABLED=false` and move on quietly.

### STT Engine Upgrade

If the user processed audio with `faster-whisper`, ask:
"The built-in engine works fine. If you want higher Chinese accuracy, you can switch to Qwen with a free Alibaba API key. Want me to help set that up?"
