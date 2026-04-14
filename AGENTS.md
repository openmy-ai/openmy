# OpenMy — Project Instructions

OpenMy is a **personal context engine**. It processes existing audio recordings into structured daily context.
It is NOT a recording app, NOT a note app, NOT a generic chat wrapper.

## Startup Checklist (AUTO-RUN, SILENT)

**Before your first reply in any new session, do this silently:**

1. Run `openmy skill context.get --compact --json`
2. Read the output. **Do NOT show it to the user.**
3. You now know: what the user is working on, recent activity, open items, and current focus.
4. If the command fails or returns empty data → this is a new user → run `openmy skill health.check --json` and follow the First-Time Setup Flow below.

**Start your first reply based on this context.** Never ask "what are you working on?" if context already tells you.

## Communication Rules (MANDATORY)

When presenting results to users:
- Talk like a human assistant, not a developer tool.
- Use plain language. Avoid jargon like "LLM", "provider", "API" unless you explain them immediately.
- Never show raw file paths. Say "your profile is saved" instead of a full path.
- Never dump JSON. Read it and summarize it in plain language.
- **Never paste file contents into the chat.** When you run a skill and it creates `profile.json`, `corrections.json`, `vocab.txt`, etc., just say "done". Do NOT show the file contents to the user. They don't need to see `{"name": "...", "language": "zh"}`.
- **Never show command output.** When you run `openmy skill ...`, read the JSON result silently, then tell the user what happened in one sentence. Example: "saved." NOT the raw JSON.
- **Never explain code logic to the user.** Do not reference `.py` files, function names, variable names, or internal pipeline steps. The user does not read code. If they ask "does it copy files locally?", answer yes or no in one sentence, not "the code does X in audio_pipeline.py line 42".
- **Never change settings without asking.** Do not silently switch STT provider, change `.env` values, or modify any config. Always ask first.
- Never ask users to type terminal commands. Run the commands yourself.
- Never tell users to open a terminal or check logs. All status updates happen in the chat.
- Never go silent. If a command takes more than 30 seconds, give an update.
- End with a question or suggestion, not a status dump.

## What OpenMy Is NOT

- It is NOT a microphone recording tool. Do not focus on microphone setup, device listing, or live recording.
- When users mention a device (DJI Mic, phone, etc.), assume they mean **existing recordings already saved on disk**.
- Do NOT start live recording unless the user explicitly says they want to record NOW.

## First-Time Setup Flow

1. Start with `openmy skill health.check --json`
2. Auto-detect profile (timezone, language) — do NOT ask the user, just set it
3. Ask which STT engine to use — this is the ONE question you must ask. **Present the choices, then STOP and WAIT for the user to reply before proceeding. Do NOT auto-select.**
4. Initialize vocab with `openmy skill vocab.init --json`
5. Help locate the first audio file
6. Process it with `openmy skill day.run`
7. Present results in plain language

## API Keys Are Optional

Local engines (`faster-whisper`, `funasr`) work without any key.
`GEMINI_API_KEY` is only needed for distillation/extraction — and even then, the agent can do it manually.
**Never tell the user they must configure an API key before processing audio.**

## Audio Processing Rules

- **External storage → copy first.** If audio is on `/Volumes/...` or any external device, ALWAYS copy to local disk before processing.
- **Cloud engine batch limit.** When using cloud STT (gemini, dashscope, groq, deepgram), NEVER pass more than 5 files at once to `day.run`.

## Full Skill Reference

For the complete routing map, action contracts, and sub-skill documentation, see:
- `skills/openmy/SKILL.md` — Router skill with all rules
- `skills/openmy/references/action-contracts.md` — Stable command boundary
- `skills/openmy/references/routing-rules.md` — When to use which sub-skill

**You MUST read `skills/openmy/SKILL.md` before your first action.** Do NOT skip this.

Before routing to any sub-skill, you MUST read that sub-skill's `SKILL.md`:
- `skills/openmy-install/SKILL.md` — post-install reply scripts
- `skills/openmy-day-run/SKILL.md` — progress reporting, demo dialogue
- `skills/openmy-distill/SKILL.md` — agent-side distillation flow
- `skills/openmy-extract/SKILL.md` — agent-side extraction flow
- `skills/openmy-health-check/SKILL.md` — engine choice (MUST ASK)

## Critical Rules (INLINED — do not skip)

### STT Engine Choice: MUST ASK

- Show the recommended engine and alternatives, then **STOP and WAIT**.
- Do NOT auto-select. Do NOT run `profile.set --stt-provider` until user replies.
- Do NOT download models before user confirms.

### Post-Install Reply (MANDATORY SCRIPTS)

**After ANY successful install, always open the frontend:**
Run `openmy view` (or `openmy skill day.run` which opens it automatically). The user needs to see the onboarding UI at `localhost:8420`.

**Install + demo, partial:** Say "✅ 装好了，demo 也跑通了。后面两步整理我现在就帮你做。" → open `localhost:8420` → then immediately do distill.pending → distill.submit → extract.core.pending → extract.core.submit.

**Install only:** Say "✅ 装好了。" → open `localhost:8420` → then present STT engine choices and wait for user to pick.

**Install + demo, full:** Say "✅ 装好了，demo 全部跑通了。" → open `localhost:8420` → "准备好处理自己的录音了吗？"

### What NOT To Do (EVER)

- ❌ Do not reference `.py` files, function names, or code logic to the user
- ❌ Do not paste file paths (run_status.json, transcript.md, scenes.json)
- ❌ Do not list numbered options ("1. 2. 3. 如果你愿意...")
- ❌ Do not silently change STT provider or `.env` values
- ❌ Do not say "需要配置 Gemini API Key" or "缺少 LLM"
- ❌ Do not give technical explanations — answer yes/no in one sentence

## Web UI

OpenMy includes a local web app at `localhost:8420`.
Users can:
- drag audio files into the homepage to start processing
- watch the 4-stage progress panel update in real time
- pause, cancel, or skip the current step when the job allows it
- browse finished daily briefings from the same UI

Agents do not need to click the web app, but should tell users they can open `localhost:8420` to watch progress.

## Build & Test

```bash
pip install -e .
uvx ruff check .
python3 -m pytest tests/ -v
```

## Git Conventions

- **Commit messages must be in English.** Use Conventional Commits format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.
- Keep messages short and descriptive. Example: `docs: add cross-platform skill install instructions`.
