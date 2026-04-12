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
   - On first setup, **always ask the user which speech-to-text engine they want to use.** Do NOT silently default to `faster-whisper`.
   - Present the options from `stt_providers` in a clear comparison:
     - **Local (no key needed):** `faster-whisper` (English-optimized), `funasr` (Chinese-optimized, needs extra install)
     - **Cloud (needs API key):** `gemini` (good all-around), `dashscope/Qwen` (best Chinese accuracy, free tier available), `groq` (fast), `deepgram` (enterprise)
   - Recommend based on the user's language: Chinese speakers → suggest `dashscope` or `gemini`; English speakers → suggest `faster-whisper` or `gemini`.
   - Once the user chooses, set `OPENMY_STT_PROVIDER=<chosen>` in the project `.env` file. If the chosen engine needs an API key, help the user add it.
6. **Always highlight that local engines work without any key.** If the user has no API keys configured, say: "You can already process audio with the built-in local engine. API keys are optional — they unlock cloud-based engines with better accuracy."
7. When recommending an engine, start with the one that is already `ready: true`.
8. If `llm_available` is false, explain that an agent can still finish distillation and extraction through `distill.pending -> distill.submit` and `extract.core.pending -> extract.core.submit`.
