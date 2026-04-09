---
name: openmy
description: OpenMy 是自维护的个人上下文系统。信源是录音和 Screenpipe，前端给用户，CLI 给 Agent。这份文档定义产品是什么，不是怎么调命令。
---

# OpenMy — 自维护的个人上下文系统

> 核心定义：让 Agent 少猜一点。
> 不是笔记工具，不是日报生成器，是 Agent 的"用户认知层"。

## 第零铁律

**用户永远不碰终端。**

- CLI 是 Agent 的 API，不是给人用的
- 前端页面（`app/`）是用户唯一的界面
- 用户只通过自然语言对话和 Agent 交互，Agent 负责调用 CLI

## 产品是什么

OpenMy 是一个本地优先的个人上下文内核。它：

1. **自动采集** — 录音（DJI Mic，你说了什么）+ Screenpipe（你做了什么）
2. **自动理解** — 转写 → 清洗 → 场景切分 → 角色归因 → 蒸馏 → 提取 → 聚合
3. **自动维护** — active_context 跨日滚动更新，corrections 追加式修正
4. **Agent 消费** — 任何 Agent 启动时读 active_context，就知道用户是谁、在忙什么、有什么待办
5. **用户无感** — 用户只管过日子，系统在后台运转

## 信源（只有两个）

| 信源 | 角色 | 采集方式 |
|------|------|---------|
| 🎙️ 录音 | "你说了什么" | DJI Mic 全天佩戴 → 音频文件 → 去静音 → 压缩 → 切块 → 转写 |
| 👁️ Screenpipe | "你做了什么" | 屏幕活动自动采集 → API 查询 → 角色归因辅助 |

## 架构分层

```
┌──────────────────────────────────────┐
│              前端页面                 │  ← 给用户看的
│   查看个人档案 / 确认纠正 / 时间轴    │     app/index.html + app/server.py
└──────────────────┬───────────────────┘
                   │ HTTP API
┌──────────────────┴───────────────────┐
│            CLI / Python API          │  ← 给 Agent 调的
│   openmy context / correct / run     │     src/openmy/cli.py
└──────────────────┬───────────────────┘
                   │ 读写
┌──────────────────┴───────────────────┐
│          active_context.json         │  ← 状态数据库
│     corrections.jsonl（变更历史）      │     唯一真相源
└──────────────────┬───────────────────┘
                   │ 输入
         ┌─────────┴─────────┐
         │                   │
     🎙️ 录音             👁️ Screenpipe
    （你说了什么）        （你做了什么）
```

## 状态核心：active_context + corrections

```
active_context.json
├── stable_profile        ← 长期不变：身份、偏好、关键人物
│   └── identity, preferences, key_people_registry
├── rolling_context       ← 滚动更新（7-14 天窗口）
│   └── active_projects, open_loops, recent_decisions, entity_rollups
└── realtime_context      ← 当天即时
    └── today_focus, today_state

corrections.jsonl         ← append-only 修正历史，查询时自动叠加
```

## 处理管线

```
音频文件
  ↓ 去静音 + 压缩 + 切块（ffmpeg, services/ingest/audio_pipeline.py）
  ↓ 转写（Gemini CLI, adapters/transcription/gemini_cli.py）
  ↓ 清洗（services/cleaning/cleaner.py）
  ↓ 场景切分（services/segmentation/segmenter.py）
  ↓ 角色归因（services/roles/resolver.py）
  ↓ 蒸馏（services/distillation/distiller.py）
  ↓ 结构化提取：intents + facts（services/extraction/extractor.py）
  ↓ 跨日聚合（services/context/consolidation.py）
  ↓ active_context.json + corrections.jsonl
  ↓ Agent 消费 / 前端展示
```

> [!IMPORTANT]
> 音频导入**必须**经过本地去静音、压缩、切块预处理（`audio_pipeline.py`），
> 然后才送到 Gemini 转写。不能直接把原始音频扔给 LLM。

## 提取系统：intents + facts 双桶

提取器输出两类结构化数据：

- **intents** — 未来约束（待办、提醒、计划、承诺）
  - 带 due date（支持中文相对时间归一化）
  - 带 confidence + needs_review 标记
- **facts** — 已发生/已知的事实（观察、决策、偏好）

## 执行入口

Agent 的具体操作命令见 `skills/openmy-agent/SKILL.md`（执行层 skill）。

## 项目结构

```
~/Desktop/周瑟夫的上下文/
├── src/openmy/                         ← Python 包
│   ├── cli.py                           ← 统一 CLI 入口
│   ├── domain/                          ← 领域模型（intent, fact, models）
│   ├── services/
│   │   ├── ingest/audio_pipeline.py     ← 音频预处理（去静音/压缩/切块/重试）
│   │   ├── context/                     ← 状态系统（active_context, consolidation, corrections, renderer）
│   │   ├── extraction/extractor.py      ← 结构化提取（intents + facts）
│   │   ├── segmentation/segmenter.py    ← 场景切分
│   │   ├── cleaning/cleaner.py          ← 文本清洗
│   │   ├── roles/resolver.py            ← 角色归因
│   │   ├── distillation/distiller.py    ← 蒸馏
│   │   └── briefing/generator.py        ← 日报生成
│   └── adapters/
│       ├── transcription/gemini_cli.py  ← Gemini CLI 转写适配器
│       └── screenpipe/client.py         ← Screenpipe API 客户端
├── app/                                 ← 前端（用户唯一界面）
│   ├── server.py                        ← HTTP 服务
│   └── index.html                       ← 前端页面
├── data/
│   ├── active_context.json              ← 当前状态快照
│   ├── active_context.compact.md        ← Agent 注入用压缩版
│   ├── corrections.jsonl                ← 纠正历史（append-only）
│   └── YYYY-MM-DD/                      ← 每日原始数据
├── skills/
│   ├── openmy/SKILL.md                  ← 本文件（产品级定义）
│   └── openmy-agent/SKILL.md            ← 执行层 skill（Agent 命令路由）
└── tests/                               ← 131 个测试
```

## 纠正系统原则

1. **原始证据不改** — scenes.json、meta.json 是不可变事实
2. **推断结果可重算** — active_context 每次都从原始数据重新生成
3. **人工修正追加记录** — corrections.jsonl 是 append-only
4. **查询默认读纠错后视图** — `context` 命令自动叠加 corrections

## 路线图

- Phase 0：处理管道 ✅
- Phase 1：状态快照（active_context 三层模型）✅
- Phase 2：纠正系统 ✅
- Phase 2.5：Intent 系统（intents + facts 双桶提取）✅
- Phase 3：Screenpipe 信号接入
- Phase 4：前端页面（Dashboard）
- Phase 5：自维护闭环
- Phase 6：声纹识别

详见 Obsidian `研究报告/OpenMy-产品路线图.md`

## 测试

```bash
cd ~/Desktop/周瑟夫的上下文
python3 -m pytest tests/ -v    # 131 tests passed
```
