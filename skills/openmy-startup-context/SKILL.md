# OpenMy Startup Context

## 用途

新对话启动时，先拉取当前上下文和整体状态，给后续子 Skill 选路。

## 触发条件

- 每次新对话
- 需要先知道最近主要推进什么、有没有 stale loop、当前主问题是什么

## 执行动作

- `openmy skill context.get --level 0 --json`
- `openmy skill status.get --json`

## 禁止事项

- 不要要求用户手动输入命令
- 不要跳过总 Skill 直接改内部状态文件
- 不要直接读取或覆盖原始证据文件

## 输出说明

- 优先用 `human_summary` 给出一句话启动摘要
- 如果任务还不明确，转到 openmy-status-review
- 如果已经明确要读状态细节，转到 openmy-context-read
