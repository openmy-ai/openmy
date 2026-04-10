# OpenMy Beta Entry & Local Boundary Design

日期：2026-04-10

## 背景

这轮目标不是继续加能力，而是把 OpenMy 的 Beta 基础盘收稳：

- README 说出来的入口，要和真实 CLI 能跑的入口一致
- 本地网页默认边界，要回到“本机默认安全”
- CLI / server 要从“继续堆功能会越来越难改”过渡到“还能继续长”
- pipeline 工作台要有最小可恢复性
- watcher 要从“只靠事件”变成“监听优先、扫描托底”

## 用户给定约束

- 不做产品重设计
- 不改输出格式
- 不碰新的大功能
- 不顺手做更聪明的提取逻辑
- 优先级顺序明确：`quick-start` → 本地网页边界 → `cli.py` / `server.py` 拆薄 → `job_runner` 持久化 → `watcher` 兜底

## 方案比较

### 方案 A：只补行为，不整理结构

做法：
- 在现有 `src/openmy/cli.py` 和 `app/server.py` 上继续叠 `quick-start` / host / CORS / persistence / watcher fallback

优点：
- 短期最快

缺点：
- 把两个已经偏重的文件继续做胖
- 这轮能过，下一轮继续难改

### 方案 B：边修边做最小结构整理

做法：
- 先补真实行为
- 同一轮里把 CLI 和 server 拆成“入口层 + 具体逻辑层”
- 只拆这轮相关区域，不动其他成熟命令

优点：
- 行为对齐和结构降压一起完成
- 符合用户给的阶段目标

缺点：
- 改动面比方案 A 大
- 需要更强的测试兜底

### 方案 C：先做大重构，再补行为

做法：
- 先把 CLI / server 全量模块化，再回填 `quick-start`、host、persistence、watcher

优点：
- 结构最干净

缺点：
- 明显超出本轮约束
- 风险高，容易把成熟路径一并带崩

## 选型

选 **方案 B**。

原因：
- 它能满足用户要求的“这次就收这 5 件事”
- 不会像方案 A 那样继续透支结构
- 又不会像方案 C 那样把任务扩成大重构

## 设计结论

### 1. CLI 入口契约

保留 `openmy = "openmy.cli:main"`，但把 `main` 改成真正的“参数解析 + 命令调度”入口。

新增正式子命令：
- `openmy quick-start <audio_path>`

`quick-start` 的职责：
- 校验输入音频存在
- 从文件名推断日期，支持 `YYYY-MM-DD` / `YYYYMMDD`
- 自动加载项目根目录 `.env`
- 校验依赖：Python 版本、`ffmpeg`、`ffprobe`、`.env`、`GEMINI_API_KEY`
- 复用现有 `run` 主链
- 处理完成后启动本地网页并打开浏览器

这里不再复制一套“转写 → 清洗 → 角色 → 蒸馏 → briefing → extract → context”的实现，全部落回 `run` 和 server 启动逻辑。

### 2. CLI 分层

本轮最小拆分目标：

- `src/openmy/cli.py`
  - 保留 `main()`、`build_parser()`、分发入口
- `src/openmy/commands/run.py`
  - `run` / `quick-start` / 音频时间推断 / 环境自检
- `src/openmy/commands/context.py`
  - `context`
- `src/openmy/commands/correct.py`
  - `correct` 相关
- `src/openmy/commands/common.py`
  - 公共 path/json/date/console helper

原则：
- 只拆高频和本轮必改命令
- 其他命令行为不改，只调整落点

### 3. 本地网页边界

默认服务启动行为改成：

- host 默认 `127.0.0.1`
- port 仍默认 `8420`
- 若用户显式传 `--host 0.0.0.0` 才允许广域监听

CORS 策略改成：

- 同源页面访问同源接口时，不主动放开 `*`
- 默认不再返回 `Access-Control-Allow-Origin: *`
- `OPTIONS` 仅在本机来源需要时返回本机地址白名单，或更简单地只返回 methods / headers

### 4. server 分层

本轮最小拆分目标：

- `app/server.py`
  - 启动入口
  - 参数解析
  - HTTPServer 装配
- `app/http_handlers.py`
  - `BrainHandler`
- `app/http_responses.py`
  - JSON / HTML / error helpers
- `app/payloads.py`
  - context/date/stats/pipeline payload 读取与组装
- `app/pipeline_api.py`
  - pipeline job 创建和查询

原则：
- 路由 contract 保持不变
- 只抽逻辑，不重写接口语义

### 5. job_runner 最小持久化

存储方案：
- `data/runtime/jobs/<job_id>.json`

记录字段继续沿用当前 `JobRecord`：
- `job_id`
- `kind`
- `target_date`
- `status`
- `current_step`
- `log_lines`
- `started_at`
- `finished_at`
- `artifacts`
- `error`

恢复策略：
- 启动时扫描 job 目录
- JSON 解析失败的坏文件跳过并记录
- 状态是 `queued` 或 `running` 的历史 job，在加载时统一改为 `interrupted`

写入策略：
- 每次状态变化后原子写回，避免崩溃留下半文件

### 6. watcher 兜底

保留：
- watchdog `Observer` 事件监听

新增：
- 目录扫描器
- 维护 `path -> (size, mtime, stable_rounds)` 快照

触发规则：
- 发现新 `.wav`
- 连续两轮大小和 mtime 不变
- 文件名可解析出日期
- 还没进过本轮 pending

降级策略：
- 如果 `watchdog` 导入失败，仍进入纯扫描模式

### 7. README 修正

README 保留“30 秒快速开始”的产品叙事，但前提是代码真能兑现。

具体修正：
- `openmy quick-start` 变成真实入口
- 服务地址描述统一为 `http://127.0.0.1:8420`
- 流程图不再用会裸露源码的半成品方式；优先保留 Mermaid，若本地检查发现显示问题，则降级为静态图/普通流程列表

## 数据流

### quick-start

1. 用户传入一个音频路径
2. CLI 解析日期
3. CLI 加载 `.env` 并做人话依赖校验
4. CLI 调 `run`
5. `run` 复用现有主链处理数据
6. CLI 启动/确认本地服务
7. CLI 打开浏览器到同源页面

### pipeline job

1. 前端创建 job
2. server 调 `JobRunner.create_job`
3. `JobRunner` 立刻落盘 queued 状态
4. worker 线程执行，状态持续写回
5. 服务重启后重载历史 job
6. 旧 running job 统一变 `interrupted`

### watcher

1. 事件监听优先记录候选文件
2. 扫描器补捞未收到事件的 `.wav`
3. 文件稳定后才入 pending
4. 按日期批处理触发 `openmy run`

## 错误处理策略

- 缺 `.env`：提示“先在项目根目录创建 `.env`，至少写入 `GEMINI_API_KEY=...`”
- 缺 key：提示“检测到 `.env`/环境变量里没有 `GEMINI_API_KEY`”
- 缺 `ffmpeg` / `ffprobe`：分别提示安装命令
- 浏览器打开失败：不视为主流程失败，只提示手动访问本地地址
- job 文件损坏：跳过坏文件，其他任务照常加载
- watcher 无 `watchdog`：输出降级说明，但仍继续运行扫描模式

## 测试策略

### CLI
- `--help` 中出现 `quick-start`
- `quick-start` 能把音频路径转成内部 `run` 调用
- 缺依赖时报中文人话

### server
- 默认 host 是 `127.0.0.1`
- 默认 JSON 响应不再带 `Access-Control-Allow-Origin: *`
- 同源页面和接口仍能正常工作

### job_runner
- 任务创建后落盘
- 重建 runner 后可读回
- 旧 running/queued job 恢复为 `interrupted`

### watcher
- 丢事件也能在扫描里发现新文件
- 写入未稳定文件不会提前触发
- 无 watchdog 时仍能跑纯扫描模式

## 认可条件

这份设计直接以用户给出的详细任务单为批准依据：
- 范围已固定
- 提交顺序已固定
- 验收标准已固定

因此本轮不再单独等待“设计批准”回合，直接进入实现计划和 TDD 执行。
