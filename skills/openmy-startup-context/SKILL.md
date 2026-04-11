# OpenMy Startup Context

## Purpose

Use this skill at the start of an OpenMy conversation.
Pull the latest context and status before choosing the next workflow.

## Trigger

Use it when:
- a new OpenMy conversation starts
- you need the current focus before doing anything else
- you need to know whether onboarding is still incomplete

## Action

- `openmy skill context.get --level 0 --json`
- `openmy skill status.get --json`

## Restrictions

- Do not ask the user to type commands.
- Do not edit context files directly.
- Do not jump into day processing until you know the current state.

## Output

- lead with `human_summary`
- mention the top current focus
- mention whether onboarding is incomplete
- if the next step is unclear, route to `openmy-status-review`

## Agent Behavior After Reading Context

Do not just report counts.
Turn the snapshot into a next move.

1. If an open loop has been around for more than 3 days, ask whether it is still active.
2. If recent days have no data, ask whether recordings exist.
3. Mention the last obvious focus area.
4. If profile or vocab is missing, start onboarding.
5. If this is the first conversation ever, run `health.check` before anything else.
