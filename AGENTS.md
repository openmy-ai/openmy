# OpenMy — 小克 (Claude Code) 工作交接单

> 最后更新：2026-04-09 by CC (Antigravity)

## 团队命名

| 代号 | 身份 | actor | 日志文件 | 角色 |
|------|------|-------|---------|------|
| **CC** | Antigravity | `cc` | `cc.jsonl` | 计划·审查·文案·前端 |
| **小克** | Claude Code | `xk` | `cc.jsonl`（共用） | 编码主力 |
| **小 g** | Gemini CLI | `g` | `g.jsonl` | 轻量杂活 |
| **Codex** | Codex | `codex` | `cc.jsonl`（共用） | 批量执行 |

## Obsidian 写入规范（必读）

### Vault 路径
```
/Users/zhousefu/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault/
```

### 事件流写入

**路径**：`系统/事件流/{YYYY-MM-DD}/cc.jsonl`（小克和 CC 共用同一个文件）

**格式**（每行一条 JSON，echo >> 追加）：
```json
{"time":"2026-04-09T23:00:00+08:00","actor":"xk","project":"OpenMy","type":"commit","summary":"一句话描述"}
```

**字段说明**：
| 字段 | 说明 |
|------|------|
| `time` | ISO 8601 带时区，北京时间 `+08:00` |
| `actor` | 小克写 `xk`，CC 写 `cc`，小 g 写 `g` |
| `project` | 项目名，如 `OpenMy`、`系统`、`个人IP` |
| `type` | `commit` / `fix` / `review` / `decision` / `milestone` / `handoff` / `test` |
| `summary` | 一句话，大白话，不超过 100 字 |

**写入命令模板**：
```bash
VAULT="/Users/zhousefu/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault"
echo '{"time":"ISO时间","actor":"xk","project":"项目名","type":"类型","summary":"一句话"}' >> "$VAULT/系统/事件流/YYYY-MM-DD/cc.jsonl"
```

### 什么时候写

| 触发 | 写什么 | 写到哪 |
|------|--------|--------|
| 完成 commit | type=commit，写 hash + 一句话 | 事件流 |
| 修 bug | type=fix | 事件流 |
| 审查代码 | type=review | 事件流 |
| 做决策 | type=decision | 事件流 |
| 完成/暂停 | 更新封口状态 | `项目/{项目名}/状态.md` |
| 配置变更 | 先 git commit 再改 | 事件流 + git |

### 审查铁律（CC 审查小克代码时执行）

> **默认立场：找问题，不找亮点。** 🔴=0 且 🟡<3 = 审查不够深。

详细清单见 `系统/CC-Boot.md` 的「代码审查铁律」章节。

## 当前架构状态

### 管线概览

```
录音 → 转写(Gemini API) → 清洗(规则引擎) → 场景切分 → 蒸馏(API) → 提取(API) → 结构化 JSON
```

### 模型与配置

所有大模型参数集中在 `src/openmy/config.py`，开源用户只改这一个文件：

| 参数 | 值 | 说明 |
|------|-----|------|
| `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` | 全局统一模型 |
| `EXTRACT_TEMPERATURE` | 0.2 | 提取用 |
| `EXTRACT_THINKING_LEVEL` | `high` | 提取需深度推理 |
| `DISTILL_TEMPERATURE` | 0.2 | 蒸馏用 |
| `DISTILL_THINKING_LEVEL` | `medium` | 蒸馏中等推理 |
| `AUDIO_PIPELINE_TIMEOUT` | 1800 | 音频管线超时(秒) |

### 清洗架构（规则引擎，不调 API）

`cleaner.py` 已从 Gemini API 语义清洗改回纯规则引擎：
- Step 1-2: 删 AI 转写前缀 + [音乐] 标记
- Step 3-4: 删废词行 + 句中废词清理
- Step 5-7: 去重复行 + 合并碎句 + 合并空行
- Step 8-9: 去首尾空行 + 长段切分
- Step 10: `corrections.json` 确定性纠错

设计原则：**不删脏话**（真实语气证据） | **不加粗** | **不调 API**

### 提取架构（Gemini API + 结构化输出）

`extractor.py` 使用官方推荐的 `response_json_schema` 强制约束输出格式：
- 输出 schema 定义在 `EXTRACTION_SCHEMA` 字典
- 所有字段含 enum 约束（kind、status、confidence_label 等）
- 支持 thinking_config 深度推理

---

## 2026-04-09 变更清单（6 个 commit）

### 1. `92c0dcf` — 全部统一用 Gemini API
- `cleaner.py` 从 Gemini CLI subprocess 改成 google-genai SDK
- 消除了 `prepare_isolated_home` 等 CLI 凭证隔离逻辑

### 2. `2baf4f1` — 提取模块加 response_json_schema
- 按 Google 官方推荐传 JSON Schema，模型强制按结构输出
- 不可能缺字段或类型错

### 3. `b3675ef` — 全模块加 thinking_config
- 提取=high，蒸馏=medium，清洗=low（后来清洗改为规则引擎）

### 4. `3064ad2` — 所有大模型配置集中到 config.py
- 消除了 cleaner/extractor/distiller/audio_pipeline 中的硬编码
- temperature、thinking_level、timeout 全部从 config 引用

### 5. `c169e92` — 清洗改为规则引擎
- 恢复旧版正则规则（删废词、AI前缀、重复行、碎句合并）
- 去掉脏话过滤和关键词加粗
- 去掉 Gemini API 调用
- 效果：12字→79字，零成本秒完成

---

## 测试状态

- 122 个单元测试全部通过
- 真实管线测试（2026-04-08 数据）：清洗→场景切分→提取 全流程跑通
- Gemini API (`gemini-3.1-flash-lite-preview`) 实测可用

## 关键文件

| 文件 | 职责 |
|------|------|
| `src/openmy/config.py` | 全局配置（改这一个文件就够） |
| `src/openmy/services/cleaning/cleaner.py` | 规则引擎清洗 |
| `src/openmy/services/extraction/extractor.py` | 结构化提取（API + JSON Schema） |
| `src/openmy/services/distillation/distiller.py` | 场景蒸馏（API） |
| `src/openmy/resources/corrections.json` | 音近字纠错词典 |
| `tests/unit/test_clean.py` | 清洗规则测试 |
| `tests/unit/test_extractor.py` | 提取测试 |

## 待处理项

- [ ] GPT Pro 审视清洗规则后可能有优化建议
- [ ] 观察 API 调用频率是否触及 rate limits
- [ ] 考虑转写环节也从 CLI 迁移到 API（Files API 上传音频）
