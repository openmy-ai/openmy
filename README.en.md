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

### 🎯 Hybrid Layered Role Attribution

You talk to many people each day, but keyword matching alone isn't accurate enough, and manually tagging every recording is too tedious. DayTape uses a **hybrid layered approach** — different strategies at different stages. What can be determined by rules gets determined by rules. What can be inherited from context gets inherited. When the evidence is insufficient, it honestly marks "uncertain" instead of guessing.

**Design Philosophy:**
- 🚫 No mandatory role declaration per recording (too heavy, won't last a week)
- 🚫 No forced classification of ambiguous segments (pollutes long-term archives)
- ✅ "Uncertain" is allowed (not a bug — it's how a long-term system stays trustworthy)
- ✅ Rules first, AI models last (if rules can handle it, don't call a model)

**Two-stage classification:**
- **Coarse** (Phase 1): AI / Merchant / Pet / Self / Interpersonal / Uncertain
- **Fine** (after collecting confirmed samples): Partner / Family / Friends

> "Discussing ChatGPT with your wife" won't be misclassified as "talking to AI" — because declarations and context inheritance take priority over keywords.

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

### 🖥️ Screenpipe Screen-Context Augmentation (Optional)

Voice is the main signal; screen activity is corroborating evidence. DayTape integrates with [Screenpipe](https://github.com/mediar-ai/screenpipe) to enrich your audio timeline with screen context.

**Core design: Don't copy Screenpipe's data — borrow its understanding.**

- DayTape queries Screenpipe's HTTP API by time window, never depends on its database schema
- Only stores summarized screen sessions and frame_id references; screenshots are lazy-loaded on demand
- Raw OCR text is never mixed into the voice transcript, preventing screen text from polluting structured extraction

**Three fusion modes:**

| Mode | What it does | Example |
|------|-------------|---------|
| **hints** (default) | Boosts role attribution confidence | WeChat window → "interpersonal" ↑; Cursor window → "AI" ↑ |
| **augment** | Feeds screen summaries into extraction prompts | "Was viewing Taobao refund page" added to event context |
| **full** | Attaches frame references to scenes | Click in Web UI to view the actual screenshot from that moment |

**Time alignment (3-stage):**

```
1. Coarse: Estimate global offset delta0 from recording start time
2. Refine: Keyword overlap scan within ±30min to find best offset delta
3. Merge: Query Screenpipe for [scene.start+delta-20s, scene.end+delta+20s]
```

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

## Role Attribution: The Layered Resolution Chain

| Priority | Layer | What it does | Example |
|----------|-------|-------------|---------|
| 1 | **Explicit Declaration** | Speaker uses a direct address | "Hey babe" / "Hi Gemini" |
| 2 | **Strong Inheritance** | High-confidence role carries forward | Confirmed talking to partner → weak keywords can't override |
| 3 | **Rule Match** | Keyword-based coarse classification | 3+ AI terms → AI; "refund/invoice" → Merchant |
| 4 | **Weak Inheritance** | Medium-confidence role carries forward | Previous segment was merchant → next one defaults to merchant |
| 5 | **Mark Uncertain** | Insufficient evidence → don't force a guess | Below threshold → uncertain |

Each scene block outputs:

```
role:         Role category (6 coarse types)
addressed_to: Specific entity (Partner / AI Assistant / Pet name)
confidence:   Confidence score (0-1)
evidence:     Resolution reasoning
```

### Why not other approaches?

| Approach | Why not use it alone |
|----------|---------------------|
| Pure keyword matching | Only 45-70% accuracy for interpersonal subtypes |
| Manual declaration per recording | Too much friction, won't last a week |
| Pure LLM classification | Slow, expensive, rules handle most cases |
| No "uncertain" allowed | Forced guessing → polluted long-term archives |

**DayTape's choice:** Hybrid — rules handle the obvious cases, inheritance handles continuity, models only process truly ambiguous interpersonal segments, and "uncertain" is always an acceptable answer.

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
