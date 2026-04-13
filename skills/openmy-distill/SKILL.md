---
name: openmy-distill
description: Use when finishing missing scene summaries with the agent's own model because no LLM key is configured
---

# OpenMy Distill Handoff

## Purpose

Let an agent finish missing scene summaries with its own model when OpenMy has no LLM key configured.

## Trigger

Use it when:
- `day.run` stops after segmentation
- `health.check` shows `llm_available: false`
- scene summaries are missing
- the user prefers the agent path, or has not expressed any preference yet

## Action

- `openmy skill distill.pending --date YYYY-MM-DD --json`
- `openmy skill distill.submit --date YYYY-MM-DD --payload-file /tmp/openmy-distill-YYYY-MM-DD.json --json`

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
3. If scenes are pending, default to the agent-side path unless the user explicitly asked to configure a key instead.
4. Write 1-3 short sentences per scene, 30-80 Chinese characters total, using `我` as the subject.
5. Save the payload to `/tmp/openmy-distill-YYYY-MM-DD.json`.
6. Submit with `distill.submit`.
7. If the submission clears all pending scenes, continue to `extract.core.pending`.
8. Clean up the temp payload file after a successful submit.

## Safety Filter Behavior

- Some cloud summaries can be skipped by the Gemini safety filter.
- The pipeline keeps going when that happens; it does not stop the whole day.
- A skipped scene may end with an empty summary, so the agent should treat that as expected partial output instead of a pipeline crash.

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - `missing_scenes` → rerun `day.run` with audio
   - `invalid_scene_id` / `invalid_payload` → reread pending scenes and regenerate once
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
