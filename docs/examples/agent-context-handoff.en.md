# How to let your agent read your context first

The goal is simple:

stop re-explaining what you were doing every time you open a new session.

## Shortest path

Once OpenMy is installed, let the agent read these stable entrypoints first:

```bash
openmy skill status.get --json
openmy skill context.get --json
openmy skill day.get --date 2026-04-13 --json
```

## Why these three

1. `status.get` tells the agent whether usable data exists.
2. `context.get` loads the cross-day project and todo state.
3. `day.get` fills in the details for a specific processed day.

## A practical opening line

You can just tell your agent:

> Read my OpenMy context first, then continue yesterday's task.

A good agent should load context before asking follow-up questions.

## The safest integration rules

- Prefer the `skill` entrypoint over the old compatibility `agent` entrypoint.
- Read the JSON, then summarize it in plain language.
- Start with `context.get`, then decide whether `day.get` is still needed.
