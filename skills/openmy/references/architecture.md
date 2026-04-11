# OpenMy Architecture

## Core definition

OpenMy is a personal context engine.
It is not an MCP server and not a generic note tool.

The fixed architecture is:

```text
personal context engine
  + router skill layer
  + sub-skill workflow layer
  + CLI execution layer
  + frontend display layer
```

## Responsibility split

### 1. Personal context engine

Core assets:
- `data/active_context.json`
- `data/corrections.jsonl`
- `data/profile.json`
- per-day data folders
- `src/openmy/services/*`

This layer owns state, evidence, processing, and correction history.

### 2. Router skill layer

The router skill only:
- classifies the task
- picks the right sub-skill
- enforces boundaries and order

### 3. Sub-skill workflow layer

Each sub-skill handles one workflow only:
- startup context
- context reading
- context query
- single-day processing
- single-day viewing
- corrections
- status review
- vocab setup
- profile setup

### 4. CLI execution layer

The stable backend entrypoint is:

```bash
openmy skill <action> --json
```

The CLI executes contracts.
It does not define the product.

### 5. Frontend display layer

`app/` is for human viewing only.
Human entrypoint stays `openmy quick-start`.
Agent entrypoint stays `openmy skill ... --json`.

## Current processing chain

```text
audio
  -> ingest
  -> cleaning
  -> segmentation
  -> distillation
  -> extraction
  -> consolidation
  -> active_context / corrections
  -> agent / frontend
```
