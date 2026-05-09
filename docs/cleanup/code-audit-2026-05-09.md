# OpenMy Code Audit Report (2026-05-09)

> 本报告由 Agent 逐行扫描生成，评估文件职责、代码健康度与潜留问题。

## 目录: `app`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `audio_api.py` | 146 | HTTP 路由与 API 处理 | 未使用的 import (annotations) | 4/5 |
| `context_api.py` | 116 | HTTP 路由与 API 处理 | 未使用的 import (annotations) | 4/5 |
| `http_handlers.py` | 269 | HTTP 路由与 API 处理 | 未使用的 import (annotations)；包含空函数 (log_message) | 3/5 |
| `http_responses.py` | 32 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |
| `job_runner.py` | 444 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |
| `payloads.py` | 584 | 核心业务逻辑支撑 | 未使用的 import (annotations)；文件过长(>500行)，建议重构拆分 | 3/5 |
| `pipeline_api.py` | 96 | HTTP 路由与 API 处理 | 未使用的 import (get_pipeline_job_payload, run_pipeline_job_command, annotations) | 4/5 |
| `pipeline_runner.py` | 316 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |
| `server.py` | 228 | OpenMy — 本地网页服务（OpenMy package 版） | 未使用的 import (annotations) | 4/5 |
| `upload.py` | 139 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |

## 目录: `app/static`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `app.js` | 81 | 核心业务逻辑支撑 | 无 | 5/5 |

## 目录: `app/static/modules`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `api.js` | 30 | HTTP 路由与 API 处理 | 无 | 5/5 |
| `context.js` | 385 | 前端业务模块 (JS) | 无 | 5/5 |
| `corrections.js` | 259 | 前端业务模块 (JS) | 无 | 5/5 |
| `daily.js` | 342 | 前端业务模块 (JS) | 无 | 5/5 |
| `dates.js` | 189 | 前端业务模块 (JS) | 包含 TODO/FIXME 未完成项 | 4/5 |
| `home.js` | 211 | 前端业务模块 (JS) | 无 | 5/5 |
| `pipeline.js` | 501 | 前端业务模块 (JS) | 文件过长(>500行)，建议重构拆分 | 4/5 |
| `playback.js` | 265 | 前端业务模块 (JS) | 无 | 5/5 |
| `profile.js` | 86 | 前端业务模块 (JS) | 无 | 5/5 |
| `reports.js` | 155 | 前端业务模块 (JS) | 包含 TODO/FIXME 未完成项 | 4/5 |
| `router.js` | 22 | 前端业务模块 (JS) | 无 | 5/5 |
| `search.js` | 143 | 前端业务模块 (JS) | 无 | 5/5 |
| `settings.js` | 406 | 前端业务模块 (JS) | 无 | 5/5 |
| `sidebar.js` | 53 | 前端业务模块 (JS) | 无 | 5/5 |
| `state.js` | 74 | 前端业务模块 (JS) | 无 | 5/5 |
| `subtitle-overlay.js` | 511 | 前端业务模块 (JS) | 文件过长(>500行)，建议重构拆分 | 4/5 |
| `tokens.js` | 20 | 前端业务模块 (JS) | 无 | 5/5 |
| `utils.js` | 64 | 前端业务模块 (JS) | 无 | 5/5 |
| `waveform.js` | 164 | 前端业务模块 (JS) | 无 | 5/5 |

## 目录: `openmy`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 6 | Repo-root package shim for the src/openmy layout. | 无 | 5/5 |
| `__main__.py` | 5 | 核心业务逻辑支撑 | 无 | 5/5 |

## 目录: `scripts`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `check_readme_sync.py` | 66 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | OpenMy package. | 无 | 5/5 |
| `__main__.py` | 5 | 核心业务逻辑支撑 | 无 | 5/5 |
| `cli.py` | 401 | OpenMy — 个人上下文引擎 CLI. | 未使用的 import (annotations) | 4/5 |
| `config.py` | 261 | OpenMy 全局配置 | 未使用的 import (annotations) | 4/5 |
| `skill_dispatch.py` | 267 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/adapters`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | External adapter layer for OpenMy. | 无 | 5/5 |

## 目录: `src/openmy/adapters/screen_recognition`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 3 | 核心业务逻辑支撑 | 无 | 5/5 |
| `client.py` | 154 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/adapters/transcription`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Transcription adapters. | 无 | 5/5 |
| `gemini_cli.py` | 122 | Gemini STT 兼容壳。 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/commands`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | OpenMy CLI command implementations. | 无 | 5/5 |
| `common.py` | 420 | CLI 子命令及交互接口 | 未使用的 import (annotations) | 4/5 |
| `context.py` | 42 | CLI 子命令及交互接口 | 未使用的 import (annotations) | 4/5 |
| `correct.py` | 394 | CLI 子命令及交互接口 | 未使用的 import (annotations) | 4/5 |
| `menu.py` | 79 | CLI 子命令及交互接口 | 未使用的 import (annotations) | 4/5 |
| `parser.py` | 142 | CLI 子命令及交互接口 | 未使用的 import (annotations) | 4/5 |
| `quick_start.py` | 5 | CLI 子命令及交互接口 | 未使用的 import (annotations, cmd_quick_start) | 4/5 |
| `run.py` | 1380 | CLI 子命令及交互接口 | 未使用的 import (annotations)；文件过长(>500行)，建议重构拆分 | 3/5 |
| `screen.py` | 80 | CLI 子命令及交互接口 | 未使用的 import (annotations) | 4/5 |
| `self_update.py` | 40 | CLI 子命令及交互接口 | 未使用的 import (annotations) | 4/5 |
| `show.py` | 609 | CLI 子命令及交互接口 | 未使用的 import (annotations)；文件过长(>500行)，建议重构拆分 | 3/5 |

## 目录: `src/openmy/domain`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 35 | Core domain models for OpenMy. | 无 | 5/5 |
| `intent.py` | 257 | 领域模型与数据结构定义 | 未使用的 import (annotations) | 4/5 |
| `models.py` | 254 | 领域模型与数据结构定义 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/providers`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Model provider layer for OpenMy. | 无 | 5/5 |
| `base.py` | 98 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |
| `registry.py` | 99 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/providers/export`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 5 | 核心业务逻辑支撑 | 无 | 5/5 |
| `base.py` | 18 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |
| `notion.py` | 174 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |
| `obsidian.py` | 109 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/providers/llm`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | LLM providers. | 无 | 5/5 |
| `gemini.py` | 161 | LLM 模型接口适配 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/providers/stt`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Speech-to-text providers. | 无 | 5/5 |
| `dashscope_asr.py` | 79 | STT 语音转文本引擎适配 | 未使用的 import (annotations) | 4/5 |
| `deepgram.py` | 89 | STT 语音转文本引擎适配 | 未使用的 import (annotations) | 4/5 |
| `faster_whisper.py` | 133 | STT 语音转文本引擎适配 | 未使用的 import (annotations) | 4/5 |
| `funasr.py` | 171 | STT 语音转文本引擎适配 | 未使用的 import (annotations) | 4/5 |
| `gemini.py` | 139 | STT 语音转文本引擎适配 | 未使用的 import (annotations) | 4/5 |
| `groq_whisper.py` | 107 | STT 语音转文本引擎适配 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/resources`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Bundled resource files. | 无 | 5/5 |

## 目录: `src/openmy/services`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Service layer for OpenMy. | 无 | 5/5 |
| `feedback.py` | 140 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |
| `scene_quality.py` | 131 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |
| `watcher.py` | 199 | watcher.py — 录音文件监控器。 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/aggregation`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 15 | 周报与月报数据聚合 | 无 | 5/5 |
| `monthly.py` | 92 | 周报与月报数据聚合 | 未使用的 import (annotations) | 4/5 |
| `weekly.py` | 173 | 周报与月报数据聚合 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/briefing`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 3 | 日报生成逻辑 | 无 | 5/5 |
| `__main__.py` | 3 | 日报生成逻辑 | 无 | 5/5 |
| `cli.py` | 52 | Daily Briefing CLI. | 未使用的 import (annotations) | 4/5 |
| `generator.py` | 519 | Daily Briefing 生成器 — 把一天的语音+屏幕数据变成 AI 可读的交接文档 | 未使用的 import (annotations)；文件过长(>500行)，建议重构拆分 | 3/5 |

## 目录: `src/openmy/services/cleaning`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Cleaning services. | 无 | 5/5 |
| `cleaner.py` | 420 | cleaner.py — 规则引擎清洗 + corrections.json 确定性纠错 | 无 | 5/5 |

## 目录: `src/openmy/services/context`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Active Context — 个人上下文状态快照与跨日晋升引擎. | 无 | 5/5 |
| `active_context.py` | 476 | Active Context 数据模型 — 三层快照 schema. | 未使用的 import (annotations) | 4/5 |
| `consolidation.py` | 1163 | Active Context 汇总器 — 把日级数据提升为全局状态快照。 | 未使用的 import (annotations)；包含 TODO/FIXME 未完成项；文件过长(>500行)，建议重构拆分 | 2/5 |
| `corrections.py` | 308 | Active Context 纠正事件系统. | 未使用的 import (annotations) | 4/5 |
| `renderer.py` | 210 | Active Context 展示器 — 生成不同层级的文本视图。 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/distillation`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Scene distillation services. | 无 | 5/5 |
| `distiller.py` | 165 | 场景摘要蒸馏 (LLM) | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/extraction`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Structured extraction services. | 无 | 5/5 |
| `extractor.py` | 1636 | extract.py — 从每日上下文转写中提取结构化摘要 | 未使用的 import (annotations)；包含 TODO/FIXME 未完成项；文件过长(>500行)，建议重构拆分 | 2/5 |

## 目录: `src/openmy/services/ingest`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 2 | Audio ingest services for OpenMy. | 无 | 5/5 |
| `audio_pipeline.py` | 564 | 音频采集与调度处理 | 未使用的 import (annotations)；文件过长(>500行)，建议重构拆分 | 3/5 |
| `transcription_enrichment.py` | 369 | 音频采集与调度处理 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/onboarding`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 5 | 首配状态辅助。 | 无 | 5/5 |
| `state.py` | 141 | 核心业务逻辑支撑 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/query`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 2 | Structured query services for OpenMy. | 无 | 5/5 |
| `context_query.py` | 1090 | 结构化数据索引与查询 | 未使用的 import (annotations)；文件过长(>500行)，建议重构拆分 | 3/5 |
| `search_index.py` | 226 | 结构化数据索引与查询 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/roles`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Role resolution services. | 无 | 5/5 |
| `resolver.py` | 450 | 声纹与角色归因 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/screen_recognition`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | 屏幕上下文服务命名空间。 | 无 | 5/5 |
| `align.py` | 41 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `capture.py` | 122 | 兼容入口：把屏幕采集能力按职责拆到独立模块后继续对外暴露原接口。 | 未使用的 import (ScreenEventRecord, daemon_running, day_dir) | 4/5 |
| `capture_common.py` | 235 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `capture_daemon.py` | 33 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `capture_engine.py` | 360 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `capture_store.py` | 200 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `capture_tick.py` | 36 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `enrich.py` | 61 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `hints.py` | 205 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `ocr_bridge.py` | 191 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `privacy.py` | 70 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `provider.py` | 45 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `sessionize.py` | 79 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `settings.py` | 114 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |
| `summary.py` | 156 | 屏幕画面捕获与 OCR 提取 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/services/segmentation`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Scene segmentation services. | 无 | 5/5 |
| `segmenter.py` | 102 | 场景切分逻辑 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/skill_handlers`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | 技能动作分组实现。 | 无 | 5/5 |
| `common.py` | 373 | HTTP 路由与 API 处理 | 未使用的 import (annotations) | 4/5 |
| `context_profile.py` | 360 | HTTP 路由与 API 处理 | 未使用的 import (annotations) | 4/5 |
| `day_pipeline.py` | 405 | HTTP 路由与 API 处理 | 未使用的 import (annotations) | 4/5 |
| `health_aggregate.py` | 332 | HTTP 路由与 API 处理 | 未使用的 import (annotations) | 4/5 |

## 目录: `src/openmy/utils`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `__init__.py` | 1 | Shared utility helpers for OpenMy. | 无 | 5/5 |
| `errors.py` | 93 | 通用辅助工具函数 | 未使用的 import (annotations) | 4/5 |
| `interactive.py` | 128 | 通用辅助工具函数 | 未使用的 import (annotations) | 4/5 |
| `io.py` | 31 | 通用辅助工具函数 | 未使用的 import (annotations) | 4/5 |
| `paths.py` | 66 | 通用辅助工具函数 | 未使用的 import (annotations) | 4/5 |
| `time.py` | 65 | 通用辅助工具函数 | 未使用的 import (annotations) | 4/5 |

## 目录: `tests`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `test_monthly_aggregation.py` | 82 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_skill_agent_scenarios.py` | 219 | Skill Agent 交互场景测试。 | 无 | 5/5 |
| `test_weekly_aggregation.py` | 89 | 单元测试与集成测试用例 | 无 | 5/5 |

## 目录: `tests/unit`

| 文件 | 行数 | 职责 | 发现的问题 | 评分 |
|---|---|---|---|---|
| `fixture_loader.py` | 11 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_active_context.py` | 267 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_answer_synthesis.py` | 82 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_app_server.py` | 915 | 单元测试与集成测试用例 | 文件过长(>500行)，建议重构拆分 | 4/5 |
| `test_briefing.py` | 270 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_clean.py` | 268 | test_clean.py — 清洗模块测试 | 无 | 5/5 |
| `test_cli.py` | 2257 | CLI 子命令及交互接口 | 包含 TODO/FIXME 未完成项；文件过长(>500行)，建议重构拆分 | 3/5 |
| `test_cli_extract.py` | 51 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_consolidation.py` | 707 | 单元测试与集成测试用例 | 文件过长(>500行)，建议重构拆分 | 4/5 |
| `test_context_query.py` | 502 | 单元测试与集成测试用例 | 包含 TODO/FIXME 未完成项；文件过长(>500行)，建议重构拆分 | 3/5 |
| `test_context_query_cli.py` | 63 | CLI 子命令及交互接口 | 无 | 5/5 |
| `test_corrections.py` | 455 | 单元测试与集成测试用例 | 包含 TODO/FIXME 未完成项 | 4/5 |
| `test_distiller.py` | 221 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_export_providers.py` | 84 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_extractor.py` | 770 | 单元测试与集成测试用例 | 文件过长(>500行)，建议重构拆分 | 4/5 |
| `test_faster_whisper_provider.py` | 23 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_feedback.py` | 81 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_frontend_shell.py` | 228 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_funasr_provider.py` | 78 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_gemini_cli_transcribe.py` | 74 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_gemini_llm_provider.py` | 25 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_ingest_audio_pipeline.py` | 530 | 单元测试与集成测试用例 | 文件过长(>500行)，建议重构拆分 | 4/5 |
| `test_intent.py` | 145 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_interactive.py` | 55 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_io.py` | 23 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_job_runner.py` | 283 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_onboarding_state.py` | 72 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_paths.py` | 47 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_provider_registry.py` | 110 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_quick_start_wizard.py` | 93 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_readme_sync_guard.py` | 25 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_run_aggregation.py` | 147 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_scene_quality.py` | 55 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_scene_tagger.py` | 258 | test_scene_tagger.py — 场景切分和角色标注测试 | 无 | 5/5 |
| `test_screen_align.py` | 49 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_briefing.py` | 178 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_capture.py` | 248 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_context_hints.py` | 260 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_enrich.py` | 79 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_extract.py` | 56 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_privacy.py` | 97 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_product_copy.py` | 37 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_provider.py` | 111 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_roles.py` | 69 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_sessionize.py` | 73 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_screen_settings.py` | 87 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_skill_cli.py` | 677 | CLI 子命令及交互接口 | 包含 TODO/FIXME 未完成项；文件过长(>500行)，建议重构拆分 | 3/5 |
| `test_skill_dispatch.py` | 644 | 单元测试与集成测试用例 | 文件过长(>500行)，建议重构拆分 | 4/5 |
| `test_skill_docs.py` | 100 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_stt_provider_expansion.py` | 95 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_subtitle_review_behavior.py` | 197 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_transcription_enrichment.py` | 293 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_watcher.py` | 79 | 单元测试与集成测试用例 | 无 | 5/5 |
| `test_web_smoke.py` | 629 | 单元测试与集成测试用例 | 文件过长(>500行)，建议重构拆分 | 4/5 |

## 需要关注的问题清单

| 严重度 | 文件 | 问题描述 |
|---|---|---|
| 🔴 高 | `src/openmy/services/context/consolidation.py` | 未使用的 import (annotations) |
| 🔴 高 | `src/openmy/services/context/consolidation.py` | 包含 TODO/FIXME 未完成项 |
| 🔴 高 | `src/openmy/services/context/consolidation.py` | 文件过长(>500行)，建议重构拆分 |
| 🔴 高 | `src/openmy/services/extraction/extractor.py` | 未使用的 import (annotations) |
| 🔴 高 | `src/openmy/services/extraction/extractor.py` | 包含 TODO/FIXME 未完成项 |
| 🔴 高 | `src/openmy/services/extraction/extractor.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `app/http_handlers.py` | 未使用的 import (annotations) |
| 🟡 中 | `app/http_handlers.py` | 包含空函数 (log_message) |
| 🟡 中 | `app/payloads.py` | 未使用的 import (annotations) |
| 🟡 中 | `app/payloads.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `src/openmy/commands/run.py` | 未使用的 import (annotations) |
| 🟡 中 | `src/openmy/commands/run.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `src/openmy/commands/show.py` | 未使用的 import (annotations) |
| 🟡 中 | `src/openmy/commands/show.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `src/openmy/services/briefing/generator.py` | 未使用的 import (annotations) |
| 🟡 中 | `src/openmy/services/briefing/generator.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `src/openmy/services/ingest/audio_pipeline.py` | 未使用的 import (annotations) |
| 🟡 中 | `src/openmy/services/ingest/audio_pipeline.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `src/openmy/services/query/context_query.py` | 未使用的 import (annotations) |
| 🟡 中 | `src/openmy/services/query/context_query.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `tests/unit/test_cli.py` | 包含 TODO/FIXME 未完成项 |
| 🟡 中 | `tests/unit/test_cli.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `tests/unit/test_context_query.py` | 包含 TODO/FIXME 未完成项 |
| 🟡 中 | `tests/unit/test_context_query.py` | 文件过长(>500行)，建议重构拆分 |
| 🟡 中 | `tests/unit/test_skill_cli.py` | 包含 TODO/FIXME 未完成项 |
| 🟡 中 | `tests/unit/test_skill_cli.py` | 文件过长(>500行)，建议重构拆分 |
| 🔵 低 | `app/audio_api.py` | 未使用的 import (annotations) |
| 🔵 低 | `app/context_api.py` | 未使用的 import (annotations) |
| 🔵 低 | `app/http_responses.py` | 未使用的 import (annotations) |
| 🔵 低 | `app/job_runner.py` | 未使用的 import (annotations) |
| 🔵 低 | `app/pipeline_api.py` | 未使用的 import (get_pipeline_job_payload, run_pipeline_job_command, annotations) |
| 🔵 低 | `app/pipeline_runner.py` | 未使用的 import (annotations) |
| 🔵 低 | `app/server.py` | 未使用的 import (annotations) |
| 🔵 低 | `app/static/modules/dates.js` | 包含 TODO/FIXME 未完成项 |
| 🔵 低 | `app/static/modules/pipeline.js` | 文件过长(>500行)，建议重构拆分 |
| 🔵 低 | `app/static/modules/reports.js` | 包含 TODO/FIXME 未完成项 |
| 🔵 低 | `app/static/modules/subtitle-overlay.js` | 文件过长(>500行)，建议重构拆分 |
| 🔵 低 | `app/upload.py` | 未使用的 import (annotations) |
| 🔵 低 | `scripts/check_readme_sync.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/adapters/screen_recognition/client.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/adapters/transcription/gemini_cli.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/cli.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/commands/common.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/commands/context.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/commands/correct.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/commands/menu.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/commands/parser.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/commands/quick_start.py` | 未使用的 import (annotations, cmd_quick_start) |
| 🔵 低 | `src/openmy/commands/screen.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/commands/self_update.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/config.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/domain/intent.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/domain/models.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/base.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/export/base.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/export/notion.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/export/obsidian.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/llm/gemini.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/registry.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/stt/dashscope_asr.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/stt/deepgram.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/stt/faster_whisper.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/stt/funasr.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/stt/gemini.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/providers/stt/groq_whisper.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/aggregation/monthly.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/aggregation/weekly.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/briefing/cli.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/context/active_context.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/context/corrections.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/context/renderer.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/distillation/distiller.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/feedback.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/ingest/transcription_enrichment.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/onboarding/state.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/query/search_index.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/roles/resolver.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/scene_quality.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/align.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/capture.py` | 未使用的 import (ScreenEventRecord, daemon_running, day_dir) |
| 🔵 低 | `src/openmy/services/screen_recognition/capture_common.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/capture_daemon.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/capture_engine.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/capture_store.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/capture_tick.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/enrich.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/hints.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/ocr_bridge.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/privacy.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/provider.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/sessionize.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/settings.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/screen_recognition/summary.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/segmentation/segmenter.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/services/watcher.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/skill_dispatch.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/skill_handlers/common.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/skill_handlers/context_profile.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/skill_handlers/day_pipeline.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/skill_handlers/health_aggregate.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/utils/errors.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/utils/interactive.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/utils/io.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/utils/paths.py` | 未使用的 import (annotations) |
| 🔵 低 | `src/openmy/utils/time.py` | 未使用的 import (annotations) |
| 🔵 低 | `tests/unit/test_app_server.py` | 文件过长(>500行)，建议重构拆分 |
| 🔵 低 | `tests/unit/test_consolidation.py` | 文件过长(>500行)，建议重构拆分 |
| 🔵 低 | `tests/unit/test_corrections.py` | 包含 TODO/FIXME 未完成项 |
| 🔵 低 | `tests/unit/test_extractor.py` | 文件过长(>500行)，建议重构拆分 |
| 🔵 低 | `tests/unit/test_ingest_audio_pipeline.py` | 文件过长(>500行)，建议重构拆分 |
| 🔵 低 | `tests/unit/test_skill_dispatch.py` | 文件过长(>500行)，建议重构拆分 |
| 🔵 低 | `tests/unit/test_web_smoke.py` | 文件过长(>500行)，建议重构拆分 |
