---
title: "OpenMy dogfood 全流程阻塞点复盘（2026-05-09）"
module: openmy-pipeline
date: 2026-05-09
problem_type: developer_experience
component: tooling
severity: high
tags:
  - dogfood
  - onboarding
  - pipeline
  - stt
  - dependency
  - error-handling
applies_when:
  - "全新 clone 仓库后首次运行完整 day.run 流程"
  - "使用本地 STT 引擎（funasr / faster-whisper）"
  - "处理大量录音文件（20+ 个，总时长超 30 分钟转写时间）"
  - "录音中包含大量静音/噪音片段（VAD 切出极短 chunk）"
---

# OpenMy dogfood 全流程阻塞点复盘

## Context

2026-05-09 对 OpenMy 做了一次完整的 dogfood 测试：从全新 clone 到处理 5 月 7 日的 22 个 DJI Mic 录音文件（5GB），走完 转写 → 清洗 → 场景切分 → 蒸馏 → 日报 → 核心提取 → 上下文聚合 全流程。过程中碰到 7 个阻塞点，其中 2 个通过代码修复解决，其余是 DX 设计层面的摩擦。

## 阻塞点清单

### 1. CLI 参数接口不一致

**现象**：`openmy run --date 2026-05-07` 报 `unrecognized arguments: --date`。

**原因**：`openmy run` 的 date 是位置参数（`openmy run 2026-05-07`），但 skill 端点用 `--date` flag（`openmy skill day.run --date 2026-05-07`）。Agent 和用户容易搞混。

**影响**：中。首次使用卡一下，看 `--help` 就能解决。

**建议**：统一两套接口的 date 传递方式，或者让 `run` 命令同时接受两种写法。

---

### 2. 选 STT 引擎但依赖没装直接挂

**现象**：`profile.set --stt-provider funasr` 成功，但 `openmy run` 时报"FunASR 依赖没装好"直接退出。faster-whisper 同样。

**原因**：本地 STT 引擎（funasr / faster-whisper）是可选依赖（`pyproject.toml` 的 `[project.optional-dependencies]`），不在默认 `pip install openmy` 里。`profile.set` 不检查依赖是否已安装。

**影响**：高。用户按 health.check 推荐选了引擎，以为配好了，跑的时候才挂。

**建议**：`profile.set --stt-provider X` 时检查对应依赖是否已装，没装就自动装或提示。

---

### 3. Gemini LLM 依赖也是可选的（同一 pattern）

**现象**：转写完成后进入蒸馏，报"Gemini 依赖没装好"。

**原因**：`google-genai` 在 `[project.optional-dependencies].cloud` 里。和 #2 完全相同的 pattern——选了 provider 但依赖没装。

**影响**：高。和 #2 一样，配置时不报错，运行时才挂。

**建议**：同 #2。`install-skills.sh` 可以检测 `.env` 里配的 provider 并自动装对应依赖。

---

### 4. 空 chunk 终止整条管线 ✅ 已修

**现象**：Silero VAD 把录音切成多个 chunk，最后一个只有 1KB（静音尾巴）。faster-whisper 对它返回空结果 → `FriendlyCliError(code=*_empty_transcript)` → 整条管线终止，22 个文件只处理了 1 个的前 3 个 chunk。

**原因**：`audio_pipeline.py` 的 `_transcribe_chunk_with_retry` 不区分"空转写"和"真正失败"。provider 层把空结果当 error raise，pipeline 层没有 catch 这个特定错误。

**修复**：在 `_transcribe_chunk_with_retry` 中 catch `FriendlyCliError`，如果 code 包含 `empty_transcript`，返回空 `TranscriptionResult` 而不是 re-raise。

**文件**：`src/openmy/services/ingest/audio_pipeline.py:391-423`

---

### 5. 30 分钟超时中断后续步骤

**现象**：22 个文件的转写耗时超过 30 分钟 → run.py 的超时机制触发 → 转写完成了但清洗/切场景/蒸馏/日报全跳过。

**原因**：`run.py` 有 `RUN_TIMEOUT_SECONDS` 硬编码超时。转写是最耗时的步骤，大文件量容易超。

**影响**：高。用户以为失败了，实际转写是成功的。需要知道用 `--skip-transcribe` 续跑。

**绕过**：`openmy run 2026-05-07 --skip-transcribe` 跳过转写从清洗继续。

**建议**：超时后自动用 `--skip-transcribe` 续跑，或者把超时改成按步骤而不是全流程。

---

### 6. `cmd_distill` 没有 per-scene 错误处理 ✅ 已修

**现象**：蒸馏 43 个场景，第一个场景 Gemini 返回空结果 → 整个蒸馏终止（`0/43` 就挂了）。

**原因**：`show.py` 的 `cmd_distill` 直接调 `summarize_scene` **没有 try/except**。而 `distiller.py` 的 `_distill_scene_job`（给 `distill_scenes` 用的）有 per-scene 错误处理。`run.py` 调的是 `cmd_distill`（没保护），不是 `distill_scenes`（有保护）。

**修复**：在 `cmd_distill` 的循环里给 `summarize_scene` 加 try/except，失败时 `summary = ""`，跳过继续。

**文件**：`src/openmy/commands/show.py:437-439`

---

### 7. Gemini prompt 对低质量文本返回空

**现象**：部分场景文本是噪音/重复/串台（如"TED Talk TED Talk TED Talk Postgres 鼓掌"反复），Gemini 遵守 prompt 指令"无实质内容输出空字符串"返回空。但 `gemini.py:90-99` 把空结果当 error raise。

**原因**：`generate_text` 不区分"模型拒绝回答"和"模型按指令返回空"。对于蒸馏任务，空是合法返回值（prompt 里要求的）。

**影响**：中。被 #6 的修复覆盖了（per-scene catch），但根因还在——`generate_text` 的"空=error"假设对蒸馏场景不成立。

**建议**：让 `generate_text` 接受一个 `allow_empty=False` 参数，蒸馏调用时传 `True`。

## 修复代码变更

| 文件 | 改动 |
|------|------|
| `src/openmy/services/ingest/audio_pipeline.py` | `_transcribe_chunk_with_retry` catch `empty_transcript` 返回空结果 |
| `src/openmy/commands/show.py` | `cmd_distill` 循环加 try/except |

## 全流程最终结果

修复 #4 和 #6 后，5 月 7 日 22 个录音文件全流程跑通：
- 转写：31,575 字（含空 chunk 跳过）
- 清洗：18,476 字
- 场景：64 个
- 蒸馏：43 个场景（部分空结果跳过）
- 日报：生成成功
- 核心提取 + 上下文聚合：完成

## 优先级排序

| # | 阻塞点 | 严重度 | 状态 |
|---|--------|--------|------|
| 4 | 空 chunk 终止管线 | 高 | ✅ 已修 |
| 6 | cmd_distill 无错误处理 | 高 | ✅ 已修 |
| 2 | STT 依赖没装就挂 | 高 | 待修 |
| 3 | LLM 依赖没装就挂 | 高 | 待修 |
| 5 | 30 分钟超时 | 高 | 待修 |
| 7 | generate_text 空=error | 中 | 待修（被 #6 掩盖） |
| 1 | CLI 参数不一致 | 中 | 待修 |
