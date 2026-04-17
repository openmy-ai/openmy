# Phase 1: Evidence-Based Audio Mapping - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds a stable `audio_ref` to scene artifacts by reusing the existing transcription evidence chain. It does not add an audio HTTP endpoint, playback UI, word-selection replay, or any text reverse-matching logic.

</domain>

<decisions>
## Implementation Decisions

### Ownership of audio mapping
- **D-01:** `src/openmy/services/ingest/transcription_enrichment.py` owns scene-to-audio reference derivation because it already writes `transcription_evidence` into `scenes.json`.
- **D-02:** `src/openmy/services/segmentation/segmenter.py` stays a pure time/text splitter and must not gain scene-to-chunk text reverse-matching.

### Scene audio reference contract
- **D-03:** `audio_ref` is derived only from `transcription_evidence`, never from scene text search.
- **D-04:** `audio_ref` stores stable identifiers and offsets only. It must not store `chunk_path` or any absolute audio file path.
- **D-05:** When evidence points to more than one chunk or is otherwise not trustworthy, the scene stays without a playable `audio_ref` instead of guessing.

### Pipeline integration
- **D-06:** The run pipeline must attach `audio_ref` whenever transcription enrichment data is available, not only when a manual align flag is present.
- **D-07:** Historical days without `audio_ref` must remain readable and continue through existing JSON readers without errors.

### Compatibility
- **D-08:** Existing correction flows may rewrite scene text and summaries, but they must not invalidate or silently rewrite a previously derived `audio_ref`.
- **D-09:** Existing scene JSON rewrites, such as role freezing, must preserve unknown fields like `audio_ref`.

### the agent's Discretion
- Exact helper names and function boundaries inside the enrichment pipeline
- Whether `audio_ref` includes auxiliary metadata such as `source` or `segment_ids`, as long as stable identifiers and offsets are present and no file path is stored
- Whether unavailable refs are represented by omission alone or by omission plus a lightweight internal reason field, as long as downstream readers fail safe

</decisions>

<specifics>
## Specific Ideas

- The original feature plan is still useful as product intent, but Phase 1 must only keep the scene-mapping subset and reject its text reverse-matching proposal.
- The accepted architecture is “existing evidence chain first, direct local audio later.”
- The first correctness bar is repeated text, corrected text, and old data without audio refs.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product and scope
- `.planning/PROJECT.md` — locked project boundaries, core value, and out-of-scope items
- `.planning/ROADMAP.md` — Phase 1 goal, requirements, and plan slots
- `docs/plan-audio-playback.md` — original feature intent; use only as product background, not as source of truth for Phase 1 architecture

### Existing mapping path
- `src/openmy/services/ingest/transcription_enrichment.py` — current `transcription_evidence` writeback path and chunk-to-scene linkage
- `src/openmy/commands/run.py` — current pipeline gates that decide when scene enrichment is applied

### Existing readers and regressions
- `app/payloads.py` — date detail payload behavior for returning raw scenes
- `src/openmy/commands/show.py` — scene-freeze rewrite path that must preserve unknown fields
- `tests/unit/test_cli.py` — run-pipeline fixture patterns and artifact assertions
- `tests/unit/test_app_server.py` — local server payload and correction rewrite tests

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apply_transcription_enrichment_to_scenes(...)`: already writes scene-linked evidence into `scenes.json`
- `safe_write_json(...)`: standard safe write path for artifact updates
- `freeze_scene_roles(...)`: rewrites scene roles in place while preserving non-role fields

### Established Patterns
- Day artifacts are stored as plain JSON under `data/<date>/`
- `run.py` uses explicit step markers and “continue main chain on optional enrichment failure”
- Server payloads usually return raw scene dictionaries rather than re-serializing through dataclasses

### Integration Points
- Scene `audio_ref` should be written into `scenes.json` beside `transcription_evidence`
- `run.py` controls whether enrichment is applied during new runs and reused-scene runs
- Tests should cover enrichment helper behavior, pipeline invocation, and browser-facing payload safety

</code_context>

<deferred>
## Deferred Ideas

- Local audio HTTP endpoint with Range support — Phase 2
- Scene-level playback controls — Phase 3
- Explicit correction replay anchors and word-to-segment-to-scene fallback — Phase 4
- Waveform, extra transcoding, and quality-flag replay entry points — out of current milestone scope

</deferred>

---

*Phase: 01-evidence-based-audio-mapping*
*Context gathered: 2026-04-17*
