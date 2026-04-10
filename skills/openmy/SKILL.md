---
name: openmy
description: 总 Skill。用在 OpenMy 相关任务的路由、禁令和统一交互原则判断，不直接承担具体工作流执行。
---

# OpenMy 总 Skill

OpenMy 的主架构固定为：

**个人上下文引擎 + 总 Skill 编排层 + 子 Skill 工作流层 + CLI 执行层 + 前端展示层。**

这里的 OpenMy 本体负责状态、证据、管线和纠错；Skill 负责路由和编排；CLI 只负责执行；前端只给用户看。  
**不要把 OpenMy 写成 MCP。**

产品与接口参考：
- `references/architecture.md`
- `references/action-contracts.md`
- `references/routing-rules.md`

## 什么时候触发

- 任务和 OpenMy 的上下文读取、单日处理、状态盘点、纠错闭环相关
- 需要决定“现在该读哪个子 Skill”
- 需要先定禁令，避免直接碰内部文件和内部 Python 模块

## 路由规则

- 新对话启动、要先知道最近状态：读 openmy-startup-context
- 要回答“我最近在干什么 / 重点是什么 / 有哪些待办”：读 openmy-context-read
- 要处理新音频、重跑某天、补一天的数据流：读 openmy-day-run
- 要查看某天日报、时间线、提取结果：读 openmy-day-view
- 要修正项目、关闭 loop、排除误判：读 openmy-correction-apply
- 任务不明确、先想盘整体：读 openmy-status-review

## 全局禁令

- 不要要求用户输入终端命令
- 不要跳过 `openmy skill <action> --json` 直接调用内部 Python 模块
- 不要直接编辑 `active_context.json`、`corrections.jsonl`、`scenes.json`、`meta.json`
- 不要把前端当成 Skill 执行面
- 不要把 MCP 作为本项目主架构的一部分

## 统一交互原则

- 先判断任务类型，再路由到单一子 Skill
- 子 Skill 只做一类工作流，不补产品大背景
- 不明确时先走 openmy-status-review，再决定后续子 Skill
- 对用户回复时优先使用返回里的 `human_summary`
