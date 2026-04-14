---
name: openmy-context-query
description: Use when searching structured context for projects, people, open items, closed items, or evidence
---

# OpenMy Context Query

## Purpose

Search the structured context for projects, people, open items, closed items, decisions, or evidence.

## Trigger

Use it when the user asks things like:
- find everything about OpenMy
- show open items
- what evidence do I have for this
- what decisions did I make
- search people named Claude
- list closed items about the README

## Action

- `openmy skill context.query --kind project --query OpenMy --json`
- `openmy skill context.query --kind open --json`
- `openmy skill context.query --kind evidence --query "发布" --include-evidence --json`
- `openmy skill context.query --kind closed --json`

## Restrictions

- Do not guess results without querying.
- Do not edit context while searching.
- Do not turn a search into a correction write unless the user confirms a fix.

## Output

- lead with `human_summary`
- state the matched kind and count
- show the most useful hits first
- include evidence only when it helps answer the question

## Valid `--kind` Values

| kind | meaning | typical use |
|------|---------|-------------|
| project | project | check progress for one project |
| person | person | check activity around one person |
| open | open item | find unfinished loops |
| closed | closed item | find finished loops |
| evidence | evidence | collect supporting records (also covers decisions) |

> **Note**: To search for decisions, use `--kind evidence --query "决策关键词"`. Decisions are returned as evidence hits with `type: decision`.

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - invalid kind → rerun with one of the valid values above
   - query failed → simplify the query and retry once
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
