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

## Output

- start with `human_summary`
- say whether installation is already ready or still missing pieces
- if setup was needed, say that the virtual environment and command entry are ready
- end with one concrete next step

## Steps

1. Detect Python version (`>= 3.10`)
2. Create virtual environment: `python3 -m venv .venv`
3. Install the project: `pip install -e .`
4. Copy `.env.example` to `.env` if missing
5. Verify `openmy --help`
6. Run `bash scripts/install-skills.sh`
7. Route to `openmy-health-check`
