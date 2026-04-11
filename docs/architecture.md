# OpenMy Architecture

OpenMy turns raw personal signals into structured daily context for humans and agents.

## High-level flow

1. **Ingest** — import audio and prepare transcription chunks
2. **Transcribe** — run STT through Gemini, faster-whisper, or FunASR
3. **Clean** — apply deterministic cleanup and typo correction rules
4. **Segment** — split transcripts into time-based scene blocks
5. **Distill** — generate short first-person summaries for each scene
6. **Extract** — identify events, intents, facts, and decisions
7. **Briefing** — compose the daily report shown in the local web UI
8. **Context** — aggregate cross-day memory into `active_context`
9. **Skills** — expose stable JSON actions for agent consumption

## Repository layout

- `openmy/` — repo-root bootstrap shim so `python -m openmy` works from a source checkout
- `src/openmy/commands/` — CLI command entrypoints
- `src/openmy/providers/` — STT / LLM provider boundary
- `src/openmy/services/` — pipeline stages and supporting services
- `app/` — local report UI and lightweight HTTP server
- `tests/` — automated tests
- `skills/` — agent-facing skill definitions

## Runtime model

- User-specific data lives under `data/`
- Private typo dictionaries live in ignored local resource files
- Checked-in `*.example` resource files document the expected format without storing personal content
- The local web UI is the primary human-facing surface; skills are the primary agent-facing surface
