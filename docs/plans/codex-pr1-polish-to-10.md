# Codex 任务：PR1 质量修到 10/10

> 工作目录：/Users/zhousefu/Desktop/openmy-clean
> 基础：commit 30e4141 之后的代码

## 背景

PR1（Drop Zone + 进度面板）功能已实现，但代码审查发现以下问题需要修复到发布质量。

## 🔴 必须修的 Bug

### BUG-1: `rerenderHomeOnboardingSlot` 已修复
~~L696 调用不存在的函数~~ — 已由 CC 修复，改为 `rerenderHomePipelineSlot()` + `renderHomePage()`。**不需要再改。**

### BUG-2: `_duration_seconds` 重复定义
`job_runner.py` L382 和 `pipeline_api.py` L140 有**完全相同的** `_duration_seconds` 函数。
- 修法：`pipeline_api.py` 里删掉，改为从 `job_runner` import

### BUG-3: upload multipart 解析太脆弱
`handle_upload_request`（pipeline_api.py L329-398）手写了 multipart 解析器。这段代码：
- 没处理 `Content-Length` 为 0 但实际有 body 的情况（chunked transfer）
- 没处理 boundary 包含引号的变体
- `buffer.find(end_marker)` 在大文件时内存会膨胀

修法：用 Python 标准库 `email` 或 `cgi.parse_multipart` 替代手写解析。如果坚持手写，至少要：
1. 限制 buffer 最大增长为 `2 * len(end_marker)`
2. 添加 chunked transfer-encoding 的测试用例

### BUG-4: SIGSTOP/SIGCONT 跨平台问题
`pipeline_api.py` L265-266 用 `signal.SIGSTOP/SIGCONT`，这在 Windows 上不存在。虽然有 `hasattr` 检查，但暂停功能在 Windows 上会静默失效——前端仍会显示"暂停"按钮。
- 修法：前端根据 `can_pause` 是否为 true 来显示暂停按钮（已做了但 `can_pause` 没根据平台设置初始值）
- 在 `register_controller` 时，如果 `pause_fn` 是 None，`update_job(can_pause=False)` 确保按钮不出现

## 🟡 代码质量

### QUALITY-1: pipeline_api.py 太大了（460行）
一个文件承担了：上传、任务创建、进程管理、状态同步、控制操作。
- 修法：拆成 3 个文件：
  - `app/upload.py` — 上传逻辑
  - `app/pipeline_api.py` — API 入口 + 任务创建
  - `app/pipeline_runner.py` — 进程管理、状态同步、控制

### QUALITY-2: `_sync_job_from_run_status` 读文件太频繁
`run_pipeline_job_command` 主循环每 0.5 秒读一次 `run_status.json`。
- 修法：检查文件 mtime，只在文件变化时才 parse JSON

### QUALITY-3: handle._runner 直接访问私有成员
`pipeline_api.py` L228、L245、L292 直接访问 `handle._runner`。
- 修法：通过 `JobHandle` 的公开方法操作，或在 `JobHandle` 上加 `get_job()` 方法

### QUALITY-4: 前端 app.js 函数命名不一致
- `getHomeDisplayJob` vs `getActiveHomeJob`（已改名但有残留引用？）
- `renderHomeProgressPanel` 叫 "progress panel" 但也渲染 Drop Zone（当 job=null 时）

## 🟢 测试缺口

### TEST-1: upload API 测试
缺 `test_upload_api.py`，需要覆盖：
- 正常上传 .wav 文件
- 拒绝 .exe 文件
- 超出 500MB 限制
- boundary 包含引号
- 空文件名

### TEST-2: 进度百分比边界测试
`test_job_runner.py` 缺：
- 所有步骤都 skipped → progress 应该 100%
- 单步骤 job → progress 计算
- 0 步骤 job → progress 计算

### TEST-3: ETA 算法测试
- 无历史数据 + 无文件大小 → 应返回 None
- 有历史数据 → 基于均值计算
- 文件大小极端值（1KB / 10GB）→ 合理 clamp

### TEST-4: 前端状态机测试
浏览器测试（可选但推荐）：
- 加载首页 → 无 active job → 显示 Drop Zone
- 有 active job → 显示进度面板
- job 完成 → 显示"查看日报"按钮

## 📘 Skill 文档同步（重要！）

PR1 加了 6 个新能力，但 **skills/ 目录的 SKILL.md 完全没更新**。Agent 不知道这些新功能存在。

### SKILL-1: 更新 `skills/openmy-day-run/SKILL.md`
新增以下内容：
- Web UI 上传入口：用户可以在 `localhost:8420` 首页直接拖入音频文件，会自动调用 `POST /api/upload` + `POST /api/pipeline/jobs`
- 进度面板：pipeline 跑起来后 Web UI 会实时显示 4 个阶段（转写→清洗→场景切分→蒸馏）的进度
- 控制操作：用户可以在 Web UI 上暂停、取消、跳过当前步骤
- Agent 不需要调这些 API（已有 skill 命令行入口），但 Agent 应该知道可以告诉用户"打开 localhost:8420 看进度"

### SKILL-2: 更新 `skills/openmy-status-review/SKILL.md`
新增以下内容：
- `GET /api/pipeline/jobs` — 获取所有 pipeline 任务列表
- `GET /api/pipeline/jobs/{id}` — 获取单个任务详情（含 steps, progress_pct, eta_seconds）
- Agent 如果想查 pipeline 状态，可以直接调这个 API 而不用读 run_status.json

### SKILL-3: 更新 `skills/openmy-distill/SKILL.md`
新增以下内容：
- LLM safety refusal 容错：如果 Gemini 因安全过滤器拒绝处理某个场景，pipeline 会自动跳过该场景（不中断），并打印 `⚠️ 场景[N]被安全过滤器跳过`
- Agent 不需要额外处理这个情况，只需知道最终结果里可能有空摘要的场景

### SKILL-4: 更新 `skills/openmy/SKILL.md`（主路由）
在路由表里新增：
- `inbox` 目录概念：上传的文件会存到 `data/inbox/` 目录
- Web UI 现在是另一个有效的输入入口（不只是 CLI 和 Agent）

### SKILL-5: 更新 `AGENTS.md`
在"Build & Test"之前新增一段：
```markdown
## Web UI

OpenMy 内置一个本地网页界面（`localhost:8420`），用户可以：
- 拖入音频文件直接开始处理
- 实时查看转写进度（4 阶段可视化）
- 暂停、取消或跳过当前步骤
- 浏览历史日报

Agent 不需要操作 Web UI，但可以建议用户"打开 localhost:8420 看进度"。
```

## 实施顺序

1. 先修 BUG-2 到 BUG-4（最快）
2. 补 TEST-1 到 TEST-3（验证修复）
3. 做 QUALITY-1 拆文件（最大改动）
4. 做 QUALITY-2 和 QUALITY-3（小改进）
5. 更新 SKILL-1 到 SKILL-5（文档同步）
6. 跑全量测试确认没回退

## 验证

```bash
python3 -m pytest tests/ -q
```

全部通过 + 无 lint 报错 + skill 文档已更新 = 完成。

## 不要做的事

- 不要改 CLI（cli.py / commands/）
- 不要动 STT provider 层
- 不要改 README
- 不要加新功能

