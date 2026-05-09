# OpenMy Audio Playback

## What This Is

This is a brownfield feature project for OpenMy's existing local web UI. It adds reliable audio playback to scene review and transcript correction so a user can hear the original recording that produced a scene or selected text. The focus is playback correctness inside the current local-first product, not a new transcription stack or media platform.

## Core Value

Every playback action must resolve to the correct original audio context, or clearly refuse to guess.

## Requirements

### Validated

- ✓ Daily brief detail view already renders scenes, transcript content, and task status — existing
- ✓ Scene evidence is already written back from transcription enrichment into downstream artifacts — existing
- ✓ Transcript correction flow already exists in the local web experience — existing
- ✓ Localhost web endpoints already expose day detail and job status for browser clients — existing

### Active

- [ ] Scene audio references are derived from the existing evidence chain instead of reverse-matching scene text
- [ ] Scene audio references store stable source identifiers and offsets without absolute audio file paths
- [ ] Local chunk audio is fetchable in the browser with Range support
- [ ] Scene cards can play and pause source audio when a valid reference exists
- [ ] Correction replay uses explicit source anchors and falls back from word to segment to scene
- [ ] Historical days without usable audio references stay readable and fail safely

### Out of Scope

- Waveform precomputation — not required for first usable playback
- Extra transcoding pipeline — local chunk audio already exists
- Multiple synchronized players — single-player control keeps state and QA simpler
- Cloud multi-user media boundaries — current product is local-first and single-user
- Universal word-timestamp backfill — current providers and historical data do not guarantee it

## Context

OpenMy is a local-first Python monolith with a localhost web UI over file-based daily artifacts. Processed days already contain chunked audio files and transcript segment data, but word-level timestamps are inconsistent across providers and old data. The engineering review for this feature rejected four brittle assumptions: text reverse-matching for scene-to-audio mapping, hard dependency on word timestamps, DOM-only text selection without explicit anchors, and storing absolute audio paths in scene data. The accepted direction is to reuse the existing evidence chain, serve local static audio with Range support, and build replay around a word-to-segment-to-scene fallback model.

## Constraints

- **Tech stack**: Reuse the current Python server and existing browser UI — avoid new frameworks or a separate media service
- **Data model**: Store stable chunk identifiers and offsets, not absolute audio paths — paths are redundant and fragile
- **Compatibility**: Old processed days must render without errors when audio references are missing — historical data cannot be assumed complete
- **Accuracy**: Reverse text lookup is not an acceptable source-of-truth mapping strategy — repeated or corrected text can silently misalign audio
- **Performance**: Serve existing local chunk files with HTTP Range — avoid lookup layers, duplicate copies, and extra transcoding
- **Scope**: First milestone excludes waveform previews, extra codecs, multi-player coordination, and cloud-user concerns — keep the first usable version narrow

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Reuse the existing evidence chain for scene audio references | Reverse-matching scene text is brittle with repeated phrases, summarization drift, and later corrections | — Pending |
| Serve local chunk audio directly with HTTP Range | The chunk files already exist on disk and browser playback needs seek support | — Pending |
| Require explicit replay anchors for correction interactions | Plain text selection in the browser does not identify a trustworthy source segment | — Pending |
| Degrade replay from word to segment to scene | Word-level timestamps are not guaranteed across providers or historical data | — Pending |
| Store only stable source identifiers in scene data | Absolute audio paths duplicate state and break easily when storage layout changes | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone**:
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-17 after initialization*
