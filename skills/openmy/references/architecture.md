# OpenMy 产品架构

> 本文件是产品级知识参考。Agent 需要理解产品全貌时读这里。
> 操作指令在上级 SKILL.md。

## 核心定义

OpenMy 是一个**自维护的个人上下文系统**。

- 让 Agent 少猜一点
- 不是笔记工具，不是日报生成器
- 是 Agent 的"用户认知层"

## 第零铁律

**用户永远不碰终端。**

- CLI 是 Agent 的 API，不是给人用的
- 前端页面（`app/`）是用户唯一的界面
- 用户只通过自然语言对话和 Agent 交互

## 信源（只有两个）

| 信源 | 角色 | 采集方式 |
|------|------|---------|
| 🎙️ 录音 | "你说了什么" | DJI Mic → 去静音 → 压缩 → 切块 → 转写 |
| 👁️ Screenpipe | "你做了什么" | 屏幕活动自动采集 → API 查询 |

## 架构分层

```
┌──────────────────────────────────────┐
│              前端页面                 │  ← 给用户看
│   app/server.py + app/index.html     │
└──────────────────┬───────────────────┘
                   │ HTTP API
┌──────────────────┴───────────────────┐
│            CLI / Python API          │  ← 给 Agent 调
│   src/openmy/cli.py                  │
└──────────────────┬───────────────────┘
                   │ 读写
┌──────────────────┴───────────────────┐
│    active_context.json               │  ← 状态数据库
│    corrections.jsonl                 │
└──────────────────┬───────────────────┘
                   │ 输入
         ┌─────────┴─────────┐
     🎙️ 录音             👁️ Screenpipe
```

## 状态核心

```
active_context.json
├── stable_profile        ← 长期不变：身份、偏好、关键人物
├── rolling_context       ← 滚动更新（7-14 天窗口）：项目、待办、决策
└── realtime_context      ← 当天即时：今日焦点

corrections.jsonl         ← append-only 修正历史，查询时自动叠加
```

## 处理管线

```
音频文件
  ↓ 去静音+压缩+切块 (services/ingest/audio_pipeline.py)
  ↓ 转写 (adapters/transcription/gemini_cli.py)
  ↓ 清洗 (services/cleaning/cleaner.py)
  ↓ 场景切分 (services/segmentation/segmenter.py)
  ↓ 蒸馏 (services/distillation/distiller.py)
  ↓ 结构化提取: intents+facts (services/extraction/extractor.py)
  ↓ 跨日聚合 (services/context/consolidation.py)
  ↓ active_context.json + corrections.jsonl
  ↓ Agent 消费 / 前端展示
```

> 角色归因（services/roles/resolver.py）已冻结，不在默认 `run` 流程中。
> 代码保留，可手动 `openmy roles YYYY-MM-DD` 调用。等 Phase 6 声纹识别再回来。

## 提取系统：intents + facts 双桶

- **intents** — 未来约束（待办、提醒、计划、承诺），带 due date + confidence
- **facts** — 已发生/已知的事实（观察、决策、偏好）

## 角色归因体系

| 层级 | 方法 |
|------|------|
| 1 | 亲口声明（"报告老婆"） |
| 2 | 关键词命中（AI术语→AI助手） |
| 3 | 继承上文 |
| 4 | Screenpipe 屏幕佐证 |
| 5 | 不确定 |

## 纠正系统原则

1. 原始证据不改（scenes.json、meta.json 是不可变事实）
2. 推断结果可重算（active_context 每次从原始数据重新生成）
3. 人工修正追加记录（corrections.jsonl 是 append-only）
4. 查询默认读纠错后视图

## 项目结构

```
~/Desktop/周瑟夫的上下文/
├── src/openmy/
│   ├── cli.py
│   ├── domain/              (intent, fact, models)
│   ├── services/
│   │   ├── ingest/          (音频预处理)
│   │   ├── context/         (active_context, consolidation, corrections, renderer)
│   │   ├── extraction/      (intents + facts)
│   │   ├── segmentation/    (场景切分)
│   │   ├── cleaning/        (文本清洗)
│   │   ├── roles/           (角色归因)
│   │   ├── distillation/    (蒸馏)
│   │   └── briefing/        (日报)
│   └── adapters/
│       ├── transcription/   (Gemini CLI)
│       └── screenpipe/      (Screenpipe API)
├── app/                     (前端：用户唯一界面)
├── data/                    (状态数据)
├── skills/openmy/           (本 skill)
└── tests/                   (131 个测试)
```

## 路线图

- Phase 0: 处理管道 ✅
- Phase 1: 状态快照 ✅
- Phase 2: 纠正系统 ✅
- Phase 2.5: Intent 系统 ✅
- **Phase 2.8: 管线质量加固** ← 当前焦点（转写去语义化 + clean 保真 + 角色归因校准 + 提取产出量校准）
- Phase 3: Screenpipe 信号接入
- Phase 4: 前端页面
- Phase 5: 自维护闭环
- Phase 6: 声纹识别

## 愿景

> 如果你把阿兹海默症患者看作一个随时可能丢失上下文的 agent，
> OpenMy 的日报就是他的"上下文恢复"机制。

详见 Obsidian `项目/OpenMy/愿景.md` 和 `研究报告/OpenMy-产品路线图.md`
