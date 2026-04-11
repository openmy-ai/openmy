# OpenMy Skill 体系完善 — Codex 实施计划（定稿）

五大块：词库自动化 + 国际化 + Skill 补全 + Agent 编排增强 + Agent 主观能动性。

---

## Part A：`vocab.init` 自动化词库初始化

### 设计核心

> **代码只做文件操作，Agent 做高频词发现。** 不写扫描脚本。

### A1. cleaner.py — 写时复制

修改 `resolve_resource_path()` 加 `auto_init` 参数：

```python
def resolve_resource_path(primary: Path, fallback: Path, *, auto_init: bool = False) -> Path | None:
    if primary.exists():
        return primary
    if fallback.exists():
        if auto_init:
            import shutil
            shutil.copy2(fallback, primary)
            return primary
        return fallback
    return None
```

- `load_corrections()` 调用时传 `auto_init=True`
- `sync_correction_to_vocab()` 不存在 vocab.txt 时先从 example 初始化

### A2. skill_dispatch.py — 新增 `handle_vocab_init()`

极简：只检查文件是否存在，不存在就从 example 复制。返回状态。注册到 `ACTION_HANDLERS["vocab.init"]`。

### A3. day.run 自动引导

`handle_day_run()` 成功后，检查 corrections.json 是否存在，不存在就在 `next_actions` 加：
```
"Personal vocab not initialized. Run: openmy skill vocab.init --json"
```

### A4. Skill 文档

新建 `skills/openmy-vocab-init/SKILL.md`（英文）。重点写 Agent Behavior（见 Part E）。

### A5. 测试（2 个）

- `test_vocab_init_creates_files_from_example`
- `test_vocab_init_idempotent`

---

## Part B：Skill 国际化全量英文化

### B1. 7 个 SKILL.md 全部翻成英文

保持 Purpose / Trigger / Action / Restrictions / Output 结构。

### B2. skill_dispatch.py 字符串英文化

所有 `human_summary`、`message`、`hint`、`next_actions` 中→英。参照：

| 中文 | 英文 |
|------|------|
| 还没有任何 OpenMy 数据。 | No OpenMy data found. |
| 共有 N 天数据；最近一天是 X。 | N days of data available; latest: X. |
| 活动上下文已更新。 | Active context updated. |
| 查询已完成。 | Query complete. |
| 缺少日期参数。 | Missing date argument. |
| 缺少纠错动作。 | Missing correction operation. |
| 已记录纠错动作：X。 | Correction recorded: X. |
| X 的处理失败了。 | Processing failed for X. |
| 不支持的 skill 动作：X | Unsupported skill action: X |
| X 处理完成。 | Processing complete for X. |
| X 已部分完成。 | X partially complete; main artifacts saved but some steps failed. |
| 要求跳过转写，但当天没有任何可复用数据。 | Skip-transcribe requested, but no reusable data found for that date. |
| 没有输入音频，也没有现成 transcript 数据。 | No audio provided and no existing transcript data. |
| X 纠错动作缺少日期。 | Correction operation X requires a date. |
| 纠错动作执行失败：X | Correction operation failed: X |
| 查看 run_status 并决定是否补跑失败步骤。 | Check run_status and decide whether to re-run failed steps. |
| 如需刷新上下文视图，再运行... | To refresh context view, run... |
| 查询已完成。 | ❌ **改为动态生成**（见下方） |

**代码改动：context.query human_summary 动态化**

`handle_context_query()` 的 `human_summary` 当前硬编码为 `"查询已完成。"`，不管查到什么都一样。改为根据 kind + 结果数量动态生成：

```python
count = len(result.get("items", []))
kind = str(getattr(args, "kind", ""))
human_summary = f"Found {count} {kind}(s)." if count else f"No {kind}s found."
```

### B3. example 资源文件英文化

- `corrections.example.json` — `_comment` 和 `context` 字段
- `vocab.example.txt` — 注释和说明

### B4. references 目录英文化

- `references/architecture.md`
- `references/action-contracts.md`
- `references/routing-rules.md`

> [!IMPORTANT]
> CLI 终端输出暂不动（cli.py / commands/run.py 的 console.print）。

---

## Part C：Skill 体系补全

### C1. 新建 `openmy-context-query/SKILL.md`（英文）

### C2. 更新 `action-contracts.md`

加 `context.query`、`vocab.init`、`profile.get`、`profile.set` 契约。

### C3. 更新 `routing-rules.md`

路由表加 context.query、vocab.init、profile.init。

### C4. 丰富所有 Skill 触发条件

每个 Skill 加 3-5 个自然语言意图示例（英文）。

### C5. README 加 Agent 安装引导

"Install Skills for Your Agent" 段落。

---

## Part D：Agent 编排增强

### D1. profile.init — 用户画像初始化

1. consolidation.py：硬编码用户画像改为读 `data/profile.json`，不存在用默认值
2. skill_dispatch.py：新增 `handle_profile_get()` + `handle_profile_set()`
3. 新建 `skills/openmy-profile-init/SKILL.md`（英文）
4. cli.py：skill 子命令加 `--name` / `--language` / `--timezone` 参数

### D2. 暴露 skip_reason

1. commands/run.py：`_mark_step()` 加 `skip_reason` 参数
2. 所有 skipped 步骤补 `skip_reason` 值
3. day-run Skill 文档 Output 部分加 skip_reason 引导

### D3. 测试（2 个）

- `test_profile_init_creates_default`
- `test_profile_set_updates_fields`

---

## Part E：Agent 主观能动性 — Skill 文档 Agent Behavior 段落

> **这部分全是文档改动，不写代码。** 在每个 SKILL.md 里加 "Agent Behavior" 段落，教 Agent 什么时候该主动想、主动做。

### E1. 总 Skill (openmy/SKILL.md) — 加三段

**a) First-Time Setup Flow：**
```markdown
## First-Time Setup Flow

If this is the user's first time using OpenMy (no data/ directory, no profile.json):

1. → openmy-profile-init: set up user name, language, timezone
2. → openmy-vocab-init: initialize personal vocabulary; mine conversation history for frequent proper nouns
3. → Help user locate their first audio file
4. → openmy-day-run: process the first recording
5. → Review results with user; suggest corrections for any transcription errors
6. → openmy-vocab-init: now that you've seen real transcription output, add more terms
```

**b) Typical Daily Workflow：**
```markdown
## Typical Daily Workflow

1. User records throughout the day (DJI Mic, phone, meeting app, etc.)
2. End of day: feed audio → day.run
3. Review the daily briefing → day.view
4. Fix transcription errors → correction.apply
5. Check overall status periodically → status.review / context.read

Your job as the Agent is to make this cycle as frictionless as possible.
When in doubt about what the user needs, start with status.review.
```

**c) Proactive Patterns：**
```markdown
## Proactive Patterns (Always Apply)

- If you notice words that look like transcription errors → suggest corrections
- If open loops are piling up → ask the user which ones to close
- If several days have no data → ask if the user has recordings to process
- If the user mentions a proper noun you haven't seen before → suggest adding it to vocab
```

### E2. openmy-day-run — Agent Behavior After Success

```markdown
## Agent Behavior After Successful Run

1. **Read the results**: call day.get to see what was produced
2. **Quality check the transcript**: scan for potential transcription errors
   - Proper nouns that look misspelled (e.g., "Cload" → "Claude"?)
   - Technical terms that seem garbled
   - Names appearing in inconsistent spellings
3. **Suggest corrections**: if you spot errors, ask the user:
   "I noticed these might be transcription errors — want me to fix them?"
   → route to openmy-correction-apply for each confirmed fix
4. **Check vocab status**: if corrections.json doesn't exist, suggest vocab.init
5. **Summarize highlights**: tell the user what their day looked like:
   "Today you mainly discussed X and Y. You have N new open items."
6. **Check for skipped steps**: if any step has skip_reason, explain why and offer help
   - "Distillation was skipped because no LLM key is configured. Want to set one up?"
```

### E3. openmy-day-run — Audio Input Guide

```markdown
## Audio Input Guide

OpenMy accepts any audio file — it is NOT tied to any specific hardware.
Supported formats: .wav, .mp3, .m4a, .ogg, .flac, or any ffmpeg-compatible format.

### How did you record?

Help the user based on their recording method:

| Method | Typical location | Notes |
|--------|-----------------|-------|
| Wireless mic (DJI, Rode, etc.) | USB drive or SD card | May have timestamp in filename |
| Phone voice memo | AirDrop → ~/Downloads/, or shared via messaging app | User provides date |
| Meeting recording (Zoom, Teams) | ~/Documents/ or app-specific folder | Usually named with date |
| Screen recorder | ~/Desktop/ or ~/Movies/ | Check file creation date |
| Any other source | Wherever the user saved it | Just need the file path |

### Date handling

- The `--date` parameter is always required by the CLI
- **Most audio files carry a timestamp** in their metadata (creation date). The Agent should:
  1. Check the file's metadata or filename for a date
  2. Suggest it to the user: "This file looks like it was recorded on April 11. Is that right?"
  3. Only use the date after user confirmation
- If the file has **no discernible date** (no metadata, no filename pattern), the Agent must:
  1. Ask the user: "When was this recorded?"
  2. If the user doesn't know, warn them clearly: "Without a date, OpenMy can still transcribe and process the audio, but it won't be able to place it on your timeline or correlate it with other days' data."
  3. As a fallback, use today's date with user's explicit consent
- Multiple audio files for the same day are supported: `--audio file1.wav file2.wav`

### If the user has no audio file yet

- Suggest: "You can record using your phone's voice memo app, any wireless mic, or even your laptop's built-in microphone."
- OpenMy works with any audio — the quality of transcription depends on audio quality, not the device.
```

### E4. openmy-startup-context — Proactive Discovery

```markdown
## Agent Behavior After Reading Context

Don't just report numbers — think about what they mean:

1. **Stale open loops**: if any loop has been open > 3 days, ask "Is [task] still active, or should we close it?"
2. **Unprocessed days**: if recent dates have no data, ask "Do you have recordings for [date]?"
3. **Continuity**: mention what the user was focused on last: "Last time you were mainly working on [project]. Continue?"
4. **Onboarding check**: if profile or vocab is not initialized, trigger the onboarding flow
```

### E5. openmy-status-review — Actionable Recommendations

```markdown
## Agent Behavior After Status Review

Don't just show the status — make recommendations:

1. **Unprocessed recordings**: "You have audio for [dates] that hasn't been processed. Want me to run them?"
2. **Expiring tasks**: "These 3 items are about to expire. Review them now?"
3. **Partial processing**: "Day X was only partially processed. Want me to re-run it?"
4. **Suggest next action**: always end with a clear recommendation:
   "I'd suggest we process yesterday's recording first, then review your open tasks."
```

### E6. openmy-context-read — Data Navigation Guide + Pattern Recognition

```markdown
## How to Navigate the Context Snapshot

The `data.snapshot` from context.get is a large nested object. Here's what to look at for each user question:

### "What am I working on?"
→ `snapshot.rolling_context.project_cards` — active projects sorted by last_touched_at
→ Present top 2-3 projects with their recent snippets

### "What's pending / what are my open items?"
→ `snapshot.rolling_context.open_loops` — tasks, commitments, delegations
→ Highlight loops with status="stale" or priority="high"

### "What happened recently?"
→ `snapshot.rolling_context.recent_events` — timestamped events
→ `snapshot.core_memory.recent_changes` — what changed in the last few days

### "What decisions have I made?"
→ `snapshot.rolling_context.decisions` — decisions with topic and date

### "Who do I talk to?"
→ `snapshot.rolling_context.entity_rollups` — people/entities with interaction frequency

### "What's my current state?"
→ `snapshot.realtime_context.today_state` — mode, energy, focus areas
→ `snapshot.status_line` — the one-line summary

### Presentation priority
1. Lead with `status_line` (one sentence)
2. Mention top 2-3 projects from `project_cards` (by recency)
3. Highlight open loops that are stale or high-priority
4. Only dive deeper if the user asks follow-up questions

## Cross-Day Pattern Recognition

When presenting context, look for patterns:

- Projects mentioned across 3+ days → "This is your core focus this week"
- Open loops that keep appearing → "This has been open for N days, might need attention"
- People who appear frequently → "You interact with [person] almost daily"
- Declining activity → "You haven't recorded anything in 3 days — everything okay?"
```

### E7. openmy-day-view — How to Present Results + Proactive Error Detection

```markdown
## Agent Behavior After Viewing Results

### Presenting data to the user ("What was I doing on April 8?")

When the user asks about a specific day, call day.get and translate the JSON into a human-friendly answer:

1. **Lead with the one-line summary**: use `data.briefing.summary` if available
2. **Key events**: list `data.meta.events` — what happened, with whom, when
3. **Decisions made**: list `data.meta.decisions` — what the user decided
4. **Open items from that day**: list `data.meta.intents` where kind=todo/commitment
5. **Scene highlights**: if the user wants more detail, summarize notable scenes from `data.scenes.scenes`

Example answer structure:
> "On April 8, you mainly worked on OpenMy and had a call with your partner about travel plans. 
> Key decisions: switched STT provider to Gemini. 
> Open items: need to finalize the README, set up CI pipeline."

### If the day has no data

- Don't just say "no data found" — ask: "I don't have any recordings for April 8. Do you have audio from that day? I can process it for you."
- Route to openmy-day-run if user provides audio

### If the day has incomplete data

- Has transcript but no briefing → "April 8 has been transcribed but not fully analyzed. Want me to run the full pipeline?"
- Has scenes but no extraction → explain what's missing and offer to re-run

### Proactive quality checks

1. **Scan for transcription quality**: flag words that look like STT errors
2. **Offer corrections**: "I noticed a few potential errors in the transcript. Want me to fix them?"
3. **Cross-reference**: compare with recent context — "You mentioned [project] again, that's 4 days in a row"
```

### E8. openmy-vocab-init — Full Agent Behavior

```markdown
## Agent Behavior After Initialization

1. **Ask the user about their context:**
   - "What tools, apps, or services do you use daily?" (Notion, Figma, Claude, etc.)
   - "Any people you mention often?" (names, nicknames, pets)
   - "Any projects or brands?" (OpenMy 等)
   - "Technical terms in your field?" (LLM, RAG, fine-tuning)

2. **Mine your conversation history:**
   - Review past conversations with the user
   - Identify proper nouns, brand names, and technical terms
   - These are the words STT is most likely to mangle

3. **Present candidates:**
   - "I found these terms from our conversations. Want to add them to your vocab?"
   - Let the user confirm, edit, or skip each one

4. **For each confirmed term:**
   - Ask: "How might speech-to-text misspell this?" (e.g., Claude → Cload, Klaud)
   - Call: correction.apply --op typo --arg "wrong" --arg "right" --json

5. **Don't skip user confirmation — always ask before writing**
```

### E9. openmy-correction-apply — Operation Reference Table

```markdown
## Available Operations

| --op | Purpose | --arg format | Needs --date? | Example |
|------|---------|-------------|:---:|--------|
| close-loop | Mark a task as done/abandoned | "task title" | No | --op close-loop --arg "Finalize README" |
| typo | Fix a transcription error | "wrong" "right" | Yes | --op typo --arg "Cload" --arg "Claude" --date 2026-04-08 |
| reject-decision | Remove a false/irrelevant decision | "decision text" | No | --op reject-decision --arg "要退休了" |
| merge-project | Merge duplicate project names | "source" "target" | No | --op merge-project --arg "openmy" --arg "OpenMy" |

When the user says something like "this is wrong" or "I already did that", figure out which operation to use and fill in the correct args.
```

### E10. openmy-status-review — How to Read Items

```markdown
## How to Read status.get Items

Each item in `data.items` represents one day:
- `date`: the date string (YYYY-MM-DD)
- `has_transcript`: raw transcript exists
- `has_scenes`: scene segmentation done  
- `has_briefing`: full processing complete
- `scene_count`: number of scenes

Categorize days for the user:
- ✅ **Complete**: has_briefing = true → fully processed
- ⚠️ **Partial**: has_transcript or has_scenes, but no briefing → needs re-run
- ❌ **Empty**: nothing exists → needs audio + day.run

Present as: "You have 7 fully processed days, 1 partially processed, and 1 with no data."
Then offer: "Want me to finish processing the partial day?"
```

---

## 翻译原则（全局）

- 技术术语保留原样
- Skill 名和 CLI 命令不变
- 翻译简洁技术范

---

## 测试计划

1. **Part A** — 2 个测试
2. **Part B** — 全量测试不回归
3. **Part C** — 验证 context.query
4. **Part D** — 2 个测试 + 验证 profile.get/set
5. **Part E** — 人工审查 Skill 文档质量（Agent Behavior 段落是否完整、自洽、可操作）
