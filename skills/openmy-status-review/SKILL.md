# OpenMy Status Review

## 用途

先盘整体状态，再决定接下来要走哪个子 Skill。

## 触发条件

- 任务不明确
- 需要先看最近哪些天缺数据
- 需要判断当前闭环情况和下一步优先级

## 执行动作

- `openmy skill status.get --json`

## 禁止事项

- 不要直接跑单日处理
- 不要直接做纠错写入
- 不要替代总 Skill 做长期产品定义

## 输出说明

- 用 `human_summary` 先给总览
- 再从 `data.items` 里看具体日期状态
- 盘完后再转到 openmy-context-read、openmy-day-run 或 openmy-day-view
