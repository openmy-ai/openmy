# Testing Patterns

**Analysis Date:** 2026-04-17

## Test Framework

**Runner:**
- `pytest` is the repo-wide runner, configured in `pyproject.toml`
- The actual test authoring style is mostly `unittest.TestCase`

**Assertion Library:**
- Standard `unittest` assertions dominate
- `pytest` is used for parametrization, skips, and runner ergonomics in selected files such as `tests/test_skill_agent_scenarios.py`

**Run Commands:**
```bash
python3 -m pytest tests -q          # run the full suite
python3 -m pytest tests -v          # verbose full suite
python3 -m pytest tests/unit/test_cli.py -q
ruff check .                        # lint gate run alongside tests
```

## Test File Organization

**Location:**
- `tests/unit/` holds most regression coverage
- `tests/fixtures/` stores audio and JSON/scene fixtures
- A few broader workflow tests live directly under `tests/`

**Naming:**
- Unit tests: `tests/unit/test_*.py`
- Broader scenario tests: `tests/test_*.py`
- Fixtures: stable filenames describing sample inputs, e.g. `sample.wav`

**Structure:**
```text
tests/
├── fixtures/
│   ├── *.wav
│   ├── *.json
│   └── *.scenes.json
├── unit/
│   ├── test_cli.py
│   ├── test_app_server.py
│   ├── test_ingest_audio_pipeline.py
│   └── ...
├── test_monthly_aggregation.py
├── test_weekly_aggregation.py
└── test_skill_agent_scenarios.py
```

## Test Structure

**Suite Organization:**
```python
class TestOpenMyCli(unittest.TestCase):
    def test_openmy_without_args_shows_main_menu(self):
        ...
```

**Patterns:**
- `tempfile.TemporaryDirectory()` is the default isolation strategy for filesystem-heavy tests
- Helper methods inside the test class build and clean day directories
- `patch`, `patch.object`, and `patch.dict` are used heavily for env vars, provider calls, and filesystem indirection

## Mocking

**Framework:**
- `unittest.mock` is the standard mocking tool

**Patterns:**
```python
with patch.object(app_server, "DATA_ROOT", data_root):
    payload = app_server.get_context_payload()

with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
    ...
```

**What to Mock:**
- External APIs and provider classes
- Environment variables
- FFmpeg / FFprobe helpers
- Local filesystem roots and report state

**What NOT to Mock:**
- Plain payload shaping logic when direct file fixtures are practical
- JSON serialization helpers when the test is explicitly verifying disk output

## Fixtures and Factories

**Test Data:**
- Realistic fixture files live under `tests/fixtures/`
- Many tests build temporary day workspaces on disk rather than relying on abstract factories
- Reusable helper loaders exist, e.g. `tests/unit/fixture_loader.py`

**Location:**
- Shared binary/JSON fixtures: `tests/fixtures/`
- Ad hoc factories/helpers: inside individual test classes

## Coverage

**Requirements:**
- No explicit percentage threshold is enforced in repo config
- CI expectation is broad regression coverage rather than a published coverage number

**Configuration:**
- `pytest` testpaths and pythonpath are set in `pyproject.toml`
- CI runs lint + smoke + full test suite in `.github/workflows/test.yml`

## Test Types

**Unit Tests:**
- Dominant test type
- Scope: individual commands, services, payload builders, providers
- Mocking: extensive, especially for env and I/O boundaries

**Integration / workflow tests:**
- Scenario-style tests cover CLI/skill contracts and aggregation behavior
- Examples: `tests/test_skill_agent_scenarios.py`, `tests/test_monthly_aggregation.py`

**Web smoke tests:**
- Python-based local-server tests, not a separate JS E2E framework
- Examples: `tests/unit/test_web_smoke.py`, `tests/unit/test_app_server.py`

## Common Patterns

**Async / long-running behavior:**
- Background job behavior is usually tested by polling helper methods like `wait_for_job_status`
- Concurrency is simulated with fake executors or mocked time/sleep in files like `tests/unit/test_ingest_audio_pipeline.py`

**Error Testing:**
- Expected-failure paths usually assert user-facing messages or structured error payloads
- Provider credential tests check exact missing-key hints

**Snapshot Testing:**
- Not used

## CI Contract

- `.github/workflows/test.yml` runs on both Ubuntu and macOS
- CI smoke-checks `openmy --help` and `openmy skill health.check --json`
- Release flow in `.github/workflows/publish.yml` depends on the test workflow passing first

---
*Testing analysis: 2026-04-17*
*Update when test patterns change*
