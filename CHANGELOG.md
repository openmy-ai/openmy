# Changelog

## [0.3.0] - 2026-05-09

### Features
- First-Run Wizard：首次使用时引导选转写引擎、配音频来源、跑 demo，全流程不再需要手动编辑配置
- 音频回放 Phase 1-3：场景卡片可以直接播放原始录音，支持 seek、变速、Range 请求
- 字幕审查 V1：选中文字先看来源字幕和原始音频，再决定是否纠错
- Smart Audio Player V2：Silero VAD 精确人声检测 + 波形可视化 + 字幕流动动画
- Grounded context Q&A：基于结构化上下文的问答合成，首页增加 recap 卡片
- 文件上传：网页端支持拖拽上传音频，带进度条和 pipeline 面板
- 周报 / 月报：`day.run` 完成后自动触发周聚合和月聚合
- 屏幕识别改进：agent_instructions 嵌入 health.check 输出，Agent 能自动发现可用能力
- Hash 路由：前端支持 `#date/weekly/monthly/start` 直接定位视图

### Fixes
- 管线质量：场景过滤更准、work_sessions 准确率提升、briefing 内容更丰富
- 首次 onboarding 不再选到不可用的本地转写路线
- `context.query` 崩溃修复 + skill agent 错误处理改进
- 音频引用跨 rerun 保持稳定，不再因为重跑丢失映射
- 上下文查询英文意图分类：`open/done/person` 等短词不再被子串误匹配
- `install-skills.sh` 处理已有 venv 和过期符号链接
- 过大 JSON 请求不再耗尽内存
- 屏幕锁定时跳过屏幕截取

### Internal
- ARCHITECTURE.md：从代码扫描生成的技术架构文档，替代过时的 STATE/ROADMAP/PROJECT
- 僵尸 worktree 清理：8 个断根 codex worktree 审计完成，7 个删除、1 个封存
- 过时的 .planning/ 文档归档到 .planning/archived/
- 527 个测试全部通过

## [0.2.0] - 2026-04-12

### Features
- Agent-native handoff for scene distillation and core extraction through `distill.pending`, `distill.submit`, `extract.core.pending`, and `extract.core.submit`
- `day.run` now pauses at the right handoff step when no LLM key is configured, instead of blindly skipping ahead
- `health.check` now reports whether LLM processing is available and points agents to the handoff flow
- New skill guides for agent-side distillation and extraction handoff
- `quick-start --demo` now runs a bundled sample without asking for cloud keys first
- Query and day status lookups now reuse `search_index.json` instead of reopening every day file

### Fixes
- Health and web surfaces no longer leak raw keys or trust unsafe transcript-shaped input
- Reruns now preserve human-confirmed roles, protect old outputs with backups, and avoid duplicate vault appends
- Runtime timestamps now go through shared time helpers instead of hand-written `+08:00`
- Scene distillation and cloud chunk transcription now run in parallel with retry/backoff on temporary `429/503` failures
- Core extraction meta writes and search index writes now use atomic JSON writes
- Open-source repo hygiene now includes issue forms, Dependabot, Ruff checks, conduct rules, and security guidance

## [0.1.0-alpha] - 2026-04-11

### Features
- Audio transcription with Gemini API, faster-whisper, and FunASR backends
- Rule-based text cleaning that preserves conversational rhythm
- Automatic scene segmentation by time windows
- AI-generated first-person daily briefing summaries
- Structured extraction of todos, facts, and decisions
- Temporal adjudication that separates completed actions from future intent
- Cross-day active_context memory aggregation with layered context views
- Optional screen recognition with application usage rollups
- Local web report for reviewing each day at a glance
- Skill endpoints for agent-facing context queries and day processing
- One-command onboarding via `openmy quick-start your-audio.wav`
