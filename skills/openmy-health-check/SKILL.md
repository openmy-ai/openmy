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


## Error Handling

If `health.check` itself fails:
1. Read `error_code` and `message`.
2. If the failure is about missing imports or runtime tools, route to `openmy-install`.
3. Unknown errors should be surfaced plainly and treated as a setup problem until proven otherwise.

## Agent Behavior

### Output Format (STRICT)

Your reply to the user MUST follow this order. No filler, no long warning block.

```
[一句话结论：先说推荐路线]

推荐你先走：
- [推荐路线名称]
- 原因：[一句人话原因]

如果你想自己挑，再看下面：

🏠 本地
- funasr — 中文优先 ✅
- faster-whisper — 通用优先

☁️ 云端
- dashscope — 中文更强
- gemini — 省事
- groq — 快
- deepgram — 英文更强

要不要先按推荐路线来？
```

- Read the recommendation from `data.onboarding.headline`, `data.onboarding.primary_action`, and `data.onboarding.choices`.
- Do NOT explain what LLM keys are, what vocab is, or what screen recognition does unless the user explicitly asks.
- Do NOT dump raw `issues` first. Recommendation first, details later.

### After the User Chooses

1. Run `openmy skill profile.set --stt-provider <chosen> --json` immediately.
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
