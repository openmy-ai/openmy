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
- Do not edit `.env` automatically.
- Do not switch providers silently.

## Output

- lead with `human_summary`
- list setup problems in priority order
- explain which speech-to-text engine is active and which ones are ready
- end with one concrete next fix

## Agent Behavior

1. If `data.healthy` is true, say the environment is ready.
2. If profile is missing, suggest `profile.set` first.
3. If vocab is missing, suggest `vocab.init` next.
4. If the active engine needs a key, explain which key name is missing.
5. When the user asks which engine to choose, compare local engines and API engines in plain language.
