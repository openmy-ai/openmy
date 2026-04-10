# OpenMy Architecture

## 主定义

OpenMy 是一个**个人上下文引擎**，不是 MCP Server，也不是笔记工具。

它的主架构固定为：

```text
个人上下文引擎
  + 总 Skill 编排层
  + 子 Skill 工作流层
  + CLI 执行层
  + 前端展示层
```

## 五层分工

### 1. 个人上下文引擎

系统中心资产不变：

- `data/active_context.json`
- `data/corrections.jsonl`
- 各天数据目录
- `src/openmy/services/*` 管线

这一层负责状态、证据、管线和纠错。

### 2. 总 Skill 编排层

总 Skill 只负责：

- 判断任务类型
- 选择子 Skill
- 规定执行顺序和禁令

### 3. 子 Skill 工作流层

子 Skill 一次只做一类工作流：

- 启动上下文
- 上下文读取
- 单日处理
- 单日查看
- 纠错闭环
- 状态总览

### 4. CLI 执行层

Agent 稳定后端入口固定为：

```bash
openmy skill <action> --json
```

CLI 只负责执行动作契约，不承载产品定义。

### 5. 前端展示层

`app/` 只给用户看。  
人类入口仍然是 `openmy quick-start`；Agent 入口是 `openmy skill ... --json`。

## 系统中心

```text
active_context.json     ← 当前状态快照
corrections.jsonl       ← append-only 纠错历史
```

所有推断都围绕这两类中心资产聚合和纠偏。

## 当前处理管线

```text
音频
  → ingest
  → cleaning
  → segmentation
  → distillation
  → extraction
  → consolidation
  → active_context / corrections
  → Agent / frontend
```

角色识别代码仍保留在仓库里，但不再是这轮架构定义的中心。

## 仓库落点

```text
src/openmy/
  cli.py
  skill_dispatch.py
  commands/
  services/
  providers/

skills/
  openmy/
  openmy-startup-context/
  openmy-context-read/
  openmy-day-run/
  openmy-day-view/
  openmy-correction-apply/
  openmy-status-review/

app/
  server.py
  index.html
```
