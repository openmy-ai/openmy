# OpenMy Routing Rules

总 Skill 只负责判断任务类型和路由，不负责执行细节。

路由固定如下：

| 任务意图 | 子 Skill |
|---|---|
| 新对话启动，先知道最近状态 | openmy-startup-context |
| 回答“最近在干什么 / 今天重点 / 待办有哪些” | openmy-context-read |
| 跑一天、补一天、重跑一天 | openmy-day-run |
| 看一天的结果，不重新处理 | openmy-day-view |
| 纠错、关闭 loop、排除误判 | openmy-correction-apply |
| 先盘整体状态再决定下一步 | openmy-status-review |

禁令：

- 不要让总 Skill 直接承担 workflow 执行
- 不要在总 Skill 里堆具体命令示例和产品背景长文
- 不要新增 MCP 主链说明
- 不要把旧 `openmy agent` 当主入口；它只是兼容别名
