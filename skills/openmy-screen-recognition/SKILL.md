# OpenMy Screen Recognition

## Purpose

Explain and manage screen recognition, the feature that matches what the user said with what they were doing on screen.

## Trigger

Use it when:
- the user asks what screen recognition does
- the user wants to enable or disable screen recognition
- the user wants richer context from screen activity
- screen recognition is enabled but the local service is not reachable

## Action

- `openmy skill health.check --json`

## Restrictions

- Never enable it without explicit user consent.
- Always explain what it does before asking for consent.
- If the local service is not running, mention it once and stop nagging.

## Output

- explain what the feature does in plain language
- explain whether it is enabled and whether the local service is reachable
- end with a clear suggestion

## How it works

1. A background service captures periodic screen snapshots.
2. It reads text from the screen.
3. OpenMy matches spoken moments with screen activity from the same time window.
4. This makes the daily summary much richer.

## Privacy

- All data stays on your machine.
- Sensitive apps can be filtered out.
- Specific apps can be excluded in settings.

## Agent Behavior

- Explain the feature before asking whether to enable it.
- If the user says no, keep going without it.
- If the local service is unavailable, say so once and move on.
