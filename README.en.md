<p align="center">
  <h1 align="center">🎙️ DayTape</h1>
  <p align="center"><strong>Turn your day into a searchable, structured log</strong></p>
  <p align="center">Record → AI Transcribe → Clean → Role Attribution → Distill → Browse</p>
</p>

<p align="center">
  <a href="README.md">中文</a> •
  <a href="README.en.md">English</a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="#license">License</a>
</p>

---

## What is DayTape?

You talk to a lot of people every day — your partner, AI assistants, merchants, or just yourself while planning ahead.

**DayTape turns a full day of audio recordings into a structured, browsable timeline.**

It's not just speech-to-text. DayTape automatically figures out *who you're talking to*, extracts key events and to-dos, and distills each conversation into a one-line summary. Open your browser, and you can review your entire day like flipping through a journal.

## Features

### 🎯 Smart Role Attribution
Automatically detects who you're talking to in each segment. Uses a three-layer resolution chain — explicit declarations, keyword rules, and contextual inheritance — for accuracy far beyond naive keyword matching.

### 🧹 10-Step Deep Cleaning
Raw transcriptions are noisy: filler words, AI boilerplate responses, background music lyrics, verbal tics. DayTape's cleaning pipeline handles each of these while protecting role-signal words from being accidentally removed.

### 💭 Distilled Summaries
Each conversation segment is distilled into a single sentence, so you know what was discussed without reading the full transcript.

### 📊 Three View Modes
- **Distilled Timeline**: A Notion-style vertical timeline — see your whole day at a glance
- **Data Table**: Structured data for each segment, sortable and filterable
- **Visualizations**: Role distribution pie chart, time-of-day bar chart

### 🏷️ Structured Extraction
Automatically extracts events, decisions, to-dos, and insights from conversations, tagged by project.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/sefuzhou770801-hub/daily-context.git
cd daily-context

# Install
pip install -e .

# Start the web UI (includes sample data)
python app/server.py
```

Open `http://localhost:8420` in your browser.

## Architecture

```
src/daytape/
├── domain/          # Data models (Scene, FactBundle, ArtifactBundle)
├── services/
│   ├── cleaning/    # 10-step cleaning pipeline
│   ├── segmentation/# Time-based scene segmentation
│   ├── roles/       # 3-layer role attribution engine
│   ├── extraction/  # Structured information extraction
│   └── distillation/# AI-powered summary distillation
├── adapters/
│   └── transcription/# Transcription engine adapters (Gemini CLI)
└── resources/       # Vocabulary, correction dictionaries
```

### Data Flow

```
Audio File
  ↓
Audio Preprocessing (normalize, chunk)
  ↓
AI Transcription (Gemini Flash)
  ↓
10-Step Cleaning (denoise, dedupe, protect signal words)
  ↓
Scene Segmentation (split by time gaps)
  ↓
Role Attribution (declaration → keywords → inheritance)
  ↓
Distilled Summaries + Structured Extraction
  ↓
Web Timeline Browser
```

## Role Attribution: The Three-Layer Chain

| Priority | Layer | Example |
|----------|-------|---------|
| 1 | Explicit Declaration | "Hey babe" / "Hi Gemini" |
| 2 | Context Inheritance | Confirmed talking to partner → weak keywords can't override |
| 3 | Keyword Rules | 3+ AI-related terms needed to classify as "talking to AI" |

## Roadmap

- [x] Speech-to-text + cleaning pipeline
- [x] Role attribution engine
- [x] Distilled summaries
- [x] Web timeline browser
- [x] Python package architecture (v0.1)
- [ ] `config.yaml` externalized configuration
- [ ] Multi-engine transcription (OpenAI / Whisper / Doubao)
- [ ] Screenpipe screen-context augmentation
- [ ] Conversational queries ("What did I discuss with my partner today?")
- [ ] Mobile recording upload (iOS Shortcuts)
- [ ] Obsidian / Notion export

## Tech Stack

- **Backend**: Python 3.10+
- **Transcription**: Gemini 2.5 Flash
- **Frontend**: Vanilla HTML + CSS + JavaScript
- **Data Format**: JSON (scenes, metadata) + Markdown (transcripts)
- **Packaging**: Hatch / pip

## License

This project is licensed under [AGPL-3.0](LICENSE).

**In plain terms:**
- ✅ Free to use, study, and modify
- ✅ Free to share with others
- 🔒 If you build a product or service based on this, you must open-source it too
- 💼 Need a commercial closed-source license? Contact the author

---

<p align="center">
  <sub>Built with 🎙️ by <a href="https://github.com/sefuzhou770801-hub">Joseph Zhou</a></sub>
</p>
