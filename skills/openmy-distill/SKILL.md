---
name: openmy-distill
description: Use when finishing missing scene summaries with the agent's own model because no LLM key is configured
---

# OpenMy Distill Handoff

## Purpose

Let an agent finish missing scene summaries with its own model when no LLM key is configured in OpenMy.

## Trigger

Use it when:
- `day.run` pauses after segmentation
- `health.check` shows `llm_available: false`
- scene summaries are missing
- the user wants to use the agent's own model instead of configuring a cloud key

## Action

- `openmy skill distill.pending --date YYYY-MM-DD --json`
- `openmy skill distill.submit --date YYYY-MM-DD --payload-file payload.json --json`

## Restrictions

- Do not edit `scenes.json` directly.
- Do not invent `scene_id` values.
- Do not submit empty summaries.
- Keep the summary style short, factual, and written in first person.

## Output

- start with `human_summary`
- explain whether distillation is still pending or already done
- if pending, mention how many scenes are left
- if submitted, mention how many summaries were saved
- end with one concrete next step

## Agent Behavior

1. Call `distill.pending` first.
2. If `data.status` is `already_done`, move on to `extract.core.pending`.
3. If scenes are pending, write 1-3 short sentences per scene, 30-80 Chinese characters total, using "我" as the subject.
4. Save the payload as JSON with `date` and `summaries` fields.
5. Submit with `distill.submit`.
6. If the submission clears all pending scenes, continue to `extract.core.pending`.
