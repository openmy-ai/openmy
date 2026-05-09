# Roadmap: OpenMy Audio Playback

## Overview

This roadmap adds reliable audio replay to OpenMy's existing daily brief and correction experience without changing the core ingestion pipeline. It starts by fixing source mapping correctness, then exposes local audio delivery, then adds scene playback, and finally adds anchored correction replay with safe fallback behavior.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Evidence-Based Audio Mapping** - Replace brittle text matching with stable scene audio references
- [x] **Phase 2: Local Audio Delivery** - Expose chunk audio to the browser with safe seek support
- [x] **Phase 3: Scene Playback UI** - Add scene-level replay controls to the existing day detail interface
- [ ] **Phase 4: Anchored Correction Replay** - Skipped and replaced by Phase 5 subtitle review V1
- [ ] **Phase 5: Subtitle Review V1** - Add selection-first subtitle source review before correction
- [ ] **Phase 6: Smart Audio Player V2** - Silero VAD 精确人声检测 + 波形可视化 + 字幕动画播放器

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
- [x] 01-02: Populate scene audio references from existing evidence during artifact generation
- [x] 01-03: Verify repeated-text, corrected-text, and historical-data regression cases

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
- [x] 02-01: Add local audio endpoint or route resolution for processed chunks
- [x] 02-02: Implement Range handling and reference validation
- [x] 02-03: Verify browser fetch behavior and unavailable-state handling

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
- [x] 03-01: Add shared playback state and single-player control model
- [x] 03-02: Render scene replay controls in the day detail UI
- [x] 03-03: Verify playback behavior on both mapped and unmapped historical days

### Phase 4: Anchored Correction Replay
**Goal**: Skipped. The original anchored replay plan is superseded by Phase 5 subtitle review V1.
**Depends on**: Phase 3
**Requirements**: None
**Success Criteria** (what must be TRUE):
  1. This phase stays skipped
  2. Phase 5 carries the shipped user value
  3. No new implementation starts here
**Plans**: 0 plans

Plans:
- [ ] 04-01: Skipped
- [ ] 04-02: Skipped
- [ ] 04-03: Skipped

### Phase 5: Subtitle Review V1
**Goal**: Users select text first, inspect source subtitles and original audio in a lightweight overlay, and only then choose whether to correct.
**Depends on**: Phase 3
**Requirements**: [SUB-01, SUB-02, SUB-03, SUB-04, SUB-05]
**Success Criteria** (what must be TRUE):
  1. Text selection opens a small action popover instead of opening the correction drawer directly
  2. "查看来源" opens a subtitle review overlay that shows sentence-index navigation and reuses the shared scene audio player
  3. "纠错" still opens the existing correction drawer, and missing anchors fail safely without guessing
**Plans**: 3 plans

Plans:
- [x] 05-01: Add Phase 5 planning artifacts and selection-first interaction flow
- [x] 05-02: Build subtitle review overlay with sentence-index pseudo timeline and shared playback reuse
- [x] 05-03: Verify subtitle review, correction handoff, and safe fallback behavior

### Phase 6: Smart Audio Player V2
**Goal**: 用 Silero VAD 替换 ffmpeg silenceremove 实现精确人声检测，将 VAD 时间戳写入转写数据，前端新增波形可视化和字幕流动动画播放器，整合"显示原文"与"播放原声"为统一交互。
**Depends on**: Phase 5
**Requirements**: [SAP-01, SAP-02, SAP-03, SAP-04, SAP-05, SAP-06, SAP-07]
**Success Criteria** (what must be TRUE):
  1. Pipeline 用 Silero VAD 检测人声段并写入 transcript.transcription.json 的 speech_segments 字段
  2. chunk 的 duration_seconds 是真实值（非 0.0），speech_segments 有精确的 start/end 秒数
  3. 前端播放器显示音频波形，用户可拖动波形导航
  4. 播放时文字像字幕一样流动（当前段高亮 + 自动卷动 + 过渡动画）
  5. "显示原文"按钮改为"显示原文和播放原声"，展开后是字幕式原文 + 整段播放控件
  6. 选中文字 → 查看来源 → 播放能定位到对应语音段附近
  7. 老数据（无 speech_segments）降级到当前行为，不报错
**Plans**: 5 plans

Plans:
- [ ] 06-01: Backend — Silero VAD 集成到音频 pipeline，替换 ffmpeg silenceremove
- [ ] 06-02: Backend — 转写数据格式升级，写入 speech_segments 和真实 duration
- [ ] 06-03: Frontend — 波形可视化组件（Web Audio API）
- [ ] 06-04: Frontend — 字幕流动动画播放器（替换 subtitle-overlay 伪时间轴）
- [ ] 06-05: 全链路验证 — 新 pipeline 处理 → 前端播放 → 老数据降级

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 (skipped) → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Evidence-Based Audio Mapping | 3/3 | Completed | 2026-04-17 |
| 2. Local Audio Delivery | 3/3 | Completed | 2026-04-18 |
| 3. Scene Playback UI | 3/3 | Completed | 2026-04-18 |
| 4. Anchored Correction Replay | 0/3 | Skipped | 2026-04-18 |
| 5. Subtitle Review V1 | 3/3 | Review pending | 2026-04-18 |
| 6. Smart Audio Player V2 | 0/5 | Planning | — |eview pending | 2026-04-18 |
