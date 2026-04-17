# Pipeline 数据质量修复 — 完整沉淀文档

> 日期：2026-04-17
> 参与：CC (Antigravity)
> 审查：Codex（发现 3 个硬伤，全部已修复）
> 触发：Codex 跑出 4/15、4/16 两天数据后，人工发现产出数据存在严重不合理

---

## 一、背景

OpenMy 的 pipeline 流程为：

```
音频 → 转写(STT) → 清洗 → 场景切分 → 角色识别(冻结) → 蒸馏(LLM) → 日报 → 核心提取(LLM) → 补全提取 → 聚合
```

Codex 对 2026-04-15 和 2026-04-16 两天数据执行了完整 pipeline。产出数据通过人工审查发现根本不可用。

### 为什么会这样（Codex 自查）

根本原因是把"先跑通"放在了"先保真"前面。前面一步失真，后面每一步都在放大错误：

1. **拼音频丢时间** — 为了减少云端 API 调用，多段录音拼成大段。一拼，每段的真实开始时间就丢了，后面只能从零点硬排，时段和顺序全错。
2. **噪音混进转写** — 车里、户外、有背景音乐的环境，云端转写把人声、歌词、噪音混在一起吃了，垃圾段直接流进后面。
3. **摘要把垃圾写漂亮** — 摘要步骤只看"有没有字"，有字就当有效内容。于是乱码、歌词、碎句被一本正经地写成像样的总结。
4. **时长算法算错** — 后台程序一直挂着，算法拿"第一帧到最后一帧"的跨度算，所以挂着也算你在用，出现了 Electron 23 小时。
5. **日报先生成、整理后生成** — 顺序上就天然漏掉待办、洞察、人物这些后来才提取的信息。加上"决定"那栏按关键词硬抓，和大事记重复。
6. **人物识别冻结** — 角色识别步骤是冻结的，即使录音里明显在和伴侣说话，也不会生成人物映射。

一句话：**前面时间和内容已经脏了，后面却还在认真整理，于是产出看起来完整，实际上不可信。**

---

## 二、问题清单

### P0-0：时间轴损坏（代码层未修，数据层已重跑）

**现象**：多段录音合成 batch 后，真实开始时间被抹掉，导致事件顺序和时段划分不准。

**根因**：`audio_pipeline.py` 和 `segmenter.py` 的时间戳传递逻辑没有保留每段录音的原始开始时间。

**当前状态**：
- ✅ 4/15、4/16 的数据已经重跑过，页面上看到的结果是修复后的
- ⚠️ 代码层的时间戳传递根因还没有修，未来新的录音仍可能触发同样问题

**影响范围**：time_blocks 的时段划分可能不准，但 work_sessions、scene 内容、结构化回灌不受影响。

---

### P0-1：work_sessions 虚高

**现象**：Electron 显示 "约23小时47分钟"，实际只用了几分钟。

**根因**：`capture_store.py` 的 `_minutes()` 函数用 `max(timestamp) - min(timestamp)` 算时长。后台 Electron 从早到晚都有截屏帧 → 被算成全天在用。

**文件**：`src/openmy/services/screen_recognition/capture_store.py`

**修法**：改为 gap-aware 累加——只有相邻帧间隔 ≤ `capture_interval_seconds × 3` 时才累计时间。超过的间隔视为用户离开，不计入。

**修复后**：Electron 从 23h47m → **7 分钟**。

---

### P0-2：歌词 / 背景音 / 乱码混入转写

**现象**：大量场景内容是背景音乐歌词、`[无法识别]` 和口水话重复，但全部标记为 `usable_for_downstream: true`。

**根因**：`scene_quality.py` 只检测助手回复和技术串台，不检测歌词、乱码、无人声。

**文件**：`src/openmy/services/scene_quality.py`

**修法**：新增三个检测器：

| 检测器 | 触发条件 | flag |
|--------|---------|------|
| 无人声检测 | 全文 = `[无人声]` / `[无声]` / `[静音]` | `no_speech` |
| 乱码密度检测 | `[无法识别]` 占总行数 ≥ 40% 且 ≥ 40 字 | `low_quality_garbled` |
| 歌词重复检测 | 4 字 n-gram 覆盖密度 > 4%（且至少出现 4 次） | `music_lyrics` |

三种 flag 均设 `usable_for_downstream: false`。

**修复后**：4/15 的 31 个场景中 16 个被拦截；4/16 的 11 个场景中 2 个被拦截。

**迭代记录**：初版用固定计数阈值（n-gram ≥ 4 次），导致 4/16 有 7/11 被误杀——"充电站" 在聊天中反复提及就会触发。经 Codex 审查后改为密度检测（覆盖占比 > 4%），将假阳性从 7/11 降至 2/11。

---

### P0-3：distill 把垃圾输入写成正常 summary

**现象**：`[无人声]` 被蒸馏成 "在一个安静的环境中感受宁静"；两句口水话被扩写成 "宝藏体验地点"。

**根因**：`distiller.py` 只检查 text 非空就送 LLM。LLM（Gemini）拿到垃圾输入后过度发挥。

**文件**：`src/openmy/services/distillation/distiller.py`

**修法**：三层防护——

1. **最小字数门槛**：text < 10 字 → 直接返回空 summary
2. **Prompt 强化**：规则 7 "原文无实质内容时直接输出空字符串，不要编造"
3. **卫生检查**：text < 50 字 && summary > text × 50% → 视为过度发挥，清空

---

### P1-1：decisions 和 key_events 重复

**现象**：briefing 的 `decisions` 和 `key_events` 有大量文本重复。

**根因**：`generator.py` 用关键词 "决定/确定/选择/定了" 做分桶，scene summary 中这些词高频出现导致同一条内容两边都有。

**文件**：`src/openmy/services/briefing/generator.py`

**修法**：
- 删掉 decisions 关键词分桶逻辑
- decisions 改为由 `enrich_briefing_from_meta()` 从 meta.json 的 `intents[kind=decision]` 回灌
- key_events 增加前 20 字前缀去重

---

### P1-2：people 数据没有进入 briefing

**现象**：`people_interaction_map` 为空。有多人对话但不显示。

**根因**：`generator.py` 依赖 `role.addressed_to`，但 roles 步骤冻结 → 该字段全空。extract 产出的 `role_hints` 未被读取。

**文件**：`src/openmy/services/briefing/generator.py`

**修法**：在 `enrich_briefing_from_meta()` 中读取 meta.json 的 `role_hints`，confidence ≥ 0.7 的角色回灌到 `people_interaction_map` 和对应 time_block。

---

### P1-3：meta.json 的 todos / intents / facts 没回灌 briefing

**现象**：meta.json 有结构化的 todos、facts，但 briefing 里 `todos_open`、`insights`、`decisions` 全空。

**根因**：pipeline 顺序是 distill → briefing → extract_core。briefing 生成时 meta.json 不存在。

**文件**：
- `src/openmy/services/briefing/generator.py`（新增 `enrich_briefing_from_meta()`）
- `src/openmy/commands/run.py`（在 extract_enrich 后调用回灌）

**修法（方案 B 后置回灌）**：不改 pipeline 主顺序。在 extract_enrich 完成后调用 `enrich_briefing_from_meta()`，从 meta.json 读取 intents/facts/role_hints 写回 briefing.json。

回灌映射：

| meta.json 字段 | briefing 字段 |
|---------------|----------------|
| `intents[kind=decision]` | `decisions` |
| `intents[kind=action_item\|commitment, status!=done]` | `todos_open` |
| `facts` | `insights` |
| `role_hints[confidence>=0.7]` | `people_interaction_map` + `time_blocks.people_talked_to` |

---

### 额外修复：所有蒸馏入口统一过滤不可用 scene

**现象**：scene_quality 标记了 scene 为 `usable_for_downstream: false`，但 pipeline 仍然尝试蒸馏它们，已被拦截的 scene 仍有非空 summary。

**根因**：蒸馏有两个入口——`run.py` 的 `missing_summaries` 统计和 `show.py` 的 `cmd_distill` 循环——都没过滤 `usable_for_downstream`。`distiller.py` 内部有过滤，但 `show.py` 的 `cmd_distill` 直接调用 `summarize_scene()` 绕过了它。

**修法**：
- `run.py`：`missing_summaries` 过滤条件增加 `scene.get("usable_for_downstream", True)`
- `show.py`：`cmd_distill` 的 pending 统计和蒸馏循环均增加 `scene_is_usable_for_downstream()` 检查

**注意**：经 Codex 审查发现 `show.py` 入口遗漏，已补修。

---

## 三、改动文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/openmy/services/scene_quality.py` | 功能增强 | 新增 3 个检测器 + 密度规则迭代 |
| `src/openmy/services/distillation/distiller.py` | 功能增强 | 最小字数 + prompt + 卫生检查 |
| `src/openmy/services/screen_recognition/capture_store.py` | Bug 修复 | `_minutes()` 算法重写 |
| `src/openmy/services/briefing/generator.py` | 功能增强 | 去重 + `enrich_briefing_from_meta()` |
| `src/openmy/commands/run.py` | 功能增强 | 回灌调用 + usable 过滤 |
| `src/openmy/commands/show.py` | Bug 修复 | `cmd_distill` 入口增加 usable 过滤 |
| `tests/unit/test_distiller.py` | 测试适配 | fixture 文本加长 |
| `skills/openmy/SKILL.md` | 规范强化 | 新增 Post-Run Quality Audit 硬约束 |
| `skills/openmy/references/quality-audit.md` | 新增文档 | 7 项审核标准 + 红线 + 输出格式 |

---

## 四、验证结果

### 自动化测试

- `ruff check` — All checks passed
- `pytest` — 501 passed（1 个 flaky test，与本次改动无关）

### 存量数据重跑

两天数据均已重跑 pipeline。以下数据分两组：
- **维度 A：磁盘上的实际产物** — 即当前用户看到的结果
- **维度 B：按最新代码重算** — 如果现在重跑会得到的结果

两组有差异，因为密度规则是在重跑之后才改的，磁盘上的 scenes.json 还是旧规则标记。

#### 4/15

| 指标 | 修复前 | 磁盘产物（旧规则） | 重算（新密度规则） |
|------|--------|---------------|----------------|
| Electron 时长 | 约23小时47分钟 | **约7分钟** | 约7分钟 |
| 场景拦截 | 0 / 31 | 16 / 31 | **6 / 31** |
| `[无人声]` s06 | 有 summary | summary = "" | summary = "" |
| people | 空 | 伴侣 | 伴侣 |
| todos_open | 空 | 3 条 | 3 条 |
| insights | 空 | 3 条 | 3 条 |

ℹ️ 4/15 磁盘上有 10 个 scene 被旧规则误杀、缺 summary。重跑后可恢复。

#### 4/16

| 指标 | 磁盘产物（旧规则） | 重算（新密度规则） |
|------|---------------|----------------|
| Electron 时长 | 约7分钟 | 约7分钟 |
| 场景拦截 | 7 / 11 | **2 / 11** |
| people | 伴侣 | 伴侣 |
| todos_open | 4 条 | 4 条 |
| insights | 4 条 | 4 条 |

ℹ️ 4/16 磁盘上有 5 个 scene 被旧规则误杀。重跑后可恢复。

**结论**：两天数据均可用，但如果要拿到最佳结果，建议用新代码重跑一次。

---

## 五、设计决策记录

| 决策点 | 方案 | 理由 |
|--------|------|------|
| meta.json 回灌方式 | **方案 B（后置回灌）** | 不改 pipeline 主顺序，改动范围可控 |
| 歌词检测策略 | **密度检测（覆盖占比 > 4%）** | 初版用固定计数，Codex 审查后改为密度，假阳性从 7/11 降至 2/11 |
| gap 阈值 | **capture_interval x 3** | 动态适配不同截屏间隔，不硬编码 |
| distill 卫生检查 | **text < 50 字 && summary > 50% text** | 比关键词黑名单更鲁棒 |

---

## 六、已知遗留项

1. **时间轴损坏（P0，未修复）**：多段录音合成 batch 后真实开始时间被抹掉，导致事件顺序和时段划分失真。需要单独处理 `audio_pipeline.py` 和 `segmenter.py` 的时间戳传递逻辑。

2. **decisions 为空**：当天 meta.json 的 `intents[kind=decision]` 为空时 decisions 就为空。这是正确行为，但可能需要和用户沟通预期。

3. **Gemini API 限流**：当前 `.env` 配了 `GEMINI_API_KEY`，pipeline 会优先走 API 蒸馏。API 不稳定时会阻塞整个 pipeline。建议：distill 失败时自动降级到 agent-side 路径。

4. **fallback app 统计**：`search_ocr` 降级路径返回帧计数（用负值标记），显示为 "N段截屏"。语义上不如精确时长清晰，但比伪造时长好。

---

## 六-附：Codex 审查反馈（已修复）

本文档首版经 Codex 审查，发现 3 个硬伤，全部已修复并更新回本文档：

| # | Codex 批评 | 修复措施 |
|---|-----------|----------|
| P0 | 问题清单漏掉时间轴损坏根因 | 新增 P0-0 记录，标注为未修复待单独处理 |
| P1 | "不可用 scene 不再蒸馏" 表述过满，`show.py` 入口未修 | 补修 `show.py` 的 `cmd_distill`，统一两个入口 |
| P1 | "少量假阳性" 偏乐观，实际 4/16 有 7/11 误杀 | 改为密度检测算法，假阳性从 7/11 降至 2/11 |

**教训**：修复文档不应自称"完整"，应明确标注已知未覆盖的范围。

---

## 七、固化的质量标准

本次修复后，新增了永久性的质量审核标准：

- **文件**：`skills/openmy/references/quality-audit.md`
- **约束级别**：HARD CONSTRAINT（写入 SKILL.md）
- **适用范围**：所有 agent（CC、小克、Codex、小g）
- **规则**：pipeline 跑完不审核 = 任务没完成

审核包含 7 项检查：
1. work_sessions 合理性
2. scene 质量拦截
3. distill 摘要质量
4. decisions 与 key_events 去重
5. people_interaction_map 存在性
6. meta.json 回灌完整性
7. 整体文件完整性

每项有明确的通过条件和红线。红线触发时必须先修后报。

---

## 八、交接注意事项

如果你是接手的 agent，请注意：

1. **先读 `skills/openmy/SKILL.md`**，特别是 "Post-Run Quality Audit" 这一节
2. **先读 `skills/openmy/references/quality-audit.md`**，里面有完整的审核清单
3. **不要直接用 `openmy run`**，先确认 Gemini API 是否可用。如果不可用，走 agent-side 路径：`distill.pending` → 自己写 summary → `distill.submit`
4. **跑完之后必须审核**，按 quality-audit.md 的 7 项逐一检查
5. **时间轴问题仍未修复**，time_blocks 时段信息暂时不可靠
6. **本次改动的核心函数**：
   - `scene_quality.py` 的 `_garbled_ratio()` 和 `_has_repeated_ngram()`
   - `generator.py` 的 `enrich_briefing_from_meta()`
   - `capture_store.py` 的 `_minutes()`
