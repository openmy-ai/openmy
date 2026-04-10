# OpenMy Correction Apply

## 用途

把用户的纠错反馈落成 append-only 修正事件，例如关闭 loop、排除误判、合并项目。

## 触发条件

- 用户说“这不是项目”
- 用户说“这个已经做完了”
- 用户说“这条待办不重要”
- 用户说“这两个项目该合并”

## 执行动作

- `openmy skill correction.apply --op close-loop --arg "任务标题" --json`

## 禁止事项

- 不要直接编辑纠错历史文件
- 不要直接改上下文快照
- 不要跳过动作契约去调用内部实现

## 输出说明

- 先读 `human_summary`
- 再确认 `data.op` 和 `data.args`
- 如需刷新当前上下文视图，再转到 openmy-context-read
