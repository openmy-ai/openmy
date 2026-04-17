# Codebase Structure

**Analysis Date:** 2026-04-17

## Directory Layout

```text
openmy-clean/
├── app/                # Localhost report server and browser-facing API
├── data/               # Runtime artifacts, context snapshots, search index
├── docs/               # Product docs, plans, examples, audits
├── openmy/             # Repo-root bootstrap shim for `python -m openmy`
├── scripts/            # Installer and repo maintenance scripts
├── skills/             # Agent skill definitions and references
├── src/openmy/         # Core package source
│   ├── adapters/       # Native or tool-specific bridges
│   ├── commands/       # CLI command implementations
│   ├── domain/         # Shared data models
│   ├── providers/      # STT / LLM / export provider boundary
│   ├── services/       # Pipeline and context-engine logic
│   ├── skill_handlers/ # Stable JSON action handlers
│   └── utils/          # Paths, I/O, errors, helpers
├── tests/              # Automated tests and fixtures
├── dist/               # Built release artifacts
├── AGENTS.md           # Codex / agent instructions for this repo
└── pyproject.toml      # Package and tool configuration
```

## Directory Purposes

**`app/`:**
- Purpose: local web UI and lightweight JSON API
- Contains: `server.py`, `http_handlers.py`, `payloads.py`, `job_runner.py`, `pipeline_api.py`, `static/`
- Key files: `app/server.py`, `app/http_handlers.py`, `app/index.html`
- Subdirectories: `app/static/` for JS, CSS, icons, and vendored browser assets

**`src/openmy/commands/`:**
- Purpose: terminal-facing commands
- Contains: `run.py`, `show.py`, `context.py`, `screen.py`, `correct.py`, `parser.py`
- Key files: `src/openmy/commands/run.py`, `src/openmy/commands/show.py`, `src/openmy/commands/common.py`
- Subdirectories: flat command collection

**`src/openmy/services/`:**
- Purpose: pipeline stages and durable domain services
- Contains: stage folders like `ingest/`, `cleaning/`, `segmentation/`, `distillation/`, `extraction/`, `briefing/`, `context/`, `query/`, `aggregation/`
- Key files: `src/openmy/services/ingest/audio_pipeline.py`, `src/openmy/services/context/consolidation.py`, `src/openmy/services/briefing/generator.py`
- Subdirectories: one per major domain concern

**`src/openmy/providers/`:**
- Purpose: isolate third-party providers and export backends
- Contains: `stt/`, `llm/`, `export/`, plus `registry.py`
- Key files: `src/openmy/providers/registry.py`, `src/openmy/providers/stt/faster_whisper.py`, `src/openmy/providers/llm/gemini.py`
- Subdirectories: provider family splits

**`src/openmy/skill_handlers/`:**
- Purpose: stable agent-action layer above commands/services
- Contains: `day_pipeline.py`, `context_profile.py`, `health_aggregate.py`, `common.py`
- Key files: `src/openmy/skill_dispatch.py`, `src/openmy/skill_handlers/day_pipeline.py`
- Subdirectories: flat handler collection

**`skills/`:**
- Purpose: agent-facing workflow documents for OpenMy
- Contains: `skills/openmy/` router plus sub-skills like `skills/openmy-day-run/`, `skills/openmy-health-check/`
- Key files: `skills/openmy/SKILL.md`, `skills/openmy/references/`
- Subdirectories: one folder per skill

**`tests/`:**
- Purpose: regression coverage
- Contains: top-level integration-style tests, `tests/unit/`, and `tests/fixtures/`
- Key files: `tests/unit/test_cli.py`, `tests/unit/test_app_server.py`, `tests/test_skill_agent_scenarios.py`
- Subdirectories: `unit/` and `fixtures/`

## Key File Locations

**Entry Points:**
- `src/openmy/cli.py`: main CLI router
- `src/openmy/skill_dispatch.py`: stable skill JSON dispatcher
- `app/server.py`: localhost server bootstrap
- `openmy/__main__.py`: source-checkout `python -m openmy` shim

**Configuration:**
- `pyproject.toml`: package metadata, pytest, Ruff
- `.env.example`: documented env contract
- `src/openmy/config.py`: runtime config accessors
- `src/openmy/utils/paths.py`: project/data root resolution

**Core Logic:**
- `src/openmy/services/ingest/audio_pipeline.py`: audio prep + STT orchestration
- `src/openmy/services/segmentation/segmenter.py`: scene generation
- `src/openmy/services/distillation/distiller.py`: scene summary generation
- `src/openmy/services/extraction/extractor.py`: structured extraction
- `src/openmy/services/context/consolidation.py`: cross-day active context

**Testing:**
- `tests/unit/`: unit and service-heavy regression tests
- `tests/fixtures/`: audio and structured sample data
- `.github/workflows/test.yml`: CI execution contract

**Documentation:**
- `README.md`: primary product and install guide
- `docs/architecture.md`: high-level system overview
- `docs/plans/` and `docs/specs/`: design history and planning artifacts
- `AGENTS.md`: repo-specific agent behavior rules

## Naming Conventions

**Files:**
- `snake_case.py` for Python modules, e.g. `audio_pipeline.py`
- `UPPERCASE.md` for top-level governance docs, e.g. `AGENTS.md`
- `test_*.py` for tests, primarily under `tests/unit/`

**Directories:**
- `snake_case` or short lowercase names for source directories
- `openmy-*` prefixes for skill directories under `skills/`

**Special Patterns:**
- `__init__.py` for package boundaries
- `.example` resources for local-copy templates like `src/openmy/resources/corrections.example.json`
- `*.bak` temporary backups in rerun flows from `src/openmy/commands/run.py`

## Where to Add New Code

**New pipeline feature:**
- Primary code: `src/openmy/services/<domain>/`
- CLI hook: `src/openmy/commands/`
- Skill bridge if needed: `src/openmy/skill_handlers/`
- Tests: `tests/unit/`

**New provider integration:**
- Implementation: `src/openmy/providers/<family>/`
- Registration: `src/openmy/providers/registry.py`
- Config surface: `src/openmy/config.py`
- Tests: `tests/unit/test_provider_*` or focused provider tests

**New local web behavior:**
- API/read model: `app/`
- Browser rendering: `app/static/`
- Tests: `tests/unit/test_app_server.py` and `tests/unit/test_web_smoke.py`

**New agent skill flow:**
- Skill docs: `skills/`
- Stable action support: `src/openmy/skill_dispatch.py` and `src/openmy/skill_handlers/`

## Special Directories

**`data/`:**
- Purpose: runtime-generated local artifacts
- Source: produced by pipeline execution and local UI usage
- Committed: mostly no; it is user/machine state

**`dist/`:**
- Purpose: packaged release outputs
- Source: build process / publish flow
- Committed: yes in this checkout, but it is generated output

**`.omx/`:**
- Purpose: local session/handoff state for OMX workflows
- Source: tooling-generated
- Committed: no

---
*Structure analysis: 2026-04-17*
*Update when directory structure changes*
