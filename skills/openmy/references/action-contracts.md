# OpenMy Skill Action Contracts

Agent 侧稳定后端入口固定为：

```bash
openmy skill <action> --json
```

当前固定 5 个动作：

```bash
openmy skill context.get --level 0 --json
openmy skill day.get --date YYYY-MM-DD --json
openmy skill day.run --date YYYY-MM-DD --audio a.wav --json
openmy skill correction.apply --op close-loop --arg "任务标题" --json
openmy skill status.get --json
```

成功返回：

```json
{
  "ok": true,
  "action": "context.get",
  "version": "v1",
  "data": {},
  "human_summary": "最近主要推进 OpenMy；当前有 9 个待办未闭环。",
  "artifacts": {},
  "next_actions": []
}
```

失败返回：

```json
{
  "ok": false,
  "action": "day.run",
  "version": "v1",
  "error_code": "missing_audio",
  "message": "没有输入音频，也没有现成 transcript 数据。",
  "hint": "请提供 --audio，或先确认该日期已有数据。"
}
```

`day.run` 如果要走 API 转写但项目 `.env` 里还没接入语音转写 key，会返回：

```json
{
  "ok": false,
  "action": "day.run",
  "version": "v1",
  "error_code": "missing_stt_key",
  "message": "缺少语音转写 KEY。",
  "hint": "如果你要走 API 转写，请在当前项目根目录 `.env` 填 `GEMINI_API_KEY` 或 `OPENMY_STT_API_KEY`；如果你是通过 Skill 接入，让 Agent 提醒你补这个 key。"
}
```

硬规则：

- `--json` 输出只允许 JSON，不混入 Rich 面板、颜色、Markdown 标题
- `action` 与 `version` 必须稳定
- 每个成功结果都必须带 `human_summary`
- 子 Skill 只能调这里列出的稳定动作，不碰内部模块
