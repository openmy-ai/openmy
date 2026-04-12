<div align="center">

<img src="docs/images/openmy-banner.png" alt="OpenMy" width="800" />

# Turn audio and screen activity into context your agent can keep

OpenMy turns saved audio, screen context, and daily progress into **queryable, correctable, cross-day memory**. You can read the daily report yourself or plug the same state into your own agent.

[![Release](https://img.shields.io/github/v/release/openmy-ai/openmy?style=flat-square&color=blue)](https://github.com/openmy-ai/openmy/releases)
[![MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-328%20passed-brightgreen?style=flat-square)]()

[中文](README.md)

</div>

---

## What you get first

- **A daily briefing** with summaries, timeline, tables, and charts
- **Active context** that keeps projects, people, todos, and facts across days
- **A correction loop** so names, roles, and decisions get better over time
- **Stable entrypoints** for both humans and agents

---

## Why this is not just another transcription tool

OpenMy does more than convert audio into text.

It keeps going:

1. Split a day into scenes
2. Resolve who you were talking to and what was happening
3. Generate a daily briefing plus structured output
4. Accumulate ongoing projects, people, and open loops into long-term context

That makes OpenMy a **personal context engine**, not a one-off transcript utility.

> OpenMy is not a live recording app. It processes recordings you already saved, plus optional screen context from the same day.

---

## ⚡ Get it running in one minute

```bash
git clone https://github.com/openmy-ai/openmy.git && cd openmy
python3 -m venv .venv && source .venv/bin/activate
pip install .
openmy quick-start --demo
```

> You only need Python 3.10+ and FFmpeg.
> `--demo` runs the bundled sample first so you can verify the full flow before switching to your own audio.

### After the demo works

```bash
openmy skill health.check --json
openmy quick-start path/to/your-audio.wav
```

- `health.check` gives you a recommended route first, so you do not have to guess between six engines
- `quick-start` now pauses and guides you if first-run setup is still incomplete

### How should you choose a speech-to-text engine?

Do not start by comparing every engine yourself. Use this order:

1. Run `health.check` and follow the recommended route
2. If your recordings are mostly Chinese and you want local-first, start with `funasr`
3. If you want the safest local path first, use `faster-whisper`
4. Only look at cloud options after that, or when local setup is not the right fit

Cloud options (`gemini`, `groq`, `dashscope`, `deepgram`) are there when you want them, but they are not the first thing you need to think about.

- `GEMINI_API_KEY` is **not** required for audio processing; it only affects later LLM-backed cleanup steps

---

## Who this is for

### 1. People who want a daily report from voice notes, meetings, and ideas
OpenMy helps turn raw recordings into a readable day summary instead of leaving you with a pile of files.

### 2. People already using agents heavily
OpenMy can act as a long-term context layer so your agent reads what happened instead of asking you to restate everything.

### 3. Developers building personal-context workflows
You can plug the stable actions into your own CLI, desktop tool, or automation flow.

---

## What the output looks like

<div align="center">
<img src="docs/images/openmy-quick-start.png" alt="OpenMy report" width="700" />
</div>

The generated report includes:

- **Overview** — scenes, word count, speaking time, role distribution
- **Daily briefing** — what happened and what still matters
- **Summary timeline** — condensed scene-by-scene timeline
- **Scene table** — full list of scenes with expandable detail
- **Charts** — visual breakdown by role and duration
- **Corrections** — fix names, roles, and decisions
- **Flow controls** — re-run specific stages when needed

---

## How it works

```mermaid
graph TD
    A["🎙️ Audio / Screen"] --> B["Transcribe + Clean"]
    B --> C["Scene Split + Role Resolve"]
    C --> D["Distill + Extract"]
    D --> E["Briefing"]
    E --> F["Active Context"]
    F --> G["Agent / You"]
```

If you want the deeper system view, read [docs/architecture.md](docs/architecture.md).

---

## 🤖 Connect OpenMy to your agent

The core asset is not a single CLI shell. It is **durable context state plus a stable action contract**.

Current stable JSON entrypoints:

```bash
openmy skill status.get --json
openmy skill day.get --date 2026-04-08 --json
openmy skill context.get --json
openmy skill day.run --date 2026-04-08 --audio path/to/audio.wav --json
```

- `status.get` — inspect readiness and data presence
- `day.get` — read one processed day
- `context.get` — read cross-day active context
- `day.run` — process one day and persist artifacts

The old `openmy agent` entrypoint still exists as a compatibility alias.

### Install the skill bundle

#### One-shot install

```bash
bash scripts/install-skills.sh
```

The script detects common agent tools and links the OpenMy skill bundle for you.

#### Key directories if you want to wire it up manually

- `skills/openmy/`
- `skills/openmy-startup-context/`
- `skills/openmy-context-read/`
- `skills/openmy-context-query/`
- `skills/openmy-day-run/`
- `skills/openmy-day-view/`
- `skills/openmy-correction-apply/`
- `skills/openmy-status-review/`
- `skills/openmy-vocab-init/`
- `skills/openmy-profile-init/`

---

## Optional capabilities

### Screen recognition

OpenMy can enrich a day with screen context so the system knows what was on-screen while you were speaking.

This feature is optional. It now uses OpenMy's built-in capture loop, so there is no separate local service to install. If you leave it off, OpenMy falls back to voice-only mode and the main flow still works.

### Export

Daily briefings can be exported to:

- `Obsidian` — write Markdown directly into your vault
- `Notion` — create pages through the API

Export is optional. If it is not configured, the main pipeline still completes normally.

### Folder watcher mode

If you prefer dropping recordings into a folder and letting OpenMy process them automatically, run the watcher:

```bash
python3 -m openmy.services.watcher ~/Recordings/OpenMy
```

This works well when:
- your phone syncs recordings onto the computer
- a recorder or wireless mic writes into a fixed folder
- you want capture and processing to stay separate

The watcher waits for files to settle, then starts processing automatically. You can still ignore watcher mode and run `quick-start` or `day.run` manually.

### Recommended workflow

Record first, sync into a stable folder, run `openmy quick-start`, then enable watcher mode only after the manual path feels right.

---

## Roadmap

- ~~v0.1~~ ✅ Core pipeline working
- **v0.2 now** — quick-start, report workspace, correction dictionary, structured extraction, active context
- **v0.3** — multilingual support, stronger cross-day context, Obsidian plugin
- **v1.0** — stable API, plugin system, multiple model backends

---

## Development

```bash
pip install -e .
uvx ruff check .
python3 -m pytest tests/ -v
```

---

## Repository shape

```text
src/openmy/                core source
app/                       report UI
skills/                    agent skill bundle
docs/                      architecture and extra docs
tests/                     automated tests
```

For the deeper module layout, see [docs/architecture.md](docs/architecture.md).

---

[CONTRIBUTING](CONTRIBUTING.md) · [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md) · [SECURITY](SECURITY.md) · [MIT License](LICENSE)

If this is useful, a ⭐ helps a lot.
