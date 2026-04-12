# OpenMy Skill Action Contracts

The stable backend entrypoint for agents is:

```bash
openmy skill <action> --json
```

Current actions:

```bash
openmy skill context.get --level 0 --json
openmy skill context.query --kind project --query OpenMy --json
openmy skill day.get --date YYYY-MM-DD --json
openmy skill day.run --date YYYY-MM-DD --audio a.wav --json
openmy skill distill.pending --date YYYY-MM-DD --json
openmy skill distill.submit --date YYYY-MM-DD --payload-file payload.json --json
openmy skill extract.core.pending --date YYYY-MM-DD --json
openmy skill extract.core.submit --date YYYY-MM-DD --payload-file payload.json --json
openmy skill aggregate --week YYYY-Www --json
openmy skill aggregate --month YYYY-MM --json
openmy skill aggregate.weekly --week YYYY-Www --json
openmy skill aggregate.monthly --month YYYY-MM --json
openmy skill correction.apply --op close-loop --arg "Task Title" --json
openmy skill status.get --json
openmy skill vocab.init --json
openmy skill profile.get --json
openmy skill profile.set --name "User Name" --language zh-CN --timezone Asia/Shanghai --json
openmy skill health.check --json
```

Success shape:

```json
{
  "ok": true,
  "action": "context.get",
  "version": "v1",
  "data": {},
  "human_summary": "Recent focus: OpenMy.",
  "artifacts": {},
  "next_actions": []
}
```

Failure shape:

```json
{
  "ok": false,
  "action": "day.run",
  "version": "v1",
  "error_code": "missing_audio",
  "message": "No audio provided and no existing transcript data found.",
  "hint": "Pass --audio, or make sure data already exists for that date."
}
```

Rules:
- `--json` output must be pure JSON
- `action` and `version` must stay stable
- every success payload must include `human_summary`
- sub-skills must call only stable actions, never internal modules


Agent handoff contracts:

- `distill.pending` returns scenes that still need `summary`.
- `distill.submit` accepts:

```json
{
  "date": "2026-04-11",
  "summaries": [
    {"scene_id": "s01", "summary": "我把关键决定记下来了。"}
  ]
}
```

- `extract.core.pending` returns transcript text, reference date, scene catalog, and output schema.
- `extract.core.submit` accepts one normalized core extraction payload and writes `{date}.meta.json`.
- `aggregate` routes to weekly or monthly aggregation based on `--week` / `--month`.
- `aggregate.weekly` writes `data/weekly/{week}.json`.
- `aggregate.monthly` writes `data/monthly/{month}.json`.
- If `health.check` shows `llm_available: false`, agents may finish distillation and extraction with their own model, then call `day.run` again to finish briefing and consolidation.


Automatic export contract:

- `openmy skill day.run --json` may export the generated daily briefing automatically when `OPENMY_EXPORT_PROVIDER` is configured.
- `openmy skill health.check --json` reports whether export is configured and ready.
- No separate export action is required for the automatic daily-briefing path.
