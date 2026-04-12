---
name: openmy-health-check
description: Use when verifying the runtime environment is ready or helping the user fix missing setup
---

# OpenMy Health Check

## Purpose

Verify that the runtime environment is ready and help the user fix missing setup.

## Trigger

Use it when:
- first-time setup looks incomplete
- the user asks whether OpenMy is working
- processing failed because setup is missing
- you need to compare available speech-to-text engines

## Action

- `openmy skill health.check --json`

## Restrictions

- Do not guess environment state without checking.
- Only edit `.env` after the user confirms the change (e.g., choosing an STT engine).
- Do not switch providers silently.

## Output

- lead with `human_summary`
- list setup problems in priority order
- explain which speech-to-text engine is active and which ones are ready
- explain whether `llm_available` is true or false
- end with one concrete next fix

## Agent Behavior

### Output Format (STRICT)

Your reply to the user MUST follow this exact structure. No extra paragraphs, no "顺手提醒", no filler.

```
[一句话状态]

选一个转写引擎：

🏠 本地（不需要 key，直接用）
- funasr — 中文推荐 ✅
- faster-whisper — 英文推荐

☁️ 云端（需要 API key）
- dashscope（阿里百炼）— 中文精度最高
- gemini（Google）— 全能型
- groq — 最快
- deepgram — 企业级

选哪个？
```

- If the user's language is Chinese, mark `funasr` with ✅. If English, mark `faster-whisper` with ✅.
- Do NOT explain what LLM keys are, what vocab is, or what screen recognition does. The user did not ask.
- Do NOT say "顺手提醒" or add disclaimers about incomplete setup. If something is missing, fix it silently or save it for later.

### After the User Chooses

1. Set `OPENMY_STT_PROVIDER=<chosen>` in `.env` immediately.
2. If the engine needs an API key:
   - Tell the user where to get it (one link, one line):
     - dashscope → https://bailian.console.aliyun.com/
     - gemini → https://aistudio.google.com/apikey
     - groq → https://console.groq.com/keys
     - deepgram → https://console.deepgram.com/
   - Say: "把 key 发给我，我帮你配好。"
   - User pastes key → write to `.env` → confirm: "配好了。"
3. If the engine is local, just confirm and move on.
4. Then ask where the user's recordings usually land:
   - "你的录音通常存在哪个文件夹？比如：~/Documents/DJI-Mic/"
   - "告诉我路径，以后自动从那里找录音。不知道的话可以跳过。"
5. If the user gives a path:
   - verify the folder exists
   - save it with `openmy skill profile.set --audio-source "..." --json`
   - confirm: "配好了。以后直接说‘处理今天的录音’就行。"

### Other Rules

- If `data.healthy` is true, say the environment is ready in one line.
- If profile is missing, run `profile.set` silently (auto-detect timezone/language). Do NOT ask the user.
- If vocab is missing, run `vocab.init` silently. Do NOT tell the user.
- If `llm_available` is false, do NOT mention it unless the user asks. Audio processing works without it.
