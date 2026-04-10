# OpenMy

Turn one audio file into a browsable daily report and structured personal context.

![OpenMy quick start screenshot](docs/images/openmy-quick-start.png)

[中文](README.md)

## Quick Start

```bash
git clone https://github.com/openmy-ai/openmy.git
cd openmy

python3 -m venv .venv
source .venv/bin/activate
pip install .

echo "GEMINI_API_KEY=your-key" > .env
openmy quick-start path/to/your-audio.wav
```

`openmy quick-start` will:

1. check Python and FFmpeg
2. load `.env` from the repo root
3. transcribe the audio
4. clean text, split scenes, resolve roles, distill summaries
5. generate the daily report and extracted metadata
6. start the local web UI
7. open `http://127.0.0.1:8420` in your browser

## Requirements

- Python 3.10+
- FFmpeg
- a Gemini API key

If FFmpeg or Python is missing, the CLI prints a human-readable install hint.

macOS:

```bash
brew install python@3.11
brew install ffmpeg
```

## Tests

```bash
python3 -m pytest tests
```

The test suite is expected to pass without a real API key.

## Optional Screenpipe Integration

Screenpipe is optional. OpenMy can use it as extra screen context, but the main daily report flow works without it.

## License

[MIT](LICENSE)
