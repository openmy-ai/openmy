---
name: openmy
description: Router skill for OpenMy tasks. Use it to choose the right sub-skill, enforce command boundaries, and apply onboarding or follow-up patterns.
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

## Global rules

- Do not ask the user to type commands manually.
- Do not bypass `openmy skill <action> --json` to call internal modules.
- Do not edit `active_context.json`, `corrections.jsonl`, `scenes.json`, `meta.json`, or `profile.json` directly.
- Do not treat the frontend as the execution surface.
- Do not describe OpenMy as an MCP-first product.

## First-Time Setup Flow

If this looks like a first-time setup:

1. route to `openmy-profile-init`
2. route to `openmy-vocab-init`
3. help the user locate the first audio file
4. route to `openmy-day-run`
5. review the result with the user
6. suggest corrections if the transcript clearly has errors
7. route back to `openmy-vocab-init` if you discover more names or terms

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
