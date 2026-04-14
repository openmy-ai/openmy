---
name: openmy-install
description: Use when verifying the runtime environment is ready or helping the user finish first-time installation
---

# OpenMy Install

## Purpose

Guide the agent through first-time installation when `openmy` command is not available.

## Trigger

Use it when:
- `openmy` command is not available
- the user says "install openmy" or "set up openmy"
- `health.check` fails with import errors

**IMPORTANT**: Always use `git clone`, never `pip install openmy`. The agent needs the repo for CLAUDE.md and skills/ directory.

## Action

- `openmy skill health.check --json`

## Restrictions

- Do NOT tell the user to do these steps manually.
- Run the setup yourself whenever the machine is ready.
- If Python version is too low, tell the user one concrete command to fix it.
- Do not skip a failed step and jump ahead.
- **NEVER use `pip install openmy`.** Always clone the repo.

## Output

- start with `human_summary`
- say whether installation is already ready or still missing pieces
- if setup was needed, say that the virtual environment and command entry are ready
- end with one concrete next step

## Steps

1. Clone the repo: `git clone https://github.com/openmy-ai/openmy.git && cd openmy`
   - If already in the repo (pyproject.toml exists with openmy), skip this step.
2. Run `bash scripts/install-skills.sh`
   - This script handles: Python check, venv creation, pip install, .env setup, skill symlinking.
3. Verify: `.venv/bin/openmy --help`
4. Run demo: `openmy quick-start --demo`
5. Open frontend: `openmy view`
6. Route to `openmy-health-check`.

## Post-Install Reply Script (MANDATORY)

After installation succeeds, the agent MUST use the following scripts.
Do NOT improvise. Do NOT add options, explanations, or technical details beyond what is listed.

### IMPORTANT: Always open the frontend after install

After ANY successful install, run `openmy view` to start the local web server and open `localhost:8420` in the browser. The user needs to see the onboarding UI immediately.

### Scenario A: Install only (no demo, no audio)

```
✅ OpenMy 装好了。
```

Open `localhost:8420` first, then route to `openmy-health-check` for engine selection.

### Scenario B: Install + demo ran, partial success (distill pending)

```
✅ OpenMy 装好了，demo 也跑通了。

音频转写和场景切分都没问题。后面还有两步整理，我现在就帮你做。
```

Open `localhost:8420`, then **immediately continue** with `distill.pending` → `distill.submit` → `extract.core.pending` → `extract.core.submit`.
Do NOT stop and ask. Do NOT list options A/B. Do NOT mention "Gemini API Key" or "LLM".

### Scenario C: Install + demo ran, full success

```
✅ OpenMy 装好了，demo 全部跑通了。

准备好处理自己的录音了吗？你的录音通常存在哪个文件夹？
```

Open `localhost:8420` (should already be open from the run).

### What NOT to say after install

- ❌ 不要列三个选项让用户选
- ❌ 不要提 "Gemini API Key"、"LLM"、"distill"、"agent token"
- ❌ 不要解释 run_status.json 或 partial success 的技术含义
- ❌ 不要贴文件路径
- ❌ 不要说 "如果你愿意，我下一步可以继续帮你：1. 2. 3."
- ❌ 不要超过 3 句话

## Error Handling

If any command returns `ok: false` or a shell step fails:
1. Read the exact error message first.
2. Common recovery:
   - Python missing or too old → show one install command for this machine.
   - `.venv` creation failed → check disk space and write permission.
   - install failed because `ffmpeg` is missing → install `ffmpeg`, then retry once.
   - import error after install → rerun the editable install once, then route to `openmy-health-check`.
3. Never ask the user to open a terminal and do it themselves.
4. Never retry the same failing step more than once without reporting the failure.
