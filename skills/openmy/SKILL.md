---
name: openmy
description: >
  Use when the task involves OpenMy data, audio processing, transcription,
  daily context, corrections, vocabulary, profile setup, onboarding, or
  first-time setup. Routes to the correct sub-skill and enforces
  communication style (plain language, no jargon, no file paths).
---

# OpenMy Router Skill

OpenMy is a personal context engine.
It is **not** an MCP server, not a note app, and not a generic chat wrapper.

The fixed stack is:

- personal context engine
- router skill layer
- sub-skill workflow layer
- CLI execution layer
- frontend display layer

## Input Surfaces

OpenMy now has three real input surfaces:
- CLI commands
- agent skill commands
- the local web UI at `localhost:8420`

Uploaded files from the web UI are stored in the `data/inbox/` directory before the pipeline job starts.

Reference files:
- `skills/openmy/references/architecture.md`
- `skills/openmy/references/action-contracts.md`
- `skills/openmy/references/routing-rules.md`

## When to use this skill

Use this skill when:
- the task is about OpenMy data, processing, corrections, status, or onboarding
- you need to choose the right sub-skill before acting
- you need to enforce the stable command boundary

## Routing map

- installation / first clone → `openmy-install`
- startup context → `openmy-startup-context`
- context snapshot reading → `openmy-context-read`
- structured context search → `openmy-context-query`
- day processing / re-run → `openmy-day-run`
- single-day result reading → `openmy-day-view`
- correction write-back → `openmy-correction-apply`
- overall status review → `openmy-status-review`
- vocabulary initialization → `openmy-vocab-init`
- profile onboarding → `openmy-profile-init`
- environment and engine check → `openmy-health-check`
- **change / switch STT engine** → `openmy-health-check` (run health.check, show engines, let user pick, update `.env`)
- agent-side scene distillation handoff → `openmy-distill`
- agent-side core extraction handoff → `openmy-extract`
- weekly / monthly summary refresh → `openmy-aggregate`
- export setup → `openmy-export`
- screen recognition setup → `openmy-screen-recognition`

## Mandatory Sub-Skill Reading (HARD CONSTRAINT)

Before routing to any sub-skill, the agent MUST read that sub-skill's `SKILL.md` first.
Do NOT execute without reading. This is not a suggestion.

The following sub-skills have critical agent behavior rules that MUST be read:

| Route | Must-Read Before Execution |
|-------|---------------------------|
| openmy-day-run | `openmy-day-run/SKILL.md`（进度汇报、禁止沉默、distill 停住时的回复） |
| openmy-distill | `openmy-distill/SKILL.md`（双选项呈现、pending/submit 流程） |
| openmy-extract | `openmy-extract/SKILL.md`（核心提取、补交流程） |
| openmy-install | `openmy-install/SKILL.md`（首次安装步骤） |

If you skip reading and produce a reply that violates the sub-skill rules,
you have failed the task.

⚠️ 执行 `day.run` 或 `quick-start` 前，Agent 必须先完整阅读以下子技能文档：
- `skills/openmy-day-run/SKILL.md`
- `skills/openmy-distill/SKILL.md`
- `skills/openmy-extract/SKILL.md`

不读完不准执行。这是硬约束，不是建议。

## Global rules

- Do not ask the user to type commands manually.
- Do not bypass `openmy skill <action> --json` to call internal modules.
- Do not edit `active_context.json`, `corrections.jsonl`, `scenes.json`, `meta.json`, or `profile.json` directly.
- Do not treat the frontend as the execution surface.
- The web UI is a valid user entry point even when the agent still prefers the skill command boundary for execution.
- Do not describe OpenMy as an MCP-first product.
- When the user mentions a device or source such as DJI Mic, phone voice memos, meeting recorder, or screen recording, assume they mean **existing recordings already saved on disk**.
- Do **not** start live recording, open the microphone, or switch into realtime transcription unless the user explicitly says they want to record **now**.
- Default interpretation:
  - "去找大疆麦克风录音" = find the recorded audio files
  - "打开麦克风开始录" = start live recording

## Date Resolution

Resolve relative dates using the current system date.
- "昨天" / "yesterday" = today - 1
- "上周" / "last week" = previous ISO week
- "这个月" / "this month" = current `YYYY-MM`
- If a relative date is still ambiguous, choose the most recent matching date and say what you chose.

## Error Handling

If any skill command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - `missing_audio` → help the user find recordings on disk.
   - `missing_profile` → route to `openmy-profile-init`.
   - `missing_engine` → route to `openmy-health-check`.
   - `permission_denied` → explain which path needs access.
   - `invalid_payload` → reread the schema and regenerate once.
3. For unknown errors, show the plain-language error and route to `openmy-health-check`.
4. Never silently swallow an error. Never retry more than once without telling the user.

## Critical: API Keys Are Optional

OpenMy works out of the box with local speech-to-text engines.
No API key is needed to process audio.
- `faster-whisper` and `funasr` run locally and are always ready.
- API-based engines (`gemini`, `groq`, `dashscope`, `deepgram`) need keys, but they are optional upgrades.
- LLM keys (`GEMINI_API_KEY`) are needed for distillation and extraction, but there are TWO ways to handle this — let the user choose.
**Never tell the user they must configure an API key before processing audio.**
Run `health.check` first. It shows which engines are already ready.

### Distillation & Extraction: Two Options

When `llm_available` is false, there are still two paths:

| Option | How | Cost | Speed |
|--------|-----|------|-------|
| **A. Configure a Gemini API key** | Add `GEMINI_API_KEY` to `.env`. OpenMy calls `gemini-flash-lite` directly. | Very cheap (~$0.01/day, free tier available) | Fast, fully automated |
| **B. Let me (the agent) do it** | Agent reads scenes via `distill.pending`, writes summaries with its own model, submits via `distill.submit`, then finishes extraction. | Uses the current agent budget | Slower, but zero config |

**Autonomous default:** if the user has not expressed a preference, default to Option B and continue immediately.
Only stop and ask first if the user explicitly says they prefer Option A.
After Option B finishes, tell the user what you completed and briefly mention that a Gemini key is only an optional convenience.

## Communication Style

When presenting results to users:
- Talk like a human assistant, not a developer tool.
- Use plain Chinese. Avoid tool jargon like "LLM", "structure extraction", "provider", "pending", or "API" unless you immediately explain them in normal language.
- Never show raw file paths. Say "your profile is saved" instead of a full path.
- Never dump JSON. Read it and summarize it in plain language.
- **Never explain code logic to the user.** Do not reference `.py` files, function names, variable names, code line numbers, or internal pipeline steps. The user does not read code. Answer their question in plain language, one sentence.
- **Never change settings without asking.** Do not silently switch STT provider, change `.env`, or modify any config. Always confirm with the user first.
- Never ask users to type terminal commands. Run the commands yourself.
- **Never tell users to open a terminal or check logs.** All status updates happen right here in the chat.
- **Never go silent.** If a command takes more than 30 seconds, give an update. Users should never wonder "is it still working?"
- Use short paragraphs, not long bullet lists.
- Lead with what matters first.
- Use emoji sparingly for visual hierarchy.
- When listing items, prefer one compact sentence over a long list.
- End with a question or suggestion, not a status dump.
- **Never say or imply:** "You must configure Gemini before audio can run."
- When audio is already processed and only the later AI steps are missing, say it plainly:
  - "音频已经跑完了。后面两步整理我现在就帮你做。"

## Transcription Entry Iron Rule

When the user is about to start transcription, always do this first:

1. **先过模型选择这一步** — 不要先跑起来再补问。
2. 如果用户没有明确指定模型，就按 `health.check` 的推荐路线问一次。
3. 如果用户明确指定了模型，也要立刻检查那条路线现在能不能用。
4. 如果用户选的是本地模型，而且依赖齐全，就直接继续。
5. 如果用户选的是云端模型，就先要密钥；**没拿到密钥前，不准开跑。**
6. 不要等 `day.run` 报错以后，才回头补“你还没配这个模型”。

一句话：**先选模型，再转写。选云端，就先拿密钥。**

## First-Time Setup Flow

If this looks like a first-time setup:

1. **Always start with `openmy-health-check`** — it now gives a recommended route, a one-line headline, and grouped engine choices.
2. **Auto-setup profile** — if `health.check` says profile is missing or still has defaults (`name=User`, `timezone=UTC`), detect the system timezone and conversation language, then run `profile.set` immediately. Do NOT ask the user — just set it and tell them what you did.
3. **Ask the user to choose an STT engine — then STOP and WAIT.** Present the recommended route first, then ask. **Do NOT auto-select.** Do NOT run `profile.set --stt-provider` until the user replies. Do NOT start downloading models. This is the ONE question you must ask during first setup, and you must wait for the answer before proceeding.
4. Route to `openmy-vocab-init` if vocab is missing.
5. Help the user locate the first audio file.
6. Route to `openmy-day-run`.
7. Review the result with the user.
8. Suggest corrections if the transcript clearly has errors.
9. Route back to `openmy-vocab-init` if you discover more names or terms.
10. **If `day.run` returns `partial` because of missing later AI steps** — default to the agent-side path and continue with distillation plus extraction unless the user explicitly asked to configure a key instead. See the "Distillation & Extraction: Two Options" section above.

### First-Run Reply Shape (MANDATORY SCRIPT)

After first-time setup, the agent MUST follow these exact patterns. No improvisation.
**After ANY install, always open `localhost:8420`** by running `openmy view`. The user needs to see the onboarding UI.

**If install + demo succeeded (partial — distill pending):**
```
✅ 装好了，demo 也跑通了。音频转写和场景切分都没问题。
后面两步整理我现在就帮你做。
```
→ Open `localhost:8420` → then immediately execute distill.pending → distill.submit → extract.core.pending → extract.core.submit. Do NOT stop, do NOT list options.

**If install succeeded, no demo yet:**
```
✅ 装好了。
```
→ Open `localhost:8420` → then route to health-check for engine selection.

**If install + demo fully succeeded:**
```
✅ 装好了，demo 全部跑完了。准备好处理自己的录音了吗？
```
→ `localhost:8420` should already be open from the run.

**Hard constraints on first-run replies:**
- Maximum 3 sentences before taking action
- Always open the frontend — the user needs to see it
- Never mention: LLM, API key, Gemini, distill, agent token, run_status.json
- Never list numbered options (1. 2. 3.)
- Never paste file paths
- Never say "如果你愿意" or "你可以选择"

## Typical Daily Workflow

1. user records audio during the day
2. route to `openmy-day-run`
3. route to `openmy-day-view`
4. route to `openmy-correction-apply` for any fixes
5. route to `openmy-context-read` or `openmy-status-review` for follow-up

When the next step is unclear, start with `openmy-status-review`.

## Proactive Patterns

Always apply these checks:

- if words look like transcription errors, suggest corrections
- if open loops keep piling up, ask which ones should be closed
- if several recent days have no data, ask whether recordings exist
- if a new proper noun appears, suggest adding it to vocab
- if setup looks broken, route to `openmy-health-check`

## Feature Discovery

After basic setup is done, proactively ask about optional features.

### Export Integration

Ask: "Would you like your daily summaries automatically saved to a note-taking app?"
- If yes, ask which one: Obsidian or Notion.
- For Obsidian, ask for the vault folder path.
- For Notion, guide the user to get an API key and database ID.
- Run `health.check` afterward to confirm the setup.

### Screen Recognition

Ask: "OpenMy can also use screen context to make the daily summary richer. Want me to turn that switch on?"
- Explain clearly: "Screen data stays on your machine. It helps match what you said with what you were doing on screen."
- If yes, run `openmy skill profile.set --screen-recognition on --json`, then `health.check`.
- If no, run `openmy skill profile.set --screen-recognition off --json` and move on quietly.

### STT Engine Upgrade

If the user processed audio with `faster-whisper`, ask:
"The built-in engine works fine. If you want higher Chinese accuracy, you can switch to Qwen with a free Alibaba API key. Want me to help set that up?"
