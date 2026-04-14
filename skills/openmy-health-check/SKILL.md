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

**HARD STOP: must wait for user response.**
- After showing engine choices, STOP and WAIT for the user to pick one.
- Do NOT auto-select the recommended engine. Do NOT run `profile.set --stt-provider` until the user replies.
- Do NOT start downloading models or running `day.run` until the user has chosen.
- The user saying "ok" / "good" / "that one" / "recommended" counts as choosing. Silence does not.
- This is the ONE question in the entire setup where you MUST wait. Everything else can be auto.

- Read the recommendation from `data.onboarding.headline`, `data.onboarding.primary_action`, and `data.onboarding.choices`.
- Do NOT explain what LLM keys are, what vocab is, or what screen recognition does unless the user explicitly asks.
- Do NOT dump raw `issues` first. Recommendation first, details later.

### After the User Chooses

**这一步是转写入口的铁规则：先把模型定下来，再开始转写。**

1. Run `openmy skill profile.set --stt-provider <chosen> --json` immediately.
2. 只要用户这次选的是云端模型，就在这里把密钥要齐。**没拿到密钥前，不要开始 `day.run`。**
3. 不要用“先跑一次，报错了再回来补密钥”这种绕路做法。
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

### Auto vs Must-Ask

| Action | Auto | Must Ask |
|--------|------|----------|
| Detect timezone and language | Yes | |
| Set profile basics | Yes | |
| Initialize vocab | Yes | |
| **Choose STT engine** | | **Yes** |
| Download local model | | **Yes (after user chose)** |
| Start transcription | | **Yes (after engine confirmed)** |

