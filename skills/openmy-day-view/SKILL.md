# OpenMy Day View

## 用途

读取某天日报、时间线、场景和提取结果，不重新处理数据。

## 触发条件

- 用户要看某天日报
- 用户要看某天时间线或提取结果
- Agent 需要确认某天已有产物

## 执行动作

- `openmy skill day.get --date YYYY-MM-DD --json`

## 禁止事项

- 不要自动触发重跑
- 不要直接修改当天数据目录
- 不要把查看动作升级成处理动作

## 输出说明

- 优先读 `human_summary`
- 再从 `data.status`、`data.briefing`、`data.scenes` 里取细节
- 如果发现当天缺产物，再转到 openmy-day-run
