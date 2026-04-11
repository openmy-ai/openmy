# Changelog

## [0.2.0] - 2026-04-12

### Features
- Agent-native handoff for scene distillation and core extraction through `distill.pending`, `distill.submit`, `extract.core.pending`, and `extract.core.submit`
- `day.run` now pauses at the right handoff step when no LLM key is configured, instead of blindly skipping ahead
- `health.check` now reports whether LLM processing is available and points agents to the handoff flow
- New skill guides for agent-side distillation and extraction handoff
- `quick-start --demo` now runs a bundled sample without asking for cloud keys first
- Query and day status lookups now reuse `search_index.json` instead of reopening every day file

### Fixes
- Health and web surfaces no longer leak raw keys or trust unsafe transcript-shaped input
- Reruns now preserve human-confirmed roles, protect old outputs with backups, and avoid duplicate vault appends
- Runtime timestamps now go through shared time helpers instead of hand-written `+08:00`
- Scene distillation and cloud chunk transcription now run in parallel with retry/backoff on temporary `429/503` failures
- Core extraction meta writes and search index writes now use atomic JSON writes
- Open-source repo hygiene now includes issue forms, Dependabot, Ruff checks, conduct rules, and security guidance

## [0.1.0-alpha] - 2026-04-11

### Features
- Audio transcription with Gemini API, faster-whisper, and FunASR backends
- Rule-based text cleaning that preserves conversational rhythm
- Automatic scene segmentation by time windows
- AI-generated first-person daily briefing summaries
- Structured extraction of todos, facts, and decisions
- Temporal adjudication that separates completed actions from future intent
- Cross-day active_context memory aggregation with layered context views
- Optional screen recognition with application usage rollups
- Local web report for reviewing each day at a glance
- Skill endpoints for agent-facing context queries and day processing
- One-command onboarding via `openmy quick-start your-audio.wav`
