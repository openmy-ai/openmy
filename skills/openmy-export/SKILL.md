---
name: openmy-export
description: Use when configuring automatic export of daily summaries to the user's note system
---

# OpenMy Export

## Purpose

Configure automatic export so processed daily summaries can be saved into the user's note system.

## Trigger

Use it when:
- the user wants daily summaries saved automatically
- the user asks for Obsidian export
- the user asks for Notion export
- export is configured but not ready

## Action

- `openmy skill health.check --json`
- `openmy skill profile.set --export-provider obsidian --export-path "/path/to/vault" --json`
- `openmy skill profile.set --export-provider notion --export-key "secret" --export-db "database_id" --json`

## Restrictions

- Do not block the main audio pipeline if export fails.
- Do not ask for an Obsidian path before trying auto-detection.
- Do not guess a Notion database ID.

## Output

- explain which export target is selected
- explain whether it is configured and ready
- end with one concrete next setup step if anything is missing

## Agent Behavior

1. Run `health.check` first.
2. If export is already configured and ready, say so and stop.
3. If the user wants Obsidian:
   - auto-detect likely vault folders first
   - if a vault is found, run `profile.set --export-provider obsidian --export-path ... --json` immediately
   - then rerun `health.check` and confirm export is ready
4. If no Obsidian vault is found, ask one question about the note app or vault path.
5. If the user wants Notion:
   - ask for the API key and database ID
   - run `profile.set --export-provider notion --export-key ... --export-db ... --json`
   - rerun `health.check` and confirm export is ready
6. If later export fails, explain that day processing still finished and only export failed.

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - `missing_export_path` / `invalid_export_path` → ask for the correct Obsidian folder.
   - `missing_notion_export_fields` → ask for the missing Notion value.
   - `permission_denied` → tell the user which folder cannot be written.
3. Unknown export errors should be surfaced plainly, then route back to `openmy-health-check`.
4. Never pretend export is ready until `health.check` says it is ready.
