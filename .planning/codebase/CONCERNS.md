# Codebase Concerns

**Analysis Date:** 2026-04-17

## Tech Debt

**Large orchestration entrypoints:**
- Issue: routing and orchestration are still concentrated in files like `src/openmy/cli.py`, `src/openmy/commands/run.py`, and `src/openmy/services/extraction/extractor.py`
- Why: the repo has been incrementally split, but core orchestration still holds many compatibility branches
- Impact: small changes can have wide blast radius across CLI, skill, and local web surfaces
- Fix approach: keep peeling orchestration into focused command/service helpers without changing public behavior

**Dual human/agent surfaces over the same files:**
- Issue: CLI, skill JSON actions, and web payload builders all reuse the same artifacts under `data/`
- Why: OpenMy intentionally serves both humans and agents from one local state store
- Impact: schema drift or partial reruns can break one surface while another appears healthy
- Fix approach: keep compatibility adapters explicit and add contract tests whenever artifact shape changes

## Known Bugs

**Original recording time can still be lost in multi-file runs:**
- Symptoms: event ordering and time blocks become distorted after batch-like audio handling
- Trigger: multi-segment ingestion where original recording start times are not preserved cleanly
- Workaround: re-run affected days using original source ordering when possible
- Root cause: documented but not fully eliminated in the time propagation path around `src/openmy/services/ingest/audio_pipeline.py` and downstream segmentation
- Blocked by: careful refactor of timestamp propagation without regressing existing day pipelines

**Provider stability can block later pipeline stages:**
- Symptoms: STT or LLM stages fail or hang when cloud credentials are missing or the provider is flaky
- Trigger: using Gemini / Groq / DashScope / Deepgram paths without healthy provider state
- Workaround: switch to local providers or agent-side follow-up paths where available
- Root cause: later stages still depend on external provider availability unless explicitly degraded

## Security Considerations

**Local web UI trusts localhost as the main boundary:**
- Risk: if the server is rebound off loopback or proxied carelessly, personal context files become reachable without auth
- Current mitigation: default host is `127.0.0.1` in `app/server.py`
- Recommendations: preserve loopback-only defaults and review carefully before exposing the server remotely

**Project-local secrets live in `.env`:**
- Risk: provider keys can leak if copied into docs, logs, screenshots, or committed by mistake
- Current mitigation: `.env.example` documents keys separately; provider modules only reference env-var names
- Recommendations: keep generated docs secret-scanned and never quote actual values in committed artifacts

## Performance Bottlenecks

**Filesystem-heavy daily pipeline:**
- Problem: the pipeline repeatedly reads and rewrites day-local JSON/markdown artifacts
- Measurement: no single benchmark is committed, but the design clearly scales with file count and artifact size
- Cause: local-first architecture plus atomic-write semantics in `src/openmy/utils/io.py`
- Improvement path: preserve file safety first; only add incremental indexing/caching where profiling proves pain

**Web job state is mostly in memory:**
- Problem: long-running report jobs depend on `app/job_runner.py` state in the server process
- Measurement: durability is process-bound rather than database-backed
- Cause: the local UI is designed as a lightweight companion, not a durable background service
- Improvement path: if the UI becomes mission-critical, persist richer job state and replay recovery more formally

## Fragile Areas

**Compatibility payload layer in extraction:**
- Why fragile: `src/openmy/services/extraction/extractor.py` maintains legacy-compatible meta payload shapes while adding new fields
- Common failures: one consumer starts reading a new field while another still depends on the old alias
- Safe modification: update payload builders and all known consumers together; add regression tests first
- Test coverage: decent, but compatibility branches still need careful manual review

**Screen-recognition stack:**
- Why fragile: `src/openmy/services/screen_recognition/` mixes Python, Swift helpers, OS tools, and privacy filters
- Common failures: machine-specific tool availability, timing issues, or OS behavior changes
- Safe modification: change one boundary at a time and verify on a real macOS machine
- Test coverage: mixed; business logic has coverage, native/runtime edges remain harder to prove in CI

## Scaling Limits

**Single-user local-state design:**
- Current capacity: one user per local checkout and whatever that machine can process
- Limit: no shared multi-user coordination model, no hosted database, no auth layer
- Symptoms at limit: collaboration becomes file-sharing and manual process coordination
- Scaling path: would require a very different hosted architecture, not an incremental tweak

## Dependencies at Risk

**Optional provider ecosystem drift:**
- Risk: cloud STT and LLM SDKs, plus WhisperX / FunASR ecosystems, can change independently of the core app
- Impact: install paths and enrichment modes can break without core logic changes
- Migration plan: keep provider wrappers thin and centralize selection in `src/openmy/providers/registry.py` and `src/openmy/config.py`

## Missing Critical Features

**No durable browser-auth/user model:**
- Problem: the local report is intentionally single-user and unauthenticated
- Current workaround: rely on localhost-only serving
- Blocks: safe remote sharing or hosted team use
- Implementation complexity: high; would change product shape, not just add a page

## Test Coverage Gaps

**Real browser E2E coverage is thin in-repo:**
- What's not tested: full browser-user flows beyond Python-based smoke tests
- Risk: UI state sync bugs can sneak through even when payload tests pass
- Priority: medium
- Difficulty to test: local-first flows and machine-specific data make full browser automation noisier

**Native screen-capture runtime edges:**
- What's not tested: true end-to-end behavior of Swift helpers and system capture tools under varied macOS setups
- Risk: regressions appear only on real machines
- Priority: high for screen-recognition work
- Difficulty to test: CI does not mirror the full local desktop environment

---
*Concerns audit: 2026-04-17*
*Update as issues are fixed or new ones discovered*
