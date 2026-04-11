# Contributing to OpenMy

Thanks for your interest in OpenMy.

## Development setup

```bash
git clone https://github.com/openmy-ai/openmy.git
cd openmy
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run tests

```bash
python3 -m pytest tests/ -v
```

The test suite does not require live API keys by default.

## Commit style

Use Conventional Commits when possible:

- `feat:` new features
- `fix:` bug fixes
- `refactor:` internal restructuring without behavior changes
- `docs:` documentation updates
- `test:` test-only changes
- `chore:` maintenance work

## Pull requests

1. Create a feature branch from the latest `main`
2. Add or update tests for the change
3. Run the full test suite
4. Open a PR with a clear summary, rationale, and verification notes

## Code style

- Python 3.10+
- English identifiers in code
- User-facing copy should stay concise and product-oriented
- Keep service boundaries explicit; avoid importing private internals across modules
