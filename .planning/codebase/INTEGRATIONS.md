# External Integrations

**Analysis Date:** 2026-04-17

## APIs & External Services

**Cloud STT / LLM providers:**
- Gemini — used for STT and LLM summarization/extraction through `src/openmy/providers/stt/gemini.py`, `src/openmy/providers/llm/gemini.py`, and `src/openmy/adapters/transcription/gemini_cli.py`
  - SDK/Client: `google-genai`
  - Auth: `GEMINI_API_KEY`, `OPENMY_STT_API_KEY`, or `OPENMY_LLM_API_KEY`
  - Usage: transcription, distillation, extraction, role fallback
- Groq — STT-only integration in `src/openmy/providers/stt/groq_whisper.py`
  - Auth: `GROQ_API_KEY`
- DashScope — STT-only integration in `src/openmy/providers/stt/dashscope_asr.py`
  - Auth: `DASHSCOPE_API_KEY`
- Deepgram — STT-only integration in `src/openmy/providers/stt/deepgram.py`
  - Auth: `DEEPGRAM_API_KEY`

**Optional project export targets:**
- Notion — export provider in `src/openmy/providers/export/notion.py`
  - Auth: `NOTION_API_KEY`
  - Destination: `NOTION_DATABASE_ID`
- Obsidian — local vault export provider in `src/openmy/providers/export/obsidian.py`
  - Config: `OPENMY_OBSIDIAN_VAULT_PATH`

## Data Storage

**Databases:**
- None — there is no relational or hosted database in the repo
- Persistent state is file-based under `data/` via helpers like `src/openmy/utils/io.py`

**File Storage:**
- Local filesystem — primary storage for transcripts, scenes, briefs, context snapshots, and search index under `data/`
- `dist/` — packaged build artifacts for release
- `tests/fixtures/` — sample audio, scenes, and structured regression fixtures

**Caching / indexes:**
- Search index JSON in `data/search_index.json`, maintained by `src/openmy/services/query/search_index.py`
- In-memory job state for the local UI via `app/job_runner.py`

## Authentication & Identity

**App auth:**
- None for end users — the local report is a single-user localhost app served by `app/server.py`
- The main security boundary is loopback-only binding and project-local files, not user accounts

**Provider credentials:**
- All provider auth is env-var based, centralized in `src/openmy/config.py`
- Hugging Face token support exists for WhisperX diarization via `HF_TOKEN` / `HUGGINGFACE_TOKEN`

## Monitoring & Observability

**Error tracking:**
- No hosted error tracker like Sentry is configured
- CLI errors go through Rich output and `FriendlyCliError` handling in `src/openmy/commands/common.py`

**Operational logs:**
- Run progress and per-step status persist to day-local JSON files such as `run_status.json`
- Local web jobs keep transient logs in memory through `app/job_runner.py`

**Feedback / update tracking:**
- Local-only feedback metadata in `src/openmy/services/feedback.py`
- Update-check hints stored under `data/.update-check.json`

## CI/CD & Deployment

**Hosting:**
- No hosted app deployment target in the product itself; this is a local-first package

**Package publishing:**
- PyPI publishing pipeline in `.github/workflows/publish.yml`
- GitHub Release creation on version tags in the same workflow

**CI pipeline:**
- GitHub Actions in `.github/workflows/test.yml`
  - Matrix: `ubuntu-latest`, `macos-latest`
  - Runs: install, `ruff check .`, smoke checks, `python3 -m pytest tests -q`
- README sync guard in `.github/workflows/readme-sync-guard.yml`

## Environment Configuration

**Development:**
- `.env.example` documents expected local variables
- Project `.env` is created by `scripts/install-skills.sh` when missing
- Common keys: `OPENMY_STT_PROVIDER`, `OPENMY_LLM_PROVIDER`, `OPENMY_AUDIO_SOURCE_DIR`, provider API keys, export keys

**Staging / production:**
- No separate staged environment model is encoded in the app runtime
- The main separation is per-machine local configuration and whichever provider keys are installed on that machine

## Webhooks & Callbacks

**Incoming:**
- None in the product runtime

**Outgoing:**
- None in the product runtime
- External communication is pull-style API invocation from providers, not webhook-driven orchestration

---
*Integration audit: 2026-04-17*
*Update when adding/removing external services*
