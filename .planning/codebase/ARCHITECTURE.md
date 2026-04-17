# Architecture

**Analysis Date:** 2026-04-17

## Pattern Overview

**Overall:** Local-first Python monolith with three surfaces: CLI, localhost web UI, and stable skill JSON actions.

**Key Characteristics:**
- File-based state instead of a database
- Pipeline-oriented processing of daily audio into structured artifacts
- Provider boundary for STT / LLM / export integrations
- Separate human surface (`app/`) and agent surface (`src/openmy/skill_dispatch.py`) over the same data model

## Layers

**Entry Surface Layer:**
- Purpose: accept work from humans or agents
- Contains: `src/openmy/cli.py`, `src/openmy/commands/parser.py`, `app/http_handlers.py`, `src/openmy/skill_dispatch.py`
- Depends on: command handlers, payload builders, skill handlers
- Used by: terminal users, browser clients, agent skills

**Orchestration Layer:**
- Purpose: turn user intent into pipeline calls and status updates
- Contains: `src/openmy/commands/*.py`, `src/openmy/skill_handlers/*.py`, `app/pipeline_api.py`, `app/job_runner.py`
- Depends on: service layer and provider registry
- Used by: CLI surface, web UI, skill surface

**Service Layer:**
- Purpose: implement the domain pipeline and context engine
- Contains: `src/openmy/services/ingest/`, `cleaning/`, `segmentation/`, `distillation/`, `extraction/`, `briefing/`, `context/`, `query/`, `aggregation/`
- Depends on: provider layer, utils, filesystem
- Used by: commands, skill handlers, web payloads

**Provider / Adapter Layer:**
- Purpose: isolate external systems and system-native integrations
- Contains: `src/openmy/providers/`, `src/openmy/adapters/transcription/`, `src/openmy/adapters/screen_recognition/`
- Depends on: config and external SDKs/binaries
- Used by: service layer

**Persistence / Resource Layer:**
- Purpose: store artifacts and reusable dictionaries/config
- Contains: `data/`, `src/openmy/resources/`, `src/openmy/utils/io.py`, `src/openmy/utils/paths.py`
- Depends on: local filesystem only
- Used by: every higher layer

## Data Flow

**CLI day pipeline:**
1. User runs `openmy run ...` or `openmy quick-start ...`
2. `src/openmy/cli.py` routes into `src/openmy/commands/run.py`
3. `src/openmy/services/ingest/audio_pipeline.py` prepares chunks and calls the selected STT provider
4. Cleaning, segmentation, distillation, extraction, briefing, aggregation, and context services run in sequence
5. Results are written under `data/<date>/` and related aggregate files
6. Terminal view or local report reads those files back

**Local web pipeline:**
1. Browser hits `app/http_handlers.py`
2. Request handlers route to payload builders or `app/pipeline_api.py`
3. `app/job_runner.py` manages an in-memory job plus step/status snapshots
4. Pipeline execution ultimately calls the same command/service layer used by CLI flows
5. Browser polls job/status endpoints and renders day detail from JSON + markdown artifacts

**Skill pipeline:**
1. Agent invokes `openmy skill <action> --json`
2. `src/openmy/skill_dispatch.py` resolves the action
3. Skill handlers bridge either directly to data readers or to existing CLI commands
4. Stable JSON payloads come back without exposing internal module boundaries

**State Management:**
- Persistent state is file-based in `data/`
- Job state for the web UI is in-memory plus lightweight JSON persistence
- Configuration is env-driven with project-root discovery and optional overrides

## Key Abstractions

**ProviderRegistry:**
- Purpose: normalize STT, LLM, and export provider selection
- Examples: `src/openmy/providers/registry.py`, `src/openmy/providers/stt/*.py`
- Pattern: factory / registry

**JobRunner / JobHandle:**
- Purpose: manage long-running local UI tasks and step transitions
- Examples: `app/job_runner.py`
- Pattern: in-memory controller with mutable status snapshots

**Skill Action Bridge:**
- Purpose: keep a stable action contract for agents while reusing existing CLI logic
- Examples: `src/openmy/skill_dispatch.py`, `src/openmy/skill_handlers/day_pipeline.py`
- Pattern: façade over commands/services

**Atomic JSON writes:**
- Purpose: reduce corruption risk for frequently rewritten artifacts
- Examples: `src/openmy/utils/io.py`
- Pattern: sibling temp file + `os.replace`

## Entry Points

**CLI entry:**
- Location: `openmy = "openmy.cli:main"` in `pyproject.toml`
- Triggers: terminal invocation
- Responsibilities: parser setup, routing, top-level error handling, local report bootstrapping

**Local report server:**
- Location: `app/server.py`
- Triggers: `openmy view`, direct Python launch, or report launcher helpers
- Responsibilities: serve HTML/static assets and JSON endpoints on localhost

**Skill entry:**
- Location: `src/openmy/skill_dispatch.py`
- Triggers: `openmy skill ... --json`
- Responsibilities: stable contracts for agent workflows

## Error Handling

**Strategy:** fail fast inside services, then normalize at surface boundaries.

**Patterns:**
- CLI and provider boundaries use `FriendlyCliError` and translated hints
- Skill handlers return structured success/error payloads instead of raw tracebacks
- HTTP handlers convert invalid requests into status-coded JSON responses

## Cross-Cutting Concerns

**Logging / status:**
- Rich console output in CLI
- In-memory job logs in `app/job_runner.py`
- JSON status artifacts like `run_status.json` for day pipelines

**Validation:**
- Argparse validation at the CLI boundary
- Skill handler validation helpers in `src/openmy/skill_handlers/common.py`
- Date/path checks inside both CLI and HTTP surfaces

**Configuration:**
- Central env lookups in `src/openmy/config.py`
- Project/data-root discovery in `src/openmy/utils/paths.py`

---
*Architecture analysis: 2026-04-17*
*Update when major patterns change*
