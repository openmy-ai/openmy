# OpenMy Context Read

## 用途

回答“最近在干什么”“今天重点是什么”“有哪些待办”这类只读问题。

## 触发条件

- 用户要最近状态
- 用户要当前重点、待办、项目概览
- Agent 需要把上下文翻成人话回复

## 执行动作

- `openmy skill context.get --level 1 --json`

## 禁止事项

- 不要顺手做纠错写入
- 不要直接编辑上下文快照
- 不要跳去跑单日处理流程

## 输出说明

- 优先使用 `human_summary`
- 必要时展开 `data.snapshot`
- 如果用户开始纠错，转到 openmy-correction-apply
