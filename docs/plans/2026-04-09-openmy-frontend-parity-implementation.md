# OpenMy Frontend Parity Implementation Plan

> **For implementer:** Use TDD throughout. Write failing test first. Watch it fail. Then implement.

**Goal:** 把 OpenMy 前端补成一个本地工作台，覆盖 active_context、提取层、纠正动作和管线触发。

**Architecture:** 保留 `Python + 原生 HTML/CSS/JS`。`app/server.py` 继续做入口，新增更完整的读写 API；长任务走轻量 job 状态模型；前端按 `Overview / Day Workspace / Corrections / Pipeline` 四区组织。

**Tech Stack:** Python `unittest`、现有 OpenMy CLI / service 层、原生 HTML/CSS/JavaScript、现有本地 HTTP server。

---

## 改动边界

只允许修改这些区域：

- `app/server.py`
- `app/index.html`
- `tests/unit/`
- `docs/plans/2026-04-09-openmy-frontend-parity-design.md`
- `docs/plans/2026-04-09-openmy-frontend-parity-implementation.md`

如果 `server.py` 过重，可新建：

- `app/job_runner.py`
- `app/payloads.py`

## Task 1：修正日级路径解析与默认日期策略

**Files:**
- Modify: `app/server.py`
- Test: `tests/unit/test_app_server.py`

**TDD:**
1. 先写失败测试：
   - `test_resolve_day_paths_prefers_dated_meta_json`
   - `test_default_date_prefers_non_future_dates`
2. 跑：
   - `python3 -m pytest tests/unit/test_app_server.py -k "dated_meta_json or non_future_dates" -v`
3. 最小实现：
   - 修正 `{date}.meta.json` 解析
   - 新增默认日期选择 helper
4. 复跑确认通过

## Task 2：补齐 Overview 读接口

**Files:**
- Modify: `app/server.py`
- Optional Create: `app/payloads.py`
- Test: `tests/unit/test_app_server.py`

**TDD:**
1. 先写失败测试：
   - `test_context_endpoint_returns_status_and_today_focus`
   - `test_context_loops_endpoint_returns_open_loops`
   - `test_context_projects_endpoint_returns_active_projects`
2. 跑：
   - `python3 -m pytest tests/unit/test_app_server.py -k "context_endpoint or loops_endpoint or projects_endpoint" -v`
3. 最小实现：
   - 增加 `/api/context`
   - 增加 `/api/context/loops`
   - 增加 `/api/context/projects`
   - 增加 `/api/context/decisions`
4. 复跑确认通过

## Task 3：补齐 Day Workspace 的 meta / briefing 接口

**Files:**
- Modify: `app/server.py`
- Test: `tests/unit/test_app_server.py`

**TDD:**
1. 先写失败测试：
   - `test_date_detail_includes_meta_payload`
   - `test_date_meta_endpoint_returns_intents_and_facts`
   - `test_date_briefing_endpoint_returns_daily_briefing`
2. 跑：
   - `python3 -m pytest tests/unit/test_app_server.py -k "meta_endpoint or briefing_endpoint or date_detail" -v`
3. 最小实现：
   - `GET /api/date/:date/meta`
   - `GET /api/date/:date/briefing`
   - 确保现有 `/api/date/:date` 不再丢 meta
4. 复跑确认通过

## Task 4：补齐 context correction 写接口

**Files:**
- Modify: `app/server.py`
- Test: `tests/unit/test_app_server.py`

**TDD:**
1. 先写失败测试：
   - `test_close_loop_endpoint_appends_correction_and_refreshes_context`
   - `test_reject_loop_endpoint_appends_correction_and_refreshes_context`
   - `test_merge_project_endpoint_appends_correction_and_refreshes_context`
   - `test_reject_decision_endpoint_appends_correction_and_refreshes_context`
2. 跑：
   - `python3 -m pytest tests/unit/test_app_server.py -k "close_loop_endpoint or reject_loop_endpoint or merge_project_endpoint or reject_decision_endpoint" -v`
3. 最小实现：
   - 对应 POST 接口
   - 成功后重跑 `context`
4. 复跑确认通过

## Task 5：建立轻量 job runner

**Files:**
- Create: `app/job_runner.py`
- Modify: `app/server.py`
- Test: `tests/unit/test_job_runner.py`

**TDD:**
1. 先写失败测试：
   - `test_create_job_starts_in_queued_state`
   - `test_job_transitions_to_running_and_succeeded`
   - `test_job_failure_captures_log_lines`
2. 跑：
   - `python3 -m pytest tests/unit/test_job_runner.py -v`
3. 最小实现：
   - job registry
   - 后台执行入口
   - 日志收集
4. 复跑确认通过

## Task 6：开放 pipeline 任务接口

**Files:**
- Modify: `app/server.py`
- Modify: `app/job_runner.py`
- Test: `tests/unit/test_app_server.py`

**TDD:**
1. 先写失败测试：
   - `test_create_pipeline_job_endpoint_accepts_context_kind`
   - `test_create_pipeline_job_endpoint_accepts_run_kind`
   - `test_jobs_list_endpoint_returns_recent_jobs`
   - `test_job_detail_endpoint_returns_status_and_logs`
2. 跑：
   - `python3 -m pytest tests/unit/test_app_server.py -k "pipeline_job_endpoint or jobs_list_endpoint or job_detail_endpoint" -v`
3. 最小实现：
   - `POST /api/pipeline/jobs`
   - `GET /api/pipeline/jobs`
   - `GET /api/pipeline/jobs/:job_id`
4. 复跑确认通过

## Task 7：重构前端 shell，补齐 4 个工作区

**Files:**
- Modify: `app/index.html`
- Test: `tests/unit/test_frontend_shell.py`

**TDD:**
1. 先写失败测试：
   - `test_index_contains_overview_workspace`
   - `test_index_contains_day_workspace`
   - `test_index_contains_corrections_workspace`
   - `test_index_contains_pipeline_workspace`
2. 跑：
   - `python3 -m pytest tests/unit/test_frontend_shell.py -v`
3. 最小实现：
   - 新导航结构
   - 新内容容器
   - 保留原 time line / briefing 能力
4. 复跑确认通过

## Task 8：接上 Overview / Day Workspace / Corrections 数据

**Files:**
- Modify: `app/index.html`
- Test: `tests/unit/test_frontend_shell.py`

**TDD:**
1. 先写失败测试：
   - `test_index_fetches_context_payload`
   - `test_index_renders_meta_panels`
   - `test_index_exposes_correction_actions`
2. 跑：
   - `python3 -m pytest tests/unit/test_frontend_shell.py -k "context_payload or meta_panels or correction_actions" -v`
3. 最小实现：
   - Overview 卡片
   - Day Workspace 的 intents / facts / events / decisions / todos
   - Corrections 页的 action 面板
4. 复跑确认通过

## Task 9：接上 Pipeline UI 与响应式骨架

**Files:**
- Modify: `app/index.html`
- Test: `tests/unit/test_frontend_shell.py`
- Verify: 浏览器截图

**TDD:**
1. 先写失败测试：
   - `test_index_contains_pipeline_job_panel`
   - `test_mobile_layout_has_single_column_breakpoint`
2. 跑：
   - `python3 -m pytest tests/unit/test_frontend_shell.py -k "pipeline_job_panel or single_column_breakpoint" -v`
3. 最小实现：
   - Pipeline 操作面板
   - job 轮询状态区
   - 移动端单栏布局
4. 复跑确认通过

## Task 10：补集成 smoke 与视觉验证

**Files:**
- Create: `tests/unit/test_web_smoke.py`
- Modify: `app/server.py` / `app/index.html` if needed

**TDD:**
1. 先写失败测试：
   - `test_server_serves_context_and_pipeline_contract`
   - `test_server_serves_day_workspace_contract`
2. 跑：
   - `python3 -m pytest tests/unit/test_web_smoke.py -v`
3. 最小实现：
   - 修补 contract 漏项
4. 复跑确认通过

**Manual verify:**
- `python3 app/server.py`
- `HOME=/Users/zhousefu playwright screenshot --channel=chrome --viewport-size='1440,1024' --full-page --wait-for-timeout=1500 http://localhost:8420 /tmp/openmy-frontend-desktop-after.png`
- `HOME=/Users/zhousefu playwright screenshot -b chromium --device='iPhone 13' --full-page --wait-for-timeout=1500 http://localhost:8420 /tmp/openmy-frontend-mobile-after.png`

## 全量验证

```bash
cd /Users/zhousefu/Desktop/周瑟夫的上下文
python3 -m pytest tests/unit/test_app_server.py -v
python3 -m pytest tests/unit/test_job_runner.py -v
python3 -m pytest tests/unit/test_frontend_shell.py -v
python3 -m pytest tests/unit/test_web_smoke.py -v
python3 -m pytest tests/unit/test_cli.py tests/unit/test_active_context.py tests/unit/test_briefing.py -v
python3 -m pytest tests -v
python3 app/server.py
```

## 执行顺序

1. 先修路径和读接口
2. 再补 correction 写接口
3. 再做 job runner 和 pipeline API
4. 最后补前端 shell、数据接线和响应式
5. 以 smoke + 浏览器截图封口
