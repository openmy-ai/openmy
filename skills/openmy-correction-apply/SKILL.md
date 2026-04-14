---
name: openmy-correction-apply
description: Use when closing loops, fixing transcript errors, rejecting false decisions, or merging duplicate projects
---

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

## Error Handling

If `correction.apply` fails:
1. Read `error_code` and `message`.
2. **Never pretend the correction succeeded.** If `ok: false`, tell the user plainly.
3. If the target item cannot be found, ask the user for the exact wording once.
4. If `close-loop` fails because there are no open loops at all, tell the user:
   > "目前没有可关闭的待办记录。这条可能还没被系统识别为待办，不影响使用。"
   Do NOT say "已经记下了" or imply the task was closed.
5. If the user insists, suggest running `context.query --kind open --json` to check what loops currently exist.
6. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
