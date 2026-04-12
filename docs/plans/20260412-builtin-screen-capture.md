# Built-in Screen Capture — Replace External Screenpipe Dependency

## Problem

OpenMy has 4000+ lines of screen context processing code (align, sessionize, privacy, hints, summary, enrich) but **zero lines of actual screen capture**. It depends on an external Screenpipe service at `localhost:3030` that users must install separately. This is unacceptable.

## Goal

Port Screenpipe's screen capture and OCR logic from Rust to Python, making it a built-in OpenMy module. No external service. No separate install.

## IMPORTANT: Read Screenpipe Source First

**Before writing any code**, read the Screenpipe source from GitHub:
- Repo: https://github.com/mediar-ai/screenpipe
- Key files to study:
  - `screenpipe-vision/src/capture.rs` — screenshot capture logic
  - `screenpipe-vision/src/ocr.rs` or `text.rs` — OCR / text extraction
  - `screenpipe-vision/src/core.rs` — main loop and event format
  - `screenpipe-core/` — data models and storage

**Port the core logic to Python.** Do NOT reinvent from scratch. Translate what Screenpipe actually does — their capture strategy, OCR pipeline, event format, and deduplication logic. Adapt for Python (use subprocess for screencapture, PyObjC or Swift helper for Vision OCR).

Screenpipe is MIT licensed, attribution required — add a comment in `capture.py` header.

## Architecture

Replace `provider.py` (44-line HTTP client) with a local capture engine:

```
src/openmy/services/screen_recognition/
├── capture.py          # NEW: screenshot + OCR
├── provider.py         # REWRITE: use capture.py instead of HTTP
├── align.py            # keep
├── enrich.py           # keep
├── hints.py            # keep
├── privacy.py          # keep
├── sessionize.py       # keep
├── settings.py         # modify: remove 3030 dependency
├── summary.py          # keep
```

## Implementation

### [NEW] `capture.py` — Screen Capture Engine

Core logic (~100 lines):

```python
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

def capture_screenshot(output_path: Path) -> Path:
    """Take a screenshot using macOS screencapture."""
    subprocess.run(
        ["screencapture", "-x", "-C", str(output_path)],
        check=True,
        capture_output=True,
    )
    return output_path

def extract_text_from_image(image_path: Path) -> str:
    """OCR using macOS Vision framework via PyObjC."""
    # Use Vision framework (VNRecognizeTextRequest)
    # Fallback: subprocess call to a small Swift helper
    ...

def capture_screen_event() -> dict:
    """Capture one screen event: screenshot + OCR text."""
    timestamp = datetime.now().astimezone().isoformat()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        screenshot_path = Path(f.name)
    capture_screenshot(screenshot_path)
    text = extract_text_from_image(screenshot_path)
    # Get active window title
    active_app = get_active_app_name()
    return {
        "timestamp": timestamp,
        "app": active_app,
        "text": text,
        "screenshot_path": str(screenshot_path),
    }

def get_active_app_name() -> str:
    """Get frontmost app name via AppleScript."""
    result = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'],
        capture_output=True, text=True,
    )
    return result.stdout.strip()
```

### OCR Strategy (pick one, in order of preference)

1. **macOS Vision framework via PyObjC** — best quality, no extra install
   ```python
   import Quartz
   import Vision
   ```
2. **Swift helper script** — compile a tiny Swift CLI that does VNRecognizeTextRequest, call via subprocess
3. **Tesseract fallback** — `brew install tesseract`, lower quality but cross-platform

### [REWRITE] `provider.py`

Replace HTTP client with local capture:
```python
class ScreenRecognitionProvider:
    def fetch_events(self, start_time, end_time) -> list[dict]:
        # Read from local screen_events.json instead of HTTP
        ...
```

### [NEW] Background capture daemon

Add to `capture.py`:
```python
def run_capture_loop(interval_seconds: int = 5, data_root: Path):
    """Background loop: capture screen every N seconds."""
    while True:
        event = capture_screen_event()
        append_to_daily_events(data_root, event)
        time.sleep(interval_seconds)
```

Triggered by `openmy screen on` → starts background thread or subprocess.

### [MODIFY] `settings.py`

- Remove `provider_base_url` (no more 3030)
- Add `capture_interval_seconds` (default 5)
- Add `screenshot_retention_hours` (default 24, auto-cleanup)

### [MODIFY] `config.py`

- Remove `SCREEN_RECOGNITION_API = "http://localhost:3030"`
- Keep `SCREEN_RECOGNITION_ENABLED = False`

## Data Format

`data/{date}/screen_events.json` — array of events:
```json
[
  {
    "timestamp": "2026-04-12T19:30:00+08:00",
    "app": "Antigravity",
    "text": "def build_prompt(vocab_terms)...",
    "window_title": "gemini.py — openmy-clean"
  }
]
```

All existing downstream code (align, sessionize, privacy, hints, summary, enrich) should work with this format — just verify field name compatibility.

## NOT in scope

- Linux/Windows support (macOS only for now)
- Video recording (screenshots only)
- Audio capture (OpenMy already does this)

## Verification

```bash
# Unit tests
python3 -m pytest tests/unit/test_screen_*.py -v

# Manual: start capture, check data file
openmy screen on
sleep 10
cat data/$(date +%Y-%m-%d)/screen_events.json | python3 -m json.tool | head -20
openmy screen off

# Existing screen tests must still pass
python3 -m pytest tests/ -q

# Lint
ruff check .
```

## Git

Single commit: `feat: built-in screen capture engine — no more external Screenpipe dependency`
