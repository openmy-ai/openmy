---
name: openmy-startup-context
description: Use at the start of every OpenMy session to silently load user context before the first reply
---

# OpenMy Startup Context

## Purpose

Silently load user context at the start of every session so the agent knows what the user is working on **without asking**.

## Trigger

This skill is triggered **automatically** by the Startup Checklist in CLAUDE.md / AGENTS.md.
You do NOT need the user to ask for it.

## Action

- `openmy skill context.get --compact --json`

## Output Rules

- **Do NOT show the context output to the user.** Read it silently.
- **Do NOT say** "I just loaded your context" or "Let me check your recent activity."
- **Do NOT list** what you found. Just use it as background knowledge.
- If context is empty (new user), silently switch to `health.check` onboarding.

## What You Learn From Context

The `--compact` flag returns a short markdown with three layers:

1. **Monthly direction** — What the user is focused on this month
2. **Weekly progress** — What happened this week so far
3. **Recent daily activity** — What the user did in the last 1-2 days

Use this to:
- Greet the user with awareness ("继续昨天的 X 吗？")
- Skip questions the context already answers
- Suggest the next logical step based on open items

## Agent Behavior

1. If context has open items older than 3 days, ask if they are still active.
2. If recent days have no data, ask if the user has new recordings.
3. If profile or vocab is missing, start onboarding silently.
4. If this is the first session ever (empty context), run `health.check`.
5. If the user says "find the DJI mic recording" or mentions a device, treat it as a file-finding request. Do NOT start live recording.

## Anti-Patterns (NEVER DO THESE)

- ❌ "I just ran context.get and here's what I found..."
- ❌ "Let me load your recent activity first."
- ❌ "Your context shows 5 days of data, 3 open projects..."
- ✅ Just start talking as if you already know. Because you do.
