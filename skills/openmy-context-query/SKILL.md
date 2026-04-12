---
name: openmy-context-query
description: Use when searching structured context for projects, people, open items, closed items, or evidence
---

# OpenMy Context Query

## Purpose

Search the structured context for projects, people, open items, closed items, or evidence.

## Trigger

Use it when the user asks things like:
- find everything about OpenMy
- show open items
- what evidence do I have for this
- search people named Claude
- list closed items about the README

## Action

- `openmy skill context.query --kind project --query OpenMy --json`
- `openmy skill context.query --kind open --query README --json`
- `openmy skill context.query --kind evidence --query Figma --include-evidence --json`

## Restrictions

- Do not guess results without querying.
- Do not edit context while searching.
- Do not turn a search into a correction write unless the user confirms a fix.

## Output

- lead with `human_summary`
- state the matched kind and count
- show the most useful hits first
- include evidence only when it helps answer the question
