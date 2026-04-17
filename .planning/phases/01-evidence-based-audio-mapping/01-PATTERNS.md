# Phase 1: Evidence-Based Audio Mapping - Patterns

**Mapped:** 2026-04-17
**Purpose:** Point execution plans at the closest existing code paths so this phase extends established repo patterns instead of inventing new ones.

## Target-to-Analog Map

| Target File | Closest Existing Analog | Why It Matters |
|-------------|-------------------------|----------------|
| `src/openmy/services/ingest/transcription_enrichment.py` | `apply_transcription_enrichment_to_scenes(...)` in the same file | Existing owner of scene evidence writeback and safest place to derive `audio_ref` |
| `src/openmy/commands/run.py` | existing `run_transcription_enrichment(...)` / `_mark_step(...)` branches | Shows how optional enrichment success and failure are already normalized |
| `app/payloads.py` | `get_date_detail(...)` raw `scenes` return path | Confirms browser payloads can surface new scene fields without a new serializer |
| `src/openmy/commands/show.py` | `freeze_scene_roles(...)` | Demonstrates in-place scene rewrites that preserve non-role fields |
| `tests/unit/test_cli.py` | run-pipeline artifact fixture tests near transcription enrichment coverage | Best pattern for day-dir setup and asserting `scenes.json` after pipeline execution |
| `tests/unit/test_app_server.py` | correction sync and day-detail payload tests | Best pattern for asserting browser-facing JSON behavior |

## Reusable Code Behaviors

### `src/openmy/services/ingest/transcription_enrichment.py`
- Builds `chunk_by_time` from transcription payloads using `time_label`
- Writes derived scene fields directly into raw `scenes.json`
- Uses `safe_write_json(...)` for artifact persistence

### `src/openmy/commands/run.py`
- Separates “new scenes created” and “existing scenes reused” branches
- Treats transcription enrichment as optional and non-blocking
- Re-reads `scenes.json` after post-processing steps

### `app/payloads.py`
- Returns both parsed transcript segments and raw scenes payload
- Adds scene-derived fields onto transcript segments by `time_start`
- Does not reconstruct scenes through a dataclass layer

### `src/openmy/commands/show.py`
- `freeze_scene_roles(...)` mutates only `scene["role"]` and `data["stats"]`
- Leaves unrelated scene keys untouched, which is the expected preservation pattern for `audio_ref`

## Execution Guidance

- Put Phase 1 production logic in `transcription_enrichment.py`, not `segmenter.py`
- Keep run-path changes minimal and explicit in `run.py`
- Prefer regression tests that assert on raw JSON payloads, not only on helper return values
- Use the existing temporary day-dir fixture style from `tests/unit/test_cli.py` and `tests/unit/test_app_server.py`

## Do Not Copy

- Do not copy the original feature doc’s text reverse-matching proposal into any execution task
- Do not add a second mapping cache or standalone lookup file in `data/<date>/`
- Do not make frontend code responsible for deciding which chunk owns a scene

---

*Phase: 01-evidence-based-audio-mapping*
*Pattern map captured: 2026-04-17*
