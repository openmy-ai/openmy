# OpenMy — Project Instructions

OpenMy is a **personal context engine**. It processes existing audio recordings into structured daily context.
It is NOT a recording app, NOT a note app, NOT a generic chat wrapper.

## Communication Rules (MANDATORY)

When presenting results to users:
- Talk like a human assistant, not a developer tool.
- Use plain language. Avoid jargon like "LLM", "provider", "API" unless you explain them immediately.
- Never show raw file paths. Say "your profile is saved" instead of a full path.
- Never dump JSON. Read it and summarize it in plain language.
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
3. Ask which STT engine to use — this is the ONE question you must ask
4. Initialize vocab with `openmy skill vocab.init --json`
5. Help locate the first audio file
6. Process it with `openmy skill day.run`
7. Present results in plain language

## API Keys Are Optional

Local engines (`faster-whisper`, `funasr`) work without any key.
`GEMINI_API_KEY` is only needed for distillation/extraction — and even then, the agent can do it manually.
**Never tell the user they must configure an API key before processing audio.**

## Full Skill Reference

For the complete routing map, action contracts, and sub-skill documentation, see:
- `skills/openmy/SKILL.md` — Router skill with all rules
- `skills/openmy/references/action-contracts.md` — Stable command boundary
- `skills/openmy/references/routing-rules.md` — When to use which sub-skill

## Build & Test

```bash
pip install -e .
uvx ruff check .
python3 -m pytest tests/ -v
```

## Git Conventions

- **Commit messages must be in English.** Use Conventional Commits format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.
- Keep messages short and descriptive. Example: `docs: add cross-platform skill install instructions`.
