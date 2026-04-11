# OpenMy Correction Apply

## Purpose

Write correction events such as closing loops, fixing transcript errors, rejecting false decisions, or merging duplicate projects.

## Trigger

Use it when the user says things like:
- this is wrong
- I already did that
- this is not a project
- merge these two project names
- fix this transcript spelling

## Action

- `openmy skill correction.apply --op close-loop --arg "Task Title" --json`
- `openmy skill correction.apply --op typo --arg "Cload" --arg "Claude" --date YYYY-MM-DD --json`

## Restrictions

- Do not edit correction history files directly.
- Do not edit the context snapshot directly.
- Do not bypass the stable action contract.

## Output

- lead with `human_summary`
- confirm `data.op` and `data.args`
- if the user wants a refreshed view, route to `openmy-context-read`

## Available Operations

| Operation | Purpose | Args | Needs --date? |
|-----------|---------|------|:---:|
| `close-loop` | Mark a task/loop as done | `--arg "task title"` | No |
| `typo` | Fix a transcription error | `--arg "wrong" --arg "right"` | Yes |
| `reject-decision` | Remove a false decision | `--arg "decision text"` | No |
| `merge-project` | Merge duplicate projects | `--arg "source" --arg "target"` | No |

Examples:

```
openmy skill correction.apply --op close-loop --arg "Finalize README" --json
openmy skill correction.apply --op typo --arg "Cload" --arg "Claude" --date 2026-04-08 --json
openmy skill correction.apply --op reject-decision --arg "要退休了" --json
openmy skill correction.apply --op merge-project --arg "openmy" --arg "OpenMy" --json
```

Pick the operation that matches the user's correction intent.
