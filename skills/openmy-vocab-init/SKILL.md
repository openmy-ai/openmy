---
name: openmy-vocab-init
description: Use when initializing vocabulary files or gathering names, products, and domain terms that speech-to-text often gets wrong
---

# OpenMy Vocab Init

## Purpose

Initialize the personal vocabulary files and gather names, products, and domain terms that speech-to-text often gets wrong.

## Trigger

Use it when:
- vocab files do not exist yet
- transcript errors keep showing up on names or terms
- the user is onboarding OpenMy for the first time
- a new proper noun appears often in conversation

## Action

- `openmy skill vocab.init --json`

## Restrictions

- Do not edit `vocab.txt` or `corrections.json` directly inside this skill.
- Do not ask a long onboarding questionnaire.
- Do not skip obvious recurring names, projects, devices, or tools.

## Output

- say whether files were created or already existed
- tell the user what terms you added automatically
- ask only one follow-up question if anything important is still missing

## Agent Behavior

1. Run `vocab.init --json` first.
2. Auto-detect likely proper nouns from recent conversation, profile, and current project context.
3. Batch-add the obvious recurring terms silently by updating the vocab workflow through the normal correction path later when needed.
4. Tell the user what was added.
5. Ask one question: what important name or term is still missing?
6. If the user says nothing is missing, stop.

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - missing files example → rerun `vocab.init` once.
   - permission denied → tell the user the vocab files cannot be created in the current data directory.
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
