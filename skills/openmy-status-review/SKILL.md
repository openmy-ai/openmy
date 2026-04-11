# OpenMy Status Review

## Purpose

Review the overall OpenMy state before choosing the next workflow.

## Trigger

Use it when:
- the task is still vague
- you need to see which days are complete or partial
- you need to decide the next highest-value action

## Action

- `openmy skill status.get --json`

## Restrictions

- Do not start day processing automatically.
- Do not write corrections from this skill.
- Do not let this skill turn into a long product discussion.

## Output

- start with `human_summary`
- categorize days into complete, partial, and empty
- end with one recommendation

## Agent Behavior After Status Review

Always recommend something concrete.
Examples:
- process yesterday first
- finish the partial day
- review stale open items
- initialize vocab before the next run
