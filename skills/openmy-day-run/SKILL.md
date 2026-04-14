---
name: openmy-day-run
description: Use when processing new audio, re-running one day, or finishing missing outputs for a date
---

# OpenMy Day Run

## Purpose

Process new audio, re-run one day, or finish missing outputs for a date.

## Trigger

Use it when:
- the user gives audio
- the user wants to process one day
- the user wants to re-run one day
- the user wants to complete missing outputs for a day

## Action

- `openmy skill day.run --date YYYY-MM-DD --audio path/to/audio.wav --json`
- `openmy skill day.run --date YYYY-MM-DD --skip-transcribe --json`

## Restrictions

- Do not call internal modules directly.
- Do not ask the user to assemble commands manually.
- Do not change raw evidence files by hand.
- Do not go silent for more than 30 seconds during long work.

## Pre-Run Check

Before any `day.run` in a session:
1. **先确认这次到底要用哪个模型。** 不要默认沿用旧设置就直接开跑。
2. If the user did not specify a model, and `profile` has no `stt_provider` set, or the active provider is not ready, **route to `openmy-health-check`** and let the user choose an engine. Do NOT pick one silently.
3. If the user explicitly switches to another model for this run, treat that as a fresh model choice. Re-check whether that exact route is ready **before** calling `day.run`.
4. If the chosen model is cloud-based and the key is missing, stop there and ask for the key first. **Do NOT start transcription and wait for a missing-key error.**
5. Once the user has chosen and `profile.set --stt-provider` has been run, proceed with `day.run`.

一句话：**先选模型，再转写；云端没密钥，就别开跑。**

## Batch Processing

When the user asks to process multiple days at once:
1. List the unprocessed dates and confirm how many days will be processed.
2. Process in **chronological order** (oldest first) so aggregation builds correctly.
3. After each day completes, give a **one-line summary** (e.g., "4/1 ✅ 3 场景，2 个决策").
4. If one day fails, **skip it and continue** with the next. Record the failure.
5. After all days finish, give a **summary table** showing pass/fail per day.
6. If the batch is large (>3 days), warn the user about estimated time before starting.

## Output

- start with `human_summary`
- then inspect `data.run_status`
- if a step is skipped, explain `skip_reason`
- if the user only wants to inspect results, route to `openmy-day-view`

## Audio Input Guide

- OpenMy accepts normal audio files from wireless mics, phones, meetings, and screen recorders.
- If the user mentions a device, first look for files already saved on disk.
- Do **not** start live recording unless the user explicitly says they want to record now.
- If audio is on external storage, copy it into the local day folder first, then process the local copy.

## Progress Reporting

1. Before `day.run`, report how many files were found, which engine will be used, and the rough estimate.
2. If a cloud engine is used, split big batches automatically.
3. After the run, summarize each major step and what happened.
4. Always mention the local page if results are ready.

Use this progress skeleton when the run is long enough to need structure:

```text
进度表：
- ✅ 已发现音频：X 个
- ✅ 已选引擎：...
- ✅ 转写：...
- ✅ 清洗：...
- ✅ 切段：...
- ✅ 蒸馏：...
- ✅ 抽取：...
- ⏭️ 跳过步骤：...（如果有）
- ❌ 失败步骤：...（如果有）
- 下一步：...
```

## Web UI Support

- The local page at `localhost:8420` can accept dragged audio files directly.
- The page shows the 4-stage progress panel: transcribe → clean → segment → distill.
- The page can pause, cancel, or skip the current step when the job allows it.
- The agent does not need to call the web endpoints manually for normal runs, but should tell the user they can open the page to watch progress.

## Autonomous Distillation Default

If audio processing finishes but later AI steps are still missing:
1. Lead with what is already done.
2. If the user has **not** expressed a preference, continue with the agent-side distillation and extraction path immediately.
3. Only stop and ask first if the user explicitly said they prefer configuring a key instead.
4. After the agent-side path finishes, tell the user that the audio part was already done and you finished the later two steps for them.

## 自检规则

发回复前检查：
- 不要把"因为没配 Gemini key"当成主句。
- 不要把"缺少 LLM API key"当成主句。
- 主句必须先说"音频已经跑完了"或者"我已经继续把后面两步做完了"。
- 不要列选项让用户选。直接继续做。
- 不要超过 3 句话就开始干活。

### Demo 跑完后的固定话术

如果是 `quick-start --demo` 跑完，停在 distill：

```
音频转写和场景切分都搞定了。后面两步整理我现在就帮你做。
```

然后立刻执行 `distill.pending` → `distill.submit` → `extract.core.pending` → `extract.core.submit`。

禁止说的话：
- ❌ "如果你愿意，我下一步可以……"
- ❌ "你有两个选择：A 或 B"
- ❌ "需要配置 Gemini API Key"
- ❌ 贴 run_status.json 路径
- ❌ 贴 transcript.md 或 scenes.json 路径

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message` first.
2. Common recovery:
   - `missing_audio` → find the saved recordings or ask the user where they are.
   - `missing_profile` → route to `openmy-profile-init`.
   - `missing_engine` → route to `openmy-health-check`.
   - `missing_reusable_data` → rerun without `--skip-transcribe`.
   - `permission_denied` → explain which folder could not be read or written.
3. Never silently swallow errors.
4. Never retry the same failing step more than once without telling the user.
