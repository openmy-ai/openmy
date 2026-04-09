# Changelog

本文档按当前仓库可见历史整理。现有 Git 历史从 2026-04-07 开始，更早的私有阶段不在本文件范围内。

## [Unreleased]

### Added
- 前端从“浏览结果”补到“本地工作台”：
  - 新增 `概览 / 校正 / 流程` 三块工作区
  - 新增 `context/day/correction/pipeline` 一组 HTTP 接口
  - 新增轻量后台任务执行器 [`app/job_runner.py`](/Users/zhousefu/Desktop/周瑟夫的上下文/app/job_runner.py)
- 新增前端相关测试：
  - [`tests/unit/test_app_server.py`](/Users/zhousefu/Desktop/周瑟夫的上下文/tests/unit/test_app_server.py)
  - [`tests/unit/test_job_runner.py`](/Users/zhousefu/Desktop/周瑟夫的上下文/tests/unit/test_job_runner.py)
  - [`tests/unit/test_frontend_shell.py`](/Users/zhousefu/Desktop/周瑟夫的上下文/tests/unit/test_frontend_shell.py)
  - [`tests/unit/test_web_smoke.py`](/Users/zhousefu/Desktop/周瑟夫的上下文/tests/unit/test_web_smoke.py)

### Changed
- 前端可见文案从“直译型中文”进一步收成更自然的产品说法：
  - `总览` 改为 `概览`
  - `纠错` 改为 `校正`
  - `管线` 改为 `流程`
  - `更新上下文` 改为 `刷新上下文`
  - `全量运行` 改为 `重新运行`
  - `清洗 / 角色归因 / 蒸馏` 改为 `清理文本 / 识别对象 / 整理摘要`
- 前端 shell 测试同步改成围绕中文界面断言，而不是依赖旧英文文案。

### Fixed
- 修正前端 parity 阶段的测试契约漂移，当前前端相关组合验证结果为：`28 passed`。

## [2026-04-09]

### Added
- 音频导入管道抽取、相对时间归一化、格式修复，补齐更稳的 ingest 入口。(`0e910cf`)
- 提取模块接入 `response_json_schema`，结构化输出更稳定。(`2baf4f1`)
- 全模块接入 `thinking_config`，按任务深度区分推理强度。(`b3675ef`)

### Changed
- 所有大模型配置统一收到 [`src/openmy/config.py`](/Users/zhousefu/Desktop/周瑟夫的上下文/src/openmy/config.py)。(`3064ad2`)
- 模型调用统一切到 Gemini API，默认模型收敛到 `gemini-3.1-flash-lite-preview`。(`92c0dcf`)
- 清洗链路在一天内经历两次关键迭代：
  - 先把 cleaner 改为 Gemini CLI 语义清洗。(`d5042e4`)
  - 最终回到规则引擎，明确“不调 API、不改语义、不删脏话”的方向。(`c169e92`)
- SKILL 体系从“执行说明”升级为“产品定义 + 渐进披露”结构。(`9a3c7a2`, `e64e773`)

### Fixed
- 修复 Codex 审阅指出的三类问题。(`98431df`)
- 统一模型名与硬编码配置，清掉多处漂移。(`0254f6d`, `9d3eaa8`)
- `SKILL.md` 对齐 CLI 实际实现。(`0d54447`)

### Docs
- 路线图补入 Phase 2.8 管线质量加固。(`54b2f9a`)
- 前端 parity 的设计稿与实施计划落盘，为后续工作台化打基础。(`7315cef`)

## [2026-04-08]

### Added
- DayTape CLI 骨架与富文本状态命令。(`67a6ec3`)
- 每日概览查看命令。(`241c516`)
- 统一 CLI 管线入口。(`9bb9d6a`)
- Intent Phase 2.5：意图与事实双桶结构化提取上线。(`0740cd0`)

### Changed
- 项目完成 `daytape -> openmy` 全量重命名。(`45cfa2b`)
- 阶段性 corrections 收尾，测试数提升到 105 项全绿。(`205f8be`)
- 蒸馏 prompt 从“过短摘要”升级到更可读的摘要粒度，并顺手修复词库路径和补词。(`dcf27d2`)

### Fixed
- 清理个人数据、强化 `.gitignore`、移除工作区噪音。(`1c0f4b0`)
- 忽略项目本地 worktree。(`d3d8158`)

### Merge
- 合并 `codex/cli-pipeline` 分支。(`79cd41d`)

## [2026-04-07]

### Added
- 项目首次公开化：开源许可证、中文 README、英文 README。(`1783b80`, `2181b2c`, `2388286`)
- 包结构重构为 Python 包，数据落到 `data/`，为后续 OpenMy 演进打底。(`3446e66`)
- Screenpipe hints 模式，屏幕上下文可给角色判断加分。(`4a8aae4`)
- Daily Briefing 生成器。(`06ad645`)
- 前端三视图浏览骨架：时间线 / 表格 / 图表。基于当天多轮提交持续成形。(`7963bef`, `ad52642`, `a9c0ceb`)

### Changed
- 角色展示从“抽象类别”逐步改成“具体对话对象”，减少前端噪音。(`6fa5c12`, `515fca9`)
- 前端树形时间轴与 Props 卡片不断迭代，强化“读一天”而不是“看 JSON”。(`a9c0ceb`, `ad52642`)
- README 多次补充角色归因方案、Screenpipe 融合方式与设计哲学。(`e8dae7a`, `0eb229b`)

### Fixed
- 清除 AI 转写前缀噪音，并让前端展示时剥离 Markdown 标记。(`70dbaf8`)

### Notes
- 当天项目对外名称仍以 `DayTape` 为主；后续在 2026-04-08 统一更名为 `OpenMy`。
