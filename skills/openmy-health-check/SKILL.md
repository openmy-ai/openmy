---
name: openmy-health-check
description: Use when verifying the runtime environment is ready or helping the user fix missing setup
---

# OpenMy Health Check

## Purpose

Verify that the runtime environment is ready and help the user fix missing setup.

## Trigger

Use it when:
- first-time setup looks incomplete
- the user asks whether OpenMy is working
- processing failed because setup is missing
- you need to compare available speech-to-text engines

## Action

- `openmy skill health.check --json`

## Restrictions

- Do not guess environment state without checking.
- Only edit `.env` after the user confirms the change (e.g., choosing an STT engine).
- Do not switch providers silently.

## Output

- lead with `human_summary`
- list setup problems in priority order
- explain which speech-to-text engine is active and which ones are ready
- explain whether `llm_available` is true or false
- end with one concrete next fix

## Agent Behavior

1. If `data.healthy` is true, say the environment is ready.
2. If profile is missing, suggest `profile.set` first.
3. If vocab is missing, suggest `vocab.init` next.
4. If the active engine needs a key, explain which key name is missing.
5. **First-time STT engine selection (CRITICAL):**
   - On first setup, **always ask the user which speech-to-text engine they want to use.** Do NOT silently default to any engine.
   - **You MUST present ALL available engines from `stt_providers`.** Never hide or omit any. Show them grouped:
     - **Local engines (no API key needed, works immediately):**
       - `funasr` — Best for Chinese. Runs locally. Free.
       - `faster-whisper` — Best for English/multilingual. Runs locally. Free.
     - **Cloud engines (needs API key, better accuracy):**
       - `dashscope` (阿里百炼/通义千问) — Excellent Chinese accuracy. Free tier available. Key: `DASHSCOPE_API_KEY`
       - `gemini` (Google) — Good all-around. Key: `GEMINI_API_KEY`
       - `groq` (Groq Whisper) — Very fast. Key: `GROQ_API_KEY`
       - `deepgram` (Deepgram Nova) — Enterprise grade. Key: `DEEPGRAM_API_KEY`
   - Recommend based on the user's language: Chinese speakers → suggest `funasr` (local) or `dashscope` (cloud); English speakers → suggest `faster-whisper` (local) or `gemini` (cloud).
   - Once the user chooses, set `OPENMY_STT_PROVIDER=<chosen>` in the project `.env` file. If the chosen engine needs an API key, also help the user add it to `.env`.
6. **Always highlight that local engines work without any key.** If the user has no API keys configured, say: "You can already process audio with the built-in local engine. API keys are optional — they unlock cloud-based engines with better accuracy."
7. When recommending an engine, start with the one that is already `ready: true`.
8. If `llm_available` is false, explain that an agent can still finish distillation and extraction through `distill.pending -> distill.submit` and `extract.core.pending -> extract.core.submit`.
9. When `llm_available` is false, do **not** stop at "missing key". Say it in user language:
   - "先别管 Gemini key。音频可以先跑。"
   - "后面两步整理我也可以直接替你做。"
   - "你现在只需要先选转写引擎。"
