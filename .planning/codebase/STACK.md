# Technology Stack

**Analysis Date:** 2026-04-17

## Languages

**Primary:**
- Python 3.10+ — all application logic in `src/openmy/`, the local web server in `app/`, and test code in `tests/`

**Secondary:**
- JavaScript — browser-side UI logic in `app/static/app.js`
- HTML/CSS — local report shell in `app/index.html` and `app/static/style.css`
- Bash — installation and repo tooling in `scripts/install-skills.sh`
- Swift — macOS screen-recognition helpers in `src/openmy/services/screen_recognition/*.swift`

## Runtime

**Environment:**
- Python 3.10+ — required by `pyproject.toml`
- Local process runtime — CLI entrypoint `openmy` and local HTTP server `app/server.py`
- FFmpeg / FFprobe — required by `src/openmy/services/ingest/audio_pipeline.py`
- macOS system tools for screen capture — `swiftc`, `screencapture`, and frontmost-app helpers used by `src/openmy/services/screen_recognition/`

**Package Manager:**
- `pip` for normal installation (`pip install -e .` in README and CI)
- `uv` is present via `uv.lock`, but the repo is still Python-package first
- Lockfile: `uv.lock` present

## Frameworks

**Core:**
- Standard-library CLI + service modules — command routing built in `src/openmy/cli.py` and `src/openmy/commands/`
- Standard-library HTTP server — local web UI served by `app/server.py` and `app/http_handlers.py`

**Testing:**
- `pytest` — top-level runner configured in `pyproject.toml`
- `unittest` — dominant test style across `tests/unit/*.py`

**Build/Dev:**
- Hatchling — package build backend from `pyproject.toml`
- Ruff — linting configured in `pyproject.toml`

## Key Dependencies

**Critical:**
- `rich` — terminal UI and human-readable CLI output in `src/openmy/cli.py`
- `watchdog` — directory watching for audio ingestion via `src/openmy/services/watcher.py`
- `google-genai` — cloud Gemini path for STT / summarization when installed via `[cloud]`
- `faster-whisper` — local general-purpose STT via `src/openmy/providers/stt/faster_whisper.py`
- `funasr`, `modelscope`, `huggingface_hub` — local Chinese STT stack via `src/openmy/providers/stt/funasr.py`
- `whisperx` — optional alignment / diarization enrichment via `src/openmy/services/ingest/transcription_enrichment.py`

**Infrastructure:**
- FFmpeg/FFprobe — chunking, normalization, and duration probing in `src/openmy/services/ingest/audio_pipeline.py`
- GitHub Actions — CI and publish workflows in `.github/workflows/`

## Configuration

**Environment:**
- Project-level `.env` loaded from `src/openmy/utils/paths.py` and helper functions in `src/openmy/commands/common.py`
- Example env contract in `.env.example`
- Key config domains: STT provider choice, LLM provider choice, export targets, screen-context toggles, data-root overrides

**Build:**
- `pyproject.toml` — package metadata, dependencies, pytest, Ruff
- `uv.lock` — locked dependency snapshot for uv-based installs
- `.github/workflows/test.yml` — lint + test CI contract

## Platform Requirements

**Development:**
- macOS and Linux are both exercised in CI via `.github/workflows/test.yml`
- macOS is the richest environment because screen-recognition helpers depend on Apple-native tools in `src/openmy/services/screen_recognition/`
- A local virtualenv is the default developer path (`.venv/` plus `scripts/install-skills.sh`)

**Production:**
- Distributed as a PyPI package and source checkout
- Runs as a local, user-owned process instead of a hosted multi-tenant service
- The local report defaults to loopback-only binding in `app/server.py`

---
*Stack analysis: 2026-04-17*
*Update after major dependency changes*
