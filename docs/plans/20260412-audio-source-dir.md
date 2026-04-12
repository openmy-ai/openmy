# Audio Source Directory Configuration

## Problem

On first setup, the agent scans the entire disk for audio files. This is:
- Slow and wasteful
- Confusing for the user ("why is it scanning my entire machine?")
- Not how real users work — they have a fixed folder where their recorder saves files

## Solution

Let the user configure a persistent "audio source directory" during onboarding.

---

## Task 1: Add OPENMY_AUDIO_SOURCE_DIR to .env

#### [MODIFY] `.env.example`

Add:
```
# Where your recorder saves audio files (e.g., ~/Documents/DJI-Mic/)
OPENMY_AUDIO_SOURCE_DIR=
```

#### [MODIFY] `src/openmy/config.py`

Add:
```python
def get_audio_source_dir() -> str:
    return _read_env("OPENMY_AUDIO_SOURCE_DIR")
```

---

## Task 2: profile.set supports --audio-source

#### [MODIFY] `src/openmy/skill_dispatch.py`

In `handle_profile_set`, accept `--audio-source` as an optional parameter.
Store it in `profile.json` as `audio_source_dir`.

---

## Task 3: Update health.check onboarding flow

#### [MODIFY] `skills/openmy-health-check/SKILL.md`

After the user selects an STT engine, add one more step:

```
你的录音通常存在哪个文件夹？
比如：~/Documents/DJI-Mic/

告诉我路径，以后自动从那里找录音。不知道的话可以跳过。
```

When the user provides the path:
1. Validate it exists
2. Write `OPENMY_AUDIO_SOURCE_DIR=<path>` to `.env`
3. Confirm: "配好了。以后直接说'处理今天的录音'就行。"

---

## Task 4: day.run auto-discover from source dir

#### [MODIFY] `src/openmy/services/ingest/audio_pipeline.py` (or related)

When `day.run` is called WITHOUT `--audio`:
1. Check `OPENMY_AUDIO_SOURCE_DIR`
2. If set, scan that directory for today's audio files (by file modification date)
3. If files found, use them automatically
4. If not set, ask the user

Do NOT scan the entire disk. Only scan the configured source directory.

---

## Task 5: Watcher integration

The existing `watcher.py` should also watch `OPENMY_AUDIO_SOURCE_DIR` instead of
requiring the user to specify a path every time.

---

## Priority

1. Task 1 (config) — foundation
2. Task 3 (onboarding) — user-facing
3. Task 4 (auto-discover) — the actual feature
4. Task 2 (profile.set) — convenience
5. Task 5 (watcher) — nice to have

## Git Conventions

- Commit messages in English, Conventional Commits format
- Run `ruff check .` before each commit
