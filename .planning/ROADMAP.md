# Roadmap: OpenMy Audio Playback

## Overview

This roadmap adds reliable audio replay to OpenMy's existing daily brief and correction experience without changing the core ingestion pipeline. It starts by fixing source mapping correctness, then exposes local audio delivery, then adds scene playback, and finally adds anchored correction replay with safe fallback behavior.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Evidence-Based Audio Mapping** - Replace brittle text matching with stable scene audio references
- [ ] **Phase 2: Local Audio Delivery** - Expose chunk audio to the browser with safe seek support
- [ ] **Phase 3: Scene Playback UI** - Add scene-level replay controls to the existing day detail interface
- [ ] **Phase 4: Anchored Correction Replay** - Add accurate correction-time replay with word-to-segment-to-scene fallback

## Phase Details

### Phase 1: Evidence-Based Audio Mapping
**Goal**: Every playable scene resolves to the correct source chunk through the existing evidence chain, without duplicating absolute audio paths.
**Depends on**: Nothing (first phase)
**Requirements**: [LINK-01, LINK-02, LINK-03]
**Success Criteria** (what must be TRUE):
  1. Scenes resolve source audio from evidence records even when transcript text repeats or is later corrected
  2. Scene data stores stable identifiers and offsets instead of absolute audio file paths
  3. Historical days without usable audio references still render normally and show playback as unavailable
**Plans**: 3 plans

Plans:
- [x] 01-01: Define and serialize the scene audio reference contract
- [ ] 01-02: Populate scene audio references from existing evidence during artifact generation
- [ ] 01-03: Verify repeated-text, corrected-text, and historical-data regression cases

### Phase 2: Local Audio Delivery
**Goal**: The browser can request local chunk audio safely and seek within it using HTTP Range.
**Depends on**: Phase 1
**Requirements**: [AUDIO-01, AUDIO-02, AUDIO-03]
**Success Criteria** (what must be TRUE):
  1. A playable scene can request the correct chunk audio by stable identifier for a processed day
  2. Browser playback can seek and resume without downloading the whole file first
  3. Bad or stale references fail safely instead of returning the wrong audio
**Plans**: 3 plans

Plans:
- [ ] 02-01: Add local audio endpoint or route resolution for processed chunks
- [ ] 02-02: Implement Range handling and reference validation
- [ ] 02-03: Verify browser fetch behavior and unavailable-state handling

### Phase 3: Scene Playback UI
**Goal**: Users can replay source audio directly from scene cards in the existing local web interface.
**Depends on**: Phase 2
**Requirements**: [SCENE-01, SCENE-02]
**Success Criteria** (what must be TRUE):
  1. Playable scenes show replay controls and unavailable scenes show a safe disabled state
  2. Users can start, pause, seek, and change playback speed from the existing page
  3. The interface clearly shows which scene is currently active in the single-player flow
**Plans**: 3 plans

Plans:
- [ ] 03-01: Add shared playback state and single-player control model
- [ ] 03-02: Render scene replay controls in the day detail UI
- [ ] 03-03: Verify playback behavior on both mapped and unmapped historical days

### Phase 4: Anchored Correction Replay
**Goal**: Correction-time replay stays accurate even when word-level timing coverage is incomplete.
**Depends on**: Phase 3
**Requirements**: [CORR-01, CORR-02, CORR-03]
**Success Criteria** (what must be TRUE):
  1. Correction interactions resolve replay through explicit source anchors, not plain selected text
  2. When word timing exists, replay starts near the selected word
  3. When word timing does not exist, replay falls back to segment-level and then scene-level audio without silent misalignment
**Plans**: 3 plans

Plans:
- [ ] 04-01: Add explicit replay anchors to transcript and correction rendering
- [ ] 04-02: Implement resolver logic for word-to-segment-to-scene fallback
- [ ] 04-03: Verify correction replay on mixed datasets with and without word timing

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Evidence-Based Audio Mapping | 1/3 | In Progress|  |
| 2. Local Audio Delivery | 0/3 | Not started | - |
| 3. Scene Playback UI | 0/3 | Not started | - |
| 4. Anchored Correction Replay | 0/3 | Not started | - |
