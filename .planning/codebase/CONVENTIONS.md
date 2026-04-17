# Coding Conventions

**Analysis Date:** 2026-04-17

## Naming Patterns

**Files:**
- `snake_case.py` for Python modules, e.g. `skill_dispatch.py`, `audio_pipeline.py`
- `test_*.py` for tests in `tests/` and `tests/unit/`
- `openmy-*` for skill folders under `skills/`

**Functions:**
- `snake_case` for functions and helpers, including internal helpers like `_sync_runtime_overrides`
- `cmd_*` prefixes for command handlers in `src/openmy/commands/`
- `handle_*` prefixes for HTTP and skill action functions in `app/` and `src/openmy/skill_handlers/`

**Variables:**
- `snake_case` for normal variables
- `UPPER_SNAKE_CASE` for constants like `DEFAULT_STT_MODELS`, `RUN_STEPS`, `DATE_RE`
- Leading underscore for internal helpers and module-private globals

**Types / classes:**
- `PascalCase` for dataclasses and provider classes such as `JobRunner`, `ProviderRegistry`, `FriendlyCliError`
- Test classes use `Test*` naming with `unittest.TestCase`

## Code Style

**Formatting:**
- Ruff is the enforced linter from `pyproject.toml`
- Line length target is 100 characters
- Type hints are common across production code
- `from __future__ import annotations` appears broadly and should stay consistent in new Python modules

**Linting:**
- Run `ruff check .`
- Exceptions currently ignored in config: `E402`, `E741`, `F541`
- `.omx/` is excluded from Ruff

## Import Organization

**Order:**
1. `from __future__ import annotations`
2. Standard-library imports
3. Third-party imports
4. Local package imports

**Grouping:**
- Blank lines separate import groups
- Related local imports are often grouped in tuple unpacking style in `src/openmy/cli.py`

**Path aliases:**
- No custom Python import alias layer
- Imports are package-relative from `openmy.*` or module-relative inside `app/`

## Error Handling

**Patterns:**
- Raise domain-friendly exceptions inside services/providers; normalize at CLI / skill / HTTP boundaries
- CLI user-facing failures commonly go through `FriendlyCliError`
- Skill handlers return structured error payloads instead of leaking stack traces

**Error Types:**
- Throw when input, provider credentials, or runtime dependencies are missing
- Return structured JSON errors for HTTP/skill surfaces where the caller expects machine-readable status
- Preserve human-readable fix hints near provider failures, especially in `src/openmy/providers/`

## Logging

**Framework:**
- Rich console for CLI-facing status output via `src/openmy/commands/common.py`
- Plain appended log lines for local jobs in `app/job_runner.py`

**Patterns:**
- Human-readable progress messages over structured logging
- Long-running web jobs log per-step summaries and keep recent log lines in payloads
- No central observability library is present

## Comments

**When to Comment:**
- Comments often explain behavior contracts, migration notes, or why a compatibility path exists
- Chinese explanatory comments are common in source files and docs
- Avoid obvious line-by-line comments; most files rely on descriptive function names

**Docstrings:**
- Selective, not universal
- Often used on helpers where the behavior contract matters, e.g. `safe_write_json`

**TODO comments:**
- Ad hoc; no strict tag format is enforced
- Larger unfinished work is more often captured in `docs/` than inline TODOs

## Function Design

**Size:**
- Small focused helpers are common in service modules
- A few orchestration files remain large, especially `src/openmy/cli.py`, `src/openmy/commands/run.py`, and `src/openmy/services/extraction/extractor.py`

**Parameters:**
- Explicit parameters are preferred over hidden global state
- Runtime config still flows through env readers when provider/runtime behavior must stay centralized

**Return Values:**
- Service helpers usually return concrete payloads or dataclasses
- Skill and HTTP boundaries return dictionaries designed for JSON serialization
- Guard clauses and early returns are common

## Module Design

**Exports:**
- Named functions and classes dominate
- Package `__init__.py` files are lightweight and mostly mark package boundaries

**Compatibility layers:**
- The repo keeps explicit compatibility shims, e.g. `openmy/` bootstrap package and legacy payload builders in extraction
- When adding new behavior, prefer preserving the public action/CLI surface over renaming interfaces casually

---
*Convention analysis: 2026-04-17*
*Update when patterns change*
