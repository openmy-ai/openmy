# Requirements: OpenMy Audio Playback

**Defined:** 2026-04-17
**Core Value:** Every playback action must resolve to the correct original audio context, or clearly refuse to guess.

## v1 Requirements

### Evidence Linking

- [ ] **LINK-01**: System can derive each playable scene's source chunk from the existing evidence chain instead of reverse-matching scene text
- [ ] **LINK-02**: Scene audio references store stable source identifiers and offsets without absolute audio file paths
- [ ] **LINK-03**: Days missing usable audio references still load and show playback as unavailable instead of erroring

### Audio Delivery

- [ ] **AUDIO-01**: Browser can fetch a local chunk audio file for a processed day by stable source identifier
- [ ] **AUDIO-02**: Audio responses support HTTP Range so users can seek, resume, and scrub playback
- [ ] **AUDIO-03**: Invalid or stale audio references fail safely instead of playing the wrong source audio

### Scene Playback

- [ ] **SCENE-01**: User can start and pause playback from a scene card when source audio is available
- [ ] **SCENE-02**: User can see which scene is active and control playback position and speed in the existing UI

### Correction Replay

- [ ] **CORR-01**: User text selection in correction flows resolves through an explicit source anchor, not plain browser text alone
- [ ] **CORR-02**: When precise word timing exists, replay starts near that selected word
- [ ] **CORR-03**: When precise word timing does not exist, replay falls back to segment-level and then scene-level playback without silent misalignment

## v2 Requirements

### Replay Depth

- **REPLAY-01**: Historical days can be backfilled to finer-grained replay anchors when source timing data is available
- **REPLAY-02**: Quality-flagged scenes can launch verification playback directly from their warning state

### Media UX

- **MEDIA-01**: Users can see waveform or similar visual seek aids during playback

## Out of Scope

| Feature | Reason |
|---------|--------|
| Waveform precomputation | Not required for first usable playback |
| Extra transcoding pipeline | Existing chunk audio is already sufficient |
| Multiple synchronized players | Unnecessary state complexity for v1 |
| Cloud multi-user media boundaries | Current scope is local-first single-user |
| Hard requirement for universal word timestamps | Existing providers and old data do not guarantee them |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| LINK-01 | Phase 1 | Pending |
| LINK-02 | Phase 1 | Pending |
| LINK-03 | Phase 1 | Pending |
| AUDIO-01 | Phase 2 | Pending |
| AUDIO-02 | Phase 2 | Pending |
| AUDIO-03 | Phase 2 | Pending |
| SCENE-01 | Phase 3 | Pending |
| SCENE-02 | Phase 3 | Pending |
| CORR-01 | Phase 4 | Pending |
| CORR-02 | Phase 4 | Pending |
| CORR-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-17*
*Last updated: 2026-04-17 after initial definition*
