# OpenMy Routing Rules

The router skill decides the workflow.
It does not execute details itself.

| Intent | Sub-skill |
|---|---|
| start a new OpenMy conversation and get bearings | openmy-startup-context |
| ask what the user is working on now | openmy-context-read |
| search projects, people, open items, or evidence | openmy-context-query |
| process or re-run one day | openmy-day-run |
| inspect one processed day | openmy-day-view |
| correct errors or close loops | openmy-correction-apply |
| review the overall state before deciding | openmy-status-review |
| initialize vocab files | openmy-vocab-init |
| initialize or update user profile | openmy-profile-init |
| verify environment and engine readiness | openmy-health-check |

Rules:
- keep the router skill thin
- prefer one sub-skill at a time
- use `openmy-status-review` when the next step is unclear
- treat `openmy agent` as a compatibility alias, not the main path
