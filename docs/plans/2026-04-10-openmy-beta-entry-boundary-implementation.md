# OpenMy Beta Entry & Local Boundary Implementation Plan

> **For implementer:** Use TDD throughout. Write failing test first. Watch it fail. Then implement.

**Goal:** 一次性收口 OpenMy Beta 的入口契约、本地网页默认安全边界、最小结构拆分、job 持久化和 watcher 扫描兜底。

**Architecture:** 保留现有 Python + 原生 HTML/HTTP 方案，不引入新框架或数据库。CLI 改成“解析 + 调度”，server 改成“装配 + handler / payload / response helpers”，pipeline job 走本地 JSON 持久化，watcher 走“事件监听优先、目录扫描托底”。

**Tech Stack:** Python `argparse` / `unittest` / `http.server` / `threading` / `pathlib`，现有 OpenMy service 层与本地 HTML 前端。

---

## 改动边界

允许修改：

- `README.md`
- `app/server.py`
- `app/job_runner.py`
- `src/openmy/cli.py`
- `src/openmy/services/watcher.py`
- `tests/unit/test_cli.py`
- `tests/unit/test_app_server.py`
- `tests/unit/test_job_runner.py`
- `tests/unit/test_web_smoke.py`
- `docs/plans/2026-04-10-openmy-beta-entry-boundary-design.md`
- `docs/plans/2026-04-10-openmy-beta-entry-boundary-implementation.md`

允许新增：

- `src/openmy/commands/`
- `app/http_handlers.py`
- `app/http_responses.py`
- `app/payloads.py`
- `app/pipeline_api.py`

## 我正在使用 writing-plans skill 来创建实施计划

执行方式：用户已明确要求“一次性干完”，因此默认采用**当前会话直接执行**，并在末尾补一次独立代码审查。

## Task 1：为 quick-start 先写失败测试

**Files:**
- Modify: `tests/unit/test_cli.py`

**TDD:**
1. 新增失败测试：
   - `test_cli_help_lists_quick_start`
   - `test_cli_quick_start_infers_date_and_reuses_run`
   - `test_cli_quick_start_reports_missing_gemini_key_in_plain_chinese`
2. 跑：
   - `python3 -m pytest tests/unit/test_cli.py -k "quick_start or help_lists_quick_start" -v`
3. 确认看到失败，再进入 Task 2

## Task 2：实现 quick-start 最小闭环

**Files:**
- Modify: `src/openmy/cli.py`
- Optional Create: `src/openmy/commands/common.py`
- Optional Create: `src/openmy/commands/run.py`

**TDD:**
1. 最小实现：
   - 新增 `quick-start` 子命令
   - 文件名日期推断 helper
   - `.env` 加载 helper
   - 依赖检查 helper（Python / ffmpeg / ffprobe / key）
   - 复用 `cmd_run`
   - 成功后打开浏览器
2. 跑：
   - `python3 -m pytest tests/unit/test_cli.py -k "quick_start or help_lists_quick_start" -v`
3. 确认通过

## Task 3：把 README 与真实入口对齐

**Files:**
- Modify: `README.md`

**TDD / Verify:**
1. 先人工核对当前 README 的入口承诺和流程图
2. 最小改动：
   - 主入口维持 `openmy quick-start`
   - 本地地址统一为 `http://127.0.0.1:8420`
   - 修掉流程图裸露风险
3. 验证：
   - `python3 -m openmy --help`
   - 人工读取 `README.md`

## Task 4：先写 server host / CORS 失败测试

**Files:**
- Modify: `tests/unit/test_app_server.py`
- Modify: `tests/unit/test_web_smoke.py`

**TDD:**
1. 新增失败测试：
   - `test_server_defaults_to_loopback_host`
   - `test_json_response_does_not_return_wildcard_cors`
   - `test_web_smoke_server_binds_to_loopback`
2. 跑：
   - `python3 -m pytest tests/unit/test_app_server.py -k "loopback_host or wildcard_cors" -v`
   - `python3 -m pytest tests/unit/test_web_smoke.py -k "loopback" -v`
3. 确认失败，再进入 Task 5

## Task 5：实现本地网页默认安全边界

**Files:**
- Modify: `app/server.py`
- Optional Create: `app/http_responses.py`

**TDD:**
1. 最小实现：
   - server 默认 host 改为 `127.0.0.1`
   - 启动入口支持显式 `--host`
   - 去掉 wildcard CORS
   - 保证同源前端继续工作
2. 复跑：
   - `python3 -m pytest tests/unit/test_app_server.py -k "loopback_host or wildcard_cors" -v`
   - `python3 -m pytest tests/unit/test_web_smoke.py -v`

## Task 6：先写 job_runner 持久化失败测试

**Files:**
- Modify: `tests/unit/test_job_runner.py`

**TDD:**
1. 新增失败测试：
   - `test_job_is_persisted_to_disk`
   - `test_runner_restores_jobs_from_disk`
   - `test_restored_running_job_becomes_interrupted`
2. 跑：
   - `python3 -m pytest tests/unit/test_job_runner.py -k "persisted_to_disk or restores_jobs_from_disk or interrupted" -v`
3. 确认失败，再进入 Task 7

## Task 7：实现 job_runner 最小持久化

**Files:**
- Modify: `app/job_runner.py`

**TDD:**
1. 最小实现：
   - 可配置 jobs 目录
   - create/update/log/artifact 时原子写 JSON
   - 初始化时加载历史 job
   - `queued/running` 恢复成 `interrupted`
2. 复跑：
   - `python3 -m pytest tests/unit/test_job_runner.py -v`

## Task 8：先写 watcher 扫描兜底失败测试

**Files:**
- Create or Modify: `tests/unit/test_watcher.py` 或 `tests/unit/test_cli.py`

**TDD:**
1. 新增失败测试：
   - `test_scan_finds_new_stable_wav_without_event`
   - `test_scan_ignores_file_until_stable`
   - `test_watch_runs_in_scan_only_mode_without_watchdog`
2. 跑：
   - `python3 -m pytest tests/unit/test_watcher.py -v`
3. 确认失败，再进入 Task 9

## Task 9：实现 watcher 扫描兜底

**Files:**
- Modify: `src/openmy/services/watcher.py`

**TDD:**
1. 最小实现：
   - 抽出扫描器状态
   - 文件稳定性判断
   - 监听 + 扫描双通道
   - watchdog 缺失时纯扫描模式
2. 复跑：
   - `python3 -m pytest tests/unit/test_watcher.py -v`

## Task 10：拆薄 CLI

**Files:**
- Modify: `src/openmy/cli.py`
- Create: `src/openmy/commands/common.py`
- Create: `src/openmy/commands/run.py`
- Create: `src/openmy/commands/context.py`
- Create: `src/openmy/commands/correct.py`
- Tests: `tests/unit/test_cli.py`

**TDD:**
1. 保持已有 CLI 测试先绿
2. 在不改命令 contract 的前提下，把 `quick-start / run / context / correct` 抽出去
3. 复跑：
   - `python3 -m pytest tests/unit/test_cli.py -v`

## Task 11：拆薄 server

**Files:**
- Modify: `app/server.py`
- Create: `app/http_handlers.py`
- Create: `app/http_responses.py`
- Create: `app/payloads.py`
- Create: `app/pipeline_api.py`
- Tests: `tests/unit/test_app_server.py`, `tests/unit/test_web_smoke.py`

**TDD:**
1. 先确保现有 server 测试仍覆盖 contract
2. 抽离 handler / payload / response 逻辑
3. 复跑：
   - `python3 -m pytest tests/unit/test_app_server.py -v`
   - `python3 -m pytest tests/unit/test_web_smoke.py -v`

## Task 12：全量验证与人工检查

**Files:**
- Verify only

**Verify:**
1. 跑：
   - `python3 -m pytest tests/unit/test_cli.py -v`
   - `python3 -m pytest tests/unit/test_app_server.py -v`
   - `python3 -m pytest tests/unit/test_job_runner.py -v`
   - `python3 -m pytest tests/unit/test_web_smoke.py -v`
   - `python3 -m pytest tests -q`
2. 人工检查：
   - `python3 -m openmy --help`
   - `README.md` 的 quick-start 与服务地址表述
   - 如有条件，再做一次 `python3 app/server.py` 本地启动 smoke

## 独立代码审查

实现完成后补一轮 reviewer：

1. spec review：是否满足用户给的 5 件事和验收项
2. quality review：是否有多余设计、死代码、过度抽象

## 封口条件

- `quick-start` 出现在帮助里并可复用主链
- README 主入口和 CLI 一致
- server 默认只绑本机且不再回 `*`
- job 重启可恢复，旧 running/queued 变 `interrupted`
- watcher 无事件也能补捞稳定 `.wav`
- `python3 -m pytest tests -q` 全绿
