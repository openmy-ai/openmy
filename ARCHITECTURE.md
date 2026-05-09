# Architecture

> 本文件从代码生成，不从历史文档继承。最后更新 2026-05-09。

OpenMy 是本地优先的个人上下文引擎。把录音和屏幕变成 Agent 能长期记住的个人上下文。

## 技术栈

- Python 3.10+，无重型框架
- 内置 HTTP server（`http.server`）
- 前端：原生 JS + CSS，无框架
- 存储：文件系统（JSON + text）
- 核心依赖仅 3 个：`rich`（终端美化）、`silero-vad`（人声检测）、`watchdog`（文件监控）
- 各 STT / LLM provider SDK 均为可选依赖

## 目录结构

```
openmy/                     CLI 入口 shim
src/openmy/
├── cli.py                  主 CLI 入口
├── config.py               全局配置（provider / 路径 / 模型）
├── skill_dispatch.py       Agent skill 端点分发（18 个端点）
├── commands/               CLI 子命令（run / show / correct / context / screen 等 11 个）
├── services/               业务逻辑（见「数据流」）
│   ├── ingest/             音频发现 + STT 调度 + Silero VAD
│   ├── cleaning/           文本清洗
│   ├── segmentation/       场景切分
│   ├── roles/              角色归因
│   ├── distillation/       场景蒸馏（需要 LLM）
│   ├── extraction/         结构化提取（需要 LLM）
│   ├── briefing/           日报生成（需要 LLM）
│   ├── context/            活动上下文聚合 + 整合 + 纠正 + 渲染
│   ├── query/              结构化查询 + 搜索索引
│   ├── aggregation/        周报 / 月报
│   ├── onboarding/         引导状态
│   └── screen_recognition/ 屏幕识别（capture + OCR + enrich + align）
├── providers/
│   ├── stt/                6 个转写引擎：funasr / faster-whisper / gemini / groq / dashscope / deepgram
│   ├── llm/                LLM provider（gemini）
│   └── export/             导出（obsidian / notion）
├── domain/                 数据模型 + 意图系统（共 546 行）
├── adapters/               外部系统适配（gemini CLI 转写 / 屏幕识别客户端）
├── skill_handlers/         skill 端点实现
└── utils/                  工具函数（errors / interactive / io / paths / time）

app/                        HTTP server + 前端
├── server.py               HTTP server 启动
├── http_handlers.py        路由分发（30+ 路由）
├── payloads.py             请求/响应 payload 构建
├── audio_api.py            音频播放 API
├── context_api.py          上下文 API
├── pipeline_api.py         pipeline 管理
├── pipeline_runner.py      pipeline 步骤执行
├── job_runner.py           后台任务管理
├── upload.py               文件上传
├── index.html              单页入口
└── static/
    ├── app.js              前端主入口
    ├── modules/            18 个 JS 模块
    ├── css/                18 个样式文件
    └── vendor/             chart.js

skills/                     17 个 Agent skill 描述文件（Claude Code / Gemini CLI / Codex）
tests/                      57 个测试文件，13,723 行
scripts/                    install-skills.sh / check_readme_sync.py
```

## 数据流

```
录音文件 ──→ 音频发现 ──→ 转写（6 引擎之一）──→ 清洗 ──→ 场景切分
                                                              │
                 ┌──────────────────────────────────────────────┘
                 ▼
           角色归因 ──→ 蒸馏（LLM）──→ 结构化提取（LLM）──→ 日报（LLM）
                                                              │
                 ┌──────────────────────────────────────────────┘
                 ▼
           活动上下文聚合 ──→ 周报 / 月报 ──→ Agent / 你自己
```

无 LLM key 时，前 4 步（转写→清洗→切分→角色）可独立运行。蒸馏 / 提取 / 日报需要 LLM。

## CLI 命令

| 命令 | 用途 |
|------|------|
| `quick-start` | 首次使用向导 |
| `run` | 全流程处理一天 |
| `watch` | 监控录音文件夹自动处理 |
| `status` | 列出所有日期及处理状态 |
| `view` | 终端查看某天概览 |
| `clean` | 清洗转写文本 |
| `roles` | 场景切分 + 角色归因 |
| `distill` | 蒸馏摘要 |
| `briefing` | 生成日报 |
| `extract` | 提取 intents / facts |
| `correct` | 纠正转写 |
| `context` | 活动上下文 |
| `query` | 结构化查询 |
| `weekly` / `monthly` | 周报 / 月报 |
| `screen` | 屏幕识别开关 |
| `feedback` | 反馈记录 |
| `self-update` | 自升级 |
| `skill` | Agent 稳定 JSON 入口 |
| `agent` | Agent 兼容入口 |

## Skill 端点（Agent 接入）

| 端点 | 用途 |
|------|------|
| `status.get` | 所有日期状态 |
| `day.get` | 获取某天数据 |
| `day.run` | 处理某天 |
| `health.check` | 健康检查 + 推荐路线 |
| `context.get` | 活动上下文 |
| `context.query` | 结构化查询 |
| `distill.pending` / `distill.submit` | Agent-native 蒸馏交接 |
| `extract.core.pending` / `extract.core.submit` | Agent-native 提取交接 |
| `aggregate` / `aggregate.weekly` / `aggregate.monthly` | 聚合 |
| `correction.apply` | 应用纠正 |
| `vocab.init` | 初始化词库 |
| `profile.get` / `profile.set` | 用户配置 |

## HTTP API

**GET**：`/api/health` · `/api/context` · `/api/onboarding` · `/api/dates` · `/api/search` · `/api/stats` · `/api/briefing/{date}` · `/api/audio/{date}/{chunk}` · `/api/date/{date}` · `/api/date/{date}/meta` · `/api/date/{date}/briefing` · `/api/pipeline/jobs` · `/api/corrections` · `/api/settings/screen-context` · `/api/context/loops` · `/api/context/projects` · `/api/context/decisions` · `/api/context/query` · `/api/context/ask`

**POST**：`/api/upload` · `/api/correct` · `/api/correct/typo` · `/api/pipeline/jobs` · `/api/pipeline/jobs/{id}/{action}` · `/api/context/loops/close` · `/api/context/loops/reject` · `/api/context/projects/merge` · `/api/context/projects/reject` · `/api/context/decisions/reject`

## 转写引擎

| 引擎 | 类型 | 适用 |
|------|------|------|
| FunASR | 本地 | 中文为主 |
| faster-whisper | 本地 | 多语言通用 |
| Gemini | 云端 | 高精度 |
| Groq (Whisper) | 云端 | 快速 |
| DashScope | 云端 | 阿里系 |
| Deepgram | 云端 | 英文为主 |

## 代码量

| 部分 | 行数 |
|------|------|
| Python | 34,977 |
| JavaScript | 4,664 |
| 测试 | 13,723 |

版本：0.2.0
