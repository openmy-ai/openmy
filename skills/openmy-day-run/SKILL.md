# OpenMy Day Run

## 用途

处理新音频、补跑某天、重跑某天的数据流。

## 触发条件

- 用户给了音频
- 用户要求重跑某天
- 用户要求补齐某天日报或结构化结果

## 执行动作

- `openmy skill day.run --date YYYY-MM-DD --audio path/to/audio.wav --json`

## 禁止事项

- 不要直接调内部 Python 模块
- 不要要求用户自己在终端里拼命令
- 不要直接修改当天的原始证据文件

## 输出说明

- 先读 `human_summary`
- 再看 `data.run_status`
- 如果返回 `error_code=missing_stt_key`，提醒用户当前项目 `.env` 里还没接入语音转写 KEY；如果用户选择 API 转写，就让 Agent 提醒他补这个 key
- 如果用户只是想看结果而不是重跑，转到 openmy-day-view
