---
name: openmy-install
description: Use when verifying the runtime environment is ready or helping the user finish first-time installation
---

# OpenMy Install

## Purpose

Guide the agent through first-time installation when `openmy` command is not available.

## Trigger

Use it when:
- `openmy` command is not available
- the user just cloned the repo
- `health.check` fails with import errors

## Action

- `openmy skill health.check --json`

## Restrictions

- Do NOT tell the user to do these steps manually.
- Run the setup yourself whenever the machine is ready.
- If Python version is too low, tell the user one concrete command to fix it.
- Do not skip a failed step and jump ahead.

## Output

- start with `human_summary`
- say whether installation is already ready or still missing pieces
- if setup was needed, say that the virtual environment and command entry are ready
- end with one concrete next step

## Steps

1. Confirm you are in an OpenMy repo.
   - If `pyproject.toml` is missing or does not declare `openmy`, switch to the correct repo root first.
2. Check Python version (`>= 3.10`).
3. Create virtual environment: `python3 -m venv .venv`
4. Install the project with the repo-local interpreter: `.venv/bin/pip install -e .`
5. Copy `.env.example` to `.env` if missing.
6. Verify the command entry with `.venv/bin/openmy --help`.
7. Run `bash scripts/install-skills.sh`.
8. Route to `openmy-health-check`.

## Error Handling

If any command returns `ok: false` or a shell step fails:
1. Read the exact error message first.
2. Common recovery:
   - Python missing or too old → show one install command for this machine.
   - `.venv` creation failed → check disk space and write permission.
   - install failed because `ffmpeg` is missing → install `ffmpeg`, then retry once.
   - import error after install → rerun the editable install once, then route to `openmy-health-check`.
3. Never ask the user to open a terminal and do it themselves.
4. Never retry the same failing step more than once without reporting the failure.
