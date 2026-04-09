# OpenMy Frontend Parity Design

日期：2026-04-09

## 目标

把 OpenMy 前端从“结果浏览器”补到“本地工作台”：

- 前端可查看 `active_context`
- 前端可查看日级结构化提取结果
- 前端可操作 loop / project / decision 纠正
- 前端可触发现有管线并看到状态
- 不改技术栈，不重写业务逻辑

## 这版故意不做的事

- 不上 React / Vue
- 不做 LLM 对话问答页
- 不做设置面板 / API Key 管理
- 不做手机录音上传入口
- 不做远程部署和认证

## 现状问题

1. 前端只覆盖 `timeline / briefing / search / typo correction`
2. `active_context.json` 没有前端入口
3. 日级提取层 `{date}.meta.json` 没有真正接上
4. loop / project / decision correction 只能走 CLI
5. 长任务无法从前端触发，也没有进度态
6. 移动端未适配
7. 默认日期会被未来测试目录污染

## 核心原则

1. **CLI / 服务层仍是事实来源**
   - 前端不复制 `run / clean / distill / context` 的业务逻辑
   - 前端只负责触发、展示、确认、回写

2. **页面分块独立降级**
   - 某一块缺数据，只影响该卡片
   - 整页不能因为一个 JSON 缺失就白屏

3. **功能补齐优先于重构**
   - 先露出后端已有能力
   - 再谈更重的框架化重构

## 页面信息架构

### 1. Overview

数据源：`data/active_context.json`

展示：
- 当前状态摘要
- 今日重点
- 活跃项目
- open loops
- 最近决定
- 今日状态 / 最近处理日期

### 2. Day Workspace

数据源：
- `data/YYYY-MM-DD/transcript.md`
- `data/YYYY-MM-DD/scenes.json`
- `data/YYYY-MM-DD/{date}.meta.json`
- `data/YYYY-MM-DD/daily_briefing.json`

展示：
- 日报总览
- 时段块
- 时间线
- 结构化提取（events / intents / facts / decisions / todos / insights）
- 原文与场景详情

### 3. Corrections

数据源：
- `corrections.json`
- `active_context` correction 流

动作：
- typo correction
- close loop
- reject loop
- merge project
- reject project
- reject decision

### 4. Pipeline

能力：
- 触发 `clean / roles / distill / briefing / context / run`
- 显示任务状态
- 展示当前步骤、日志、结果文件

## 后端边界

保留 `app/server.py` 作为 HTTP 入口，但补齐两类 API：

### 读接口

- `GET /api/context`
- `GET /api/context/loops`
- `GET /api/context/projects`
- `GET /api/context/decisions`
- `GET /api/date/:date`
- `GET /api/date/:date/meta`
- `GET /api/date/:date/briefing`
- `GET /api/pipeline/jobs`
- `GET /api/pipeline/jobs/:job_id`

### 写接口

- `POST /api/correct/typo`
- `POST /api/context/loops/close`
- `POST /api/context/loops/reject`
- `POST /api/context/projects/merge`
- `POST /api/context/projects/reject`
- `POST /api/context/decisions/reject`
- `POST /api/pipeline/jobs`

## 任务执行策略

长任务统一走轻量 job 模型：

- `job_id`
- `kind`
- `target_date`
- `status`
- `current_step`
- `log_lines`
- `started_at`
- `finished_at`
- `artifacts`

执行模型：

1. 前端创建任务
2. 服务端后台执行现有 OpenMy 能力
3. 前端轮询任务状态
4. 完成后刷新对应数据块

## 数据流

### 读流

1. 页面启动
   - 读 Overview 数据
   - 读日期列表
   - 选中默认日期
2. 切到某天
   - 并行读 day / meta / briefing
3. 切到 Corrections / Pipeline
   - 各自单独请求，不互相阻塞

### 写流

1. typo correction
   - 更新词典
   - 视情况替换 transcript
   - 刷新当前天
2. context correction
   - 追加 correction event
   - 重跑 `openmy context`
   - 刷新 Overview / Corrections
3. pipeline action
   - 创建 job
   - 轮询状态
   - 成功后刷新对应区域

## 错误处理

- 缺 `daily_briefing.json`：显示“尚未生成”+ 触发按钮
- 缺 `{date}.meta.json`：显示“暂无提取结果”+ 提取入口
- 长任务失败：显示最后步骤 + 最近日志
- 状态修改类动作：操作前确认
- 页面级禁止白屏：卡片局部报错，其他区块照常渲染

## 关键修正项

### 1. meta 文件命名接轨

现有前端查的是 `meta.json`，真实产物是 `{date}.meta.json`。这一步必须先修，否则提取层永远缺席。

### 2. 默认日期策略

默认日期不能优先落到未来测试日期。策略建议：

- 默认优先最近“非未来日期”
- 若全是未来日期，再回退排序第一项

### 3. 响应式骨架

移动端至少做到：

- 双栏改单栏
- 侧边栏折叠为顶部摘要 / drawer
- Pipeline / Corrections / Overview 卡片可顺序堆叠

## 测试策略

### 单元测试

- server 读接口 payload 组装
- meta 文件路径解析
- 默认日期选择
- correction 写接口
- job 状态流转

### 集成测试

- 启动本地 server 后，关键接口可返回预期 JSON
- 任务创建后状态可轮询
- correction 后上下文可刷新

### 前端 smoke

- Overview 渲染
- Day Workspace 渲染 meta + briefing
- Pipeline 任务状态可见
- 移动端截图不再是桌面硬压缩

## 交付完成定义

- 前端能看 `active_context`
- 前端能看 `{date}.meta.json`
- 前端能做 loop / project / decision 纠正
- 前端能触发至少 `context / briefing / run`
- 默认日期不被测试数据污染
- 移动端基本可用
