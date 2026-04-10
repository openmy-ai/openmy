<div align="center">

<img src="docs/images/openmy-banner.png" alt="OpenMy Banner" width="800" />

<br />

### 🎙️ One Audio File → A Full Day of Structured Context

**OpenMy** is an open-source personal context engine.  
Record your day, and it auto-transcribes, cleans, splits scenes, identifies who you're talking to, distills summaries, and generates a daily briefing.  
Give your AI Agent real memory about *you*.

<br />

[![GitHub release](https://img.shields.io/github/v/release/openmy-ai/openmy?style=flat-square&color=blue)](https://github.com/openmy-ai/openmy/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-167%20passed-brightgreen?style=flat-square)]()

[Quick Start](#-quick-start) · [Features](#-features) · [Workbench](#-workbench) · [中文](README.md)

</div>

---

## ⚡ Quick Start

```bash
git clone https://github.com/openmy-ai/openmy.git && cd openmy
python3 -m venv .venv && source .venv/bin/activate
pip install .
echo "GEMINI_API_KEY=your-key" > .env
openmy quick-start path/to/your-audio.wav
```

Five steps. Your browser opens `http://127.0.0.1:8420` with your first daily briefing.

<details>
<summary>🤔 Missing FFmpeg? Wrong Python version? <b>The CLI tells you in plain language.</b></summary>

```
❌ Missing ffmpeg, ffprobe. On macOS: `brew install ffmpeg`.
❌ Requires Python 3.10+. Try `brew install python@3.11`.
❌ No .env found and no GEMINI_API_KEY detected. Run `cp .env.example .env` and fill in your key.
```

No cryptic tracebacks. One line, one fix.

</details>

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🧠 Beyond Transcription

Most tools stop at text. OpenMy keeps going—

- **Scene Splitting**: Breaks a full day into distinct conversation segments
- **Role Resolution**: Detects *who* you're talking to — AI, friends, merchants, yourself
- **Distilled Summaries**: One to two sentences per scene
- **Structured Extraction**: Events, facts, and insights in separate buckets

</td>
<td width="50%" valign="top">

### 📋 Daily Briefing + Active Context

No more manual journaling or Notion templates—

- **Daily Briefing**: Auto-generated with summary, stats, and timeline
- **Active Context**: Cross-day accumulation of projects, todos, and relationships
- **Auto-Dedup**: Different names for the same project? Merged automatically
- **Staleness Detection**: Untouched items flagged after 7 days

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🔧 CLI = Agent Interface

OpenMy's CLI isn't for humans — it's for AI agents.

```bash
openmy context --compact    # inject into prompt
openmy correct merge-project "AI Thinking" "OpenMy"
openmy agent --recent       # auto-read on agent boot
```

Your AI agent knows who you are, what you're working on, and what's still pending — before it says a word.

</td>
<td width="50%" valign="top">

### 🖥️ Local-First, Your Data Stays

- All data in a local `data/` directory
- Server defaults to `127.0.0.1`, no public access
- No SaaS, no accounts, no uploads
- API key calls Gemini from your machine only

**Your day, your rules.**

</td>
</tr>
</table>

---

## 🖼️ Workbench

<div align="center">

<img src="docs/images/openmy-quick-start.png" alt="OpenMy Workbench" width="700" />

</div>

Open `http://127.0.0.1:8420` to access your local workbench:

| View | Description |
|------|-------------|
| 📊 **Overview** | Today's stats: scenes, word count, duration, role distribution |
| 📰 **Briefing** | AI-generated structured daily briefing |
| 🕐 **Timeline** | Chronological distilled summaries per scene |
| 📋 **Table** | Full scene list with expandable transcripts |
| 📈 **Charts** | Role distribution and scene duration visualizations |
| ✏️ **Corrections** | Typo dictionary + global search & replace |
| ⚙️ **Pipeline** | Re-run any pipeline stage with one click |

---

## 🔬 How It Works

```mermaid
graph LR
    A[🎙️ Audio] --> B[Transcribe]
    B --> C[Clean Text]
    C --> D[Scene Split]
    D --> E[Role Resolve]
    E --> F[Distill]
    F --> G[Extract]
    G --> H[Briefing]
    H --> I[Active Context]
    I --> J[🖥️ Workbench]

    style A fill:#6366f1,stroke:#4f46e5,color:#fff
    style J fill:#06b6d4,stroke:#0891b2,color:#fff
```

| Stage | What | How |
|-------|------|-----|
| **Transcribe** | Audio → timestamped text | Gemini API |
| **Clean** | Remove noise, fix punctuation, apply corrections | Rule engine, no API calls |
| **Scene Split** | Group by time and topic | Rules + semantic cues |
| **Role Resolve** | Determine who you're talking to | Gemini + Screenpipe hints |
| **Distill** | One-line summary per scene | Gemini (role-aware) |
| **Extract** | Output events / facts / insights | Gemini (JSON schema constrained) |
| **Briefing** | Generate readable daily report | Gemini |
| **Active Context** | Cross-day accumulation of projects, people, todos | Local aggregation + dedup |

---

## 🔌 Optional: Screenpipe Screen Context

OpenMy can integrate with [Screenpipe](https://github.com/mediar-ai/screenpipe) for extra role-resolution signals:

```
"You were talking to an AI at 09:30" ← not just content analysis, also because Cursor was on screen
```

- **Works fine without it** — all features are unaffected
- Better role accuracy when installed
- Reads via local HTTP (`localhost:3030`), no code changes required

---

## 🤖 For Agent Developers

OpenMy's core mission: **give AI agents persistent memory about *you*.**

```python
# On your agent's startup:
import subprocess

# 1. Get the user's active context
result = subprocess.run(
    ["openmy", "context", "--compact"],
    capture_output=True, text=True
)
user_context = result.stdout

# 2. Inject into system prompt
system_prompt = f"""You are the user's assistant. Here is their recent context:
{user_context}
"""
```

One command. Your agent knows what the user has been working on, who they've been talking to, and what's still pending.

---

## ⚙️ Configuration

All settings live in [`src/openmy/config.py`](src/openmy/config.py). Most users don't need to touch this on first run.

<details>
<summary>Available parameters</summary>

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` | Global model |
| `TRANSCRIBE_TIMEOUT` | 900s | Transcription timeout |
| `EXTRACT_TEMPERATURE` | 0.2 | Extraction temperature |
| `DISTILL_TEMPERATURE` | 0.2 | Distillation temperature |
| `SCREEN_RECOGNITION_ENABLED` | `True` | Screenpipe toggle |
| `SCREEN_RECOGNITION_API` | `localhost:3030` | Screenpipe address |

</details>

---

## 🧪 Development & Testing

```bash
git clone https://github.com/openmy-ai/openmy.git && cd openmy
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 -m pytest tests/ -v   # 167 tests, 0 API key needed
```

The test suite runs without a real API key.

---

## 📍 Roadmap

| Phase | Status | What |
|-------|--------|------|
| ~~v0.1 Alpha~~ | ✅ | Core pipeline: transcribe → clean → scenes → roles → distill → briefing |
| **v0.2 Beta** | 🟢 **Current** | quick-start, web workbench, correction dictionary, structured extraction, active context |
| v0.3 | 🔜 | Multi-language support, smarter cross-day context, Obsidian plugin |
| v1.0 | 📋 | Stable API, plugin system, multi-LLM backend |

> Want to help? See [CONTRIBUTING.md](CONTRIBUTING.md) or open an Issue.

---

## 🆚 What OpenMy Is Not

| | OpenMy | Pure Transcription | Journaling Apps |
|---|---|---|---|
| Transcription | ✅ | ✅ | ❌ |
| Scene splitting & role resolution | ✅ | ❌ | ❌ |
| Structured extraction (events/facts/insights) | ✅ | ❌ | ❌ |
| Active context (for AI agents) | ✅ | ❌ | ❌ |
| 100% local data | ✅ | Depends | Depends |
| Open source | ✅ | Few | Few |

**OpenMy isn't a better transcription tool. It's what happens *after* transcription.**

---

## 📂 Repository Structure

```
src/openmy/          Core Python package (CLI + 9 service modules)
├── services/
│   ├── ingest/          Audio import & preprocessing
│   ├── cleaning/        Text cleaning (rule engine)
│   ├── segmentation/    Scene splitting
│   ├── roles/           Role resolution
│   ├── distillation/    Summary distillation
│   ├── extraction/      Structured extraction
│   ├── briefing/        Daily briefing generation
│   ├── context/         Active context management
│   └── screen_recognition/  Screenpipe integration
app/                 Local web workbench
tests/               167 automated tests
docs/                Design docs & screenshots
```

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

TL;DR: Fork → branch → code + tests → `pytest` passes → open PR.

---

## 📄 License

[MIT](LICENSE) · by [Joseph Zhou (周瑟夫)](https://github.com/openmy-ai)

---

<div align="center">

**If this is useful, a ⭐ means the world.**

</div>
