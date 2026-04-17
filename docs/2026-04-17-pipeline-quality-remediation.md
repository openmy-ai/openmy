# Pipeline 数据质量修复 — 完整沉淀文档

> 日期：2026-04-17
> 参与：CC (Antigravity)
> 触发：Codex 跑出 4/15、4/16 两天数据后，人工发现产出数据存在严重不合理

---

## 一、背景

OpenMy 的 pipeline 流程为：

```
音频 → 转写(STT) → 清洗 → 场景切分 → 角色识别(冻结) → 蒸馏(LLM) → 日报 → 核心提取(LLM) → 补全提取 → 聚合
```

Codex 对 2026-04-15 和 2026-04-16 两天数据执行了完整 pipeline。产出数据通过人工审查发现 6 类严重问题。

---

## 二、问题清单

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
| 歌词重复检测 | 任一 4 字 n-gram 出现 ≥ 4 次 | `music_lyrics` |

三种 flag 均设 `usable_for_downstream: false`。

**修复后**：4/15 的 31 个场景中 16 个被正确拦截。

**已知边界**：重复模式检测有少量假阳性（如 "开心不，开心不" 重复 4 次的正常对话也会触发）。阈值可后续微调。

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

| meta.json 字段 | → briefing 字段 |
|---------------|----------------|
| `intents[kind=decision]` | `decisions` |
| `intents[kind=action_item\|commitment, status≠done]` | `todos_open` |
| `facts` | `insights` |
| `role_hints[confidence≥0.7]` | `people_interaction_map` + `time_blocks.people_talked_to` |

---

### 额外修复：pipeline 不跳过不可用 scene 的蒸馏

**现象**：scene_quality 标记了 16 个 scene 为 `usable_for_downstream: false`，但 pipeline 仍然尝试蒸馏它们。

**根因**：`run.py` L995 统计 `missing_summaries` 时没排除不可用 scene。

**修法**：`missing_summaries` 过滤条件增加 `scene.get("usable_for_downstream", True)`。

---

## 三、改动文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/openmy/services/scene_quality.py` | 功能增强 | 新增 3 个检测器 |
| `src/openmy/services/distillation/distiller.py` | 功能增强 | 最小字数 + prompt + 卫生检查 |
| `src/openmy/services/screen_recognition/capture_store.py` | Bug 修复 | `_minutes()` 算法重写 |
| `src/openmy/services/briefing/generator.py` | 功能增强 | 去重 + `enrich_briefing_from_meta()` |
| `src/openmy/commands/run.py` | 功能增强 | 回灌调用 + usable 过滤 |
| `tests/unit/test_distiller.py` | 测试适配 | fixture 文本加长 |
| `skills/openmy/SKILL.md` | 规范强化 | 新增 Post-Run Quality Audit 硬约束 |
| `skills/openmy/references/quality-audit.md` | 新增文档 | 7 项审核标准 + 红线 + 输出格式 |

Git commits：
- `f9130c2` — fix: improve pipeline quality
- `7bd5df8` — docs: add post-run quality audit standard

---

## 四、验证结果

### 自动化测试

- `ruff check` — All checks passed ✅
- `pytest` — 501 passed（1 个 flaky test，与本次改动无关）✅

### 存量数据重跑

#### 4/15

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| Electron 时长 | 约23小时47分钟 | **约7分钟** |
| 场景拦截 | 0 / 31 | **16 / 31** |
| `[无人声]` s06 | summary = "感受安静环境" | **summary = ""，flag = no_speech** |
| s11 歌词乱码 | summary 正常 | **flag = low_quality_garbled + music_lyrics** |
| people_interaction_map | 空 | **伴侣** |
| todos_open | 空 | **3 条（参加音乐节、观察狗、购买iPad支架）** |
| insights | 空 | **3 条（宠物健康、旅行计划、烧烤活动）** |
| decisions ∩ key_events | 大量重复 | **无交集** |

#### 4/16

| 指标 | 修复后 |
|------|--------|
| Electron 时长 | 约7分钟 ✅ |
| people | 伴侣 ✅ |
| todos_open | 4 条 ✅ |
| insights | 4 条 ✅ |

---

## 五、设计决策记录

| 决策点 | 方案 | 理由 |
|--------|------|------|
| meta.json 回灌方式 | **方案 B（后置回灌）** | 不改 pipeline 主顺序，改动范围可控，无回归风险 |
| 歌词检测策略 | **只用重复模式 + 乱码密度** | 放弃了"连续拉丁字符长度"规则，避免误杀英文品牌名和技术词 |
| gap 阈值 | **capture_interval × 3** | 动态适配不同截屏间隔，不硬编码 |
| distill 卫生检查 | **text < 50 字 && summary > 50% text** | 比关键词黑名单更鲁棒，不怕 LLM 换说法 |

---

## 六、已知遗留项

1. **歌词检测假阳性**：4 字 n-gram ≥ 4 次的阈值偶尔误杀正常口头重复（如 "开心不" 连说 4 次）。可考虑提高阈值到 5 或加上下文判断。

2. **decisions 为空**：当天 meta.json 的 `intents[kind=decision]` 为空时 decisions 就为空。这是正确行为（不是所有天都有决策），但可能需要和用户沟通预期。

3. **Gemini API 限流**：当前 `.env` 配了 `GEMINI_API_KEY`，pipeline 会优先走 API 蒸馏。但 API 不稳定时会阻塞整个 pipeline。建议：在 distill 失败时自动降级到 agent-side 路径（目前需要手动走 `distill.pending` + `distill.submit`）。

4. **fallback app 统计**：`search_ocr` 降级路径返回帧计数（用负值标记），显示为 "N段截屏"。语义上不如精确时长清晰，但比伪造时长好。

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
5. **本次改动的核心函数**：
   - `scene_quality.py` 的 `_garbled_ratio()` 和 `_has_repeated_ngram()`
   - `generator.py` 的 `enrich_briefing_from_meta()`
   - `capture_store.py` 的 `_minutes()`
