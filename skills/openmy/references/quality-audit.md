# Pipeline 产出质量审核标准

本文档定义了 `day.run` 完成后的数据质量审核标准。
每次 pipeline 完成后，执行审核的 agent 必须按此标准逐项检查，不得跳过。

## 审核触发条件

- `day.run` 或 `quick-start` 返回 exit code 0 或 partial success
- agent 代做蒸馏/提取后（distill.submit / extract.core.submit）
- 手动要求审核时

## 审核项

### 1. work_sessions 合理性

| 检查 | 通过条件 |
|------|---------|
| 单个 app 时长 | ≤ 4 小时（除非用户确认是全天使用的 app） |
| 后台进程 | Electron / loginwindow / screencaptureui 不应超过 1 小时 |
| 总 app 数 | ≤ 10 个有意义的 app |
| 数值格式 | 必须是 "约X小时Y分钟" 或 "约X分钟"，不得出现 "0分钟" |

**红线**：任何 app > 8 小时 → 必须报告异常。

### 2. scene 质量拦截

| 检查 | 通过条件 |
|------|---------|
| `[无人声]` | 必须被标记为 `no_speech`，`usable_for_downstream: false` |
| `[无法识别]` 占比 ≥ 40% | 必须被标记为 `low_quality_garbled` |
| 歌词重复模式 | 4 字 n-gram ≥ 4 次 → 标记 `music_lyrics` |
| 被拦截的 scene | summary 必须为空字符串 |

**红线**：`[无人声]` 有非空 summary → 必须报告。

### 3. distill 摘要质量

| 检查 | 通过条件 |
|------|---------|
| 摘要长度 | 30-80 字（中文） |
| 主语 | 必须用 "我"，不用第三人称 |
| 过度发挥 | 短文本（< 50 字）的 summary 不得超过原文 50% 长度 |
| 幻觉内容 | 不得出现原文中没有的具体地名、人名、数字 |
| 垃圾美化 | 不得把噪音/乱码描述成正常活动 |

**红线**：乱码原文 → 漂亮 summary → 必须报告为幻觉。

### 4. decisions 与 key_events 去重

| 检查 | 通过条件 |
|------|---------|
| 交集 | decisions 和 key_events 无文本重复 |
| decisions 来源 | 必须来自 meta.json 的 `intents[kind=decision]`，不是关键词分桶 |
| decisions 数量 | ≤ 5 条（超过说明分类可能有问题） |

### 5. people_interaction_map

| 检查 | 通过条件 |
|------|---------|
| 存在性 | 如果有多人对话 scene → map 不得为空 |
| 数据来源 | 优先取 meta.json 的 `role_hints`（confidence ≥ 0.7） |
| 排除 | "自己" / "未确定" 不得出现在 map 中 |

### 6. meta.json 回灌

| 检查 | 通过条件 |
|------|---------|
| todos_open | 如果 meta.json 有 `intents[kind=action_item]` → briefing.todos_open 非空 |
| insights | 如果 meta.json 有 `facts` → briefing.insights 非空 |
| decisions | 如果 meta.json 有 `intents[kind=decision]` → briefing.decisions 非空 |

**红线**：meta.json 有结构化数据但 briefing 对应字段为空 → 回灌失败。

### 7. 整体完整性

| 检查 | 通过条件 |
|------|---------|
| daily_briefing.json | 存在且可解析 |
| meta.json | 存在且可解析 |
| scenes.json | 存在，scene 数 > 0 |
| time_blocks | 至少 1 个非空 time_block |
| narrative_summary | 非空 |

## 审核输出格式

审核结果必须包含：

```
审核日期: YYYY-MM-DD
状态: ✅ 通过 / ⚠️ 有警告 / ❌ 有红线问题

项目检查:
  1. work_sessions: ✅ / ⚠️ 具体问题
  2. scene 质量: ✅ / ⚠️ 具体问题
  3. distill 质量: ✅ / ⚠️ 具体问题
  4. decisions 去重: ✅ / ⚠️ 具体问题
  5. people: ✅ / ⚠️ 具体问题
  6. meta 回灌: ✅ / ⚠️ 具体问题
  7. 完整性: ✅ / ⚠️ 具体问题

红线问题: [列出所有红线]
```

## 审核规则

1. **红线问题必须修**：任何红线触发 → agent 不得说"已完成"，必须先修再报告
2. **警告要报告**：可以先不修，但必须告诉用户
3. **不得美化结果**：如果 13 项验收只过了 8 项，就说 8/13，不说"基本通过"
4. **审核不是可选的**：pipeline 跑完不审核 = 没完成任务
