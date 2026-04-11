# OpenMy Core Extraction Handoff

## Purpose

Let an agent produce the core structured extraction payload with its own model when OpenMy has no LLM key configured.

## Trigger

Use it when:
- `day.run` pauses before core extraction
- `health.check` shows `llm_available: false`
- distillation is already complete
- the user wants the agent to finish extraction instead of configuring a cloud key

## Action

- `openmy skill extract.core.pending --date YYYY-MM-DD --json`
- `openmy skill extract.core.submit --date YYYY-MM-DD --payload-file payload.json --json`

## Restrictions

- Do not edit `.meta.json` directly.
- Do not skip the schema returned by `extract.core.pending`.
- Do not fabricate historical dates when the transcript only gives relative time.
- Submit one normalized core payload object at a time.

## Output

- start with `human_summary`
- explain whether extraction is pending or already done
- if pending, say that transcript text and schema are ready
- if submitted, mention how many intents and facts were saved
- end with one concrete next step

## Agent Behavior

1. Call `extract.core.pending` first.
2. If `data.status` is `already_done`, go back to `day.run` to finish briefing and consolidation.
3. If pending, read `transcript_text`, `reference_date`, `scene_catalog`, and `output_schema`.
4. Generate one payload that matches the returned schema.
5. Submit it with `extract.core.submit`.
6. After submit succeeds, call `day.run --skip-transcribe` for the same date so OpenMy can finish briefing and consolidation.
