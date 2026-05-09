# OpenMy 僵尸 worktree 审计（2026-05-09）

## 审计范围和方法

- 基线：`/Users/zhousefu/projects/openmy`，当前为远端 `origin/main` 的干净副本，提交 `18b543a`。
- 审计对象：`~/.codex/worktrees/{1e62,1e67,8058,8285,d398,d94b,f6f7,fb9b}/openmy-clean`。
- 对比命令：`diff -rq -x .git -x .venv -x __pycache__ -x node_modules <baseline> <worktree>`。
- 额外校验：过滤 `.git/.venv/__pycache__/node_modules` 后，8 个 worktree 内容逐字节一致；差异清单也逐行一致。

## 总结论

8 个目录不是 8 份不同工作，而是同一份旧工作区的 8 个断根副本。它们都包含一组未进入当前远端主线的真实代码：卡片内联回听、旧音频路径容错、VAD 小切片、前端请求超时、哈希路由、若干本地化 UI 收敛。保留一个目录作为抢救源即可；本报告用 `d398` 作为代表源，其余 7 个没有独有价值。

## 公共 diff -rq 清单（8 个 worktree 完全相同）

> 下方 `WT` 代表任意一个被审计的 worktree；实际 8 个目录输出一致。

```text
Only in baseline: .claude
Only in baseline: .gstack
Files baseline/.planning/PROJECT.md and WT/.planning/PROJECT.md differ
Files baseline/.planning/REQUIREMENTS.md and WT/.planning/REQUIREMENTS.md differ
Files baseline/.planning/ROADMAP.md and WT/.planning/ROADMAP.md differ
Files baseline/.planning/STATE.md and WT/.planning/STATE.md differ
Files baseline/app/audio_api.py and WT/app/audio_api.py differ
Files baseline/app/index.html and WT/app/index.html differ
Files baseline/app/static/app.js and WT/app/static/app.js differ
Only in WT/app/static/css: inline-review.css
Files baseline/app/static/css/sidebar.css and WT/app/static/css/sidebar.css differ
Files baseline/app/static/css/tokens.css and WT/app/static/css/tokens.css differ
Files baseline/app/static/modules/api.js and WT/app/static/modules/api.js differ
Files baseline/app/static/modules/context.js and WT/app/static/modules/context.js differ
Files baseline/app/static/modules/daily.js and WT/app/static/modules/daily.js differ
Files baseline/app/static/modules/home.js and WT/app/static/modules/home.js differ
Only in WT/app/static/modules: inline-review.js
Files baseline/app/static/modules/router.js and WT/app/static/modules/router.js differ
Files baseline/app/static/modules/state.js and WT/app/static/modules/state.js differ
Files baseline/app/static/modules/subtitle-overlay.js and WT/app/static/modules/subtitle-overlay.js differ
Files baseline/src/openmy/services/ingest/audio_pipeline.py and WT/src/openmy/services/ingest/audio_pipeline.py differ
Files baseline/src/openmy/services/query/context_query.py and WT/src/openmy/services/query/context_query.py differ
Files baseline/tests/unit/test_app_server.py and WT/tests/unit/test_app_server.py differ
Files baseline/tests/unit/test_web_smoke.py and WT/tests/unit/test_web_smoke.py differ
```

## 逐个 worktree 结论

### d398

**未合并差异文件清单**：见上方公共 `diff -rq` 清单，24 条。

**关键差异摘要**
- 新增卡片内联回听：`inline-review.js/css`，把日报卡片内直接展开句子、波形、播放、纠错入口。
- 音频接口增加旧路径容错：当历史 `chunk_path` 指向已删除的 `openmy-clean` 时，按文件名回落到当天 `stt_chunks`。
- 转写管道增加 VAD 合并切片：按人声段生成 30-90 秒小切片，并带上偏移字段。
- 前端请求封装增加 4 秒超时和超时提示。
- 前端哈希路由增加 `date/weekly/monthly/start` 的直接恢复能力。
- UI 去掉 Google Font 依赖和部分 emoji/图片图标，偏向本地化、朴素文本。
- 查询分类修正英文词误判，避免把普通单词里的 `open/done/person` 子串误当查询类型。
- `.planning/*` 是旧计划文档差异，不是可交付代码。

**价值判断**：真工作（未合并，建议作为唯一抢救源）。

**处置建议**
- 直接抢救并补测：`app/audio_api.py`、`tests/unit/test_app_server.py`、`src/openmy/services/query/context_query.py`。
- 开新分支评估后抢救：`app/static/modules/inline-review.js`、`app/static/css/inline-review.css`，以及它们在 `app/index.html`、`app/static/app.js`、`app/static/modules/daily.js`、`app/static/modules/subtitle-overlay.js`、`app/static/modules/router.js`、`app/static/modules/state.js` 里的接线。
- 只参考不整文件覆盖：`src/openmy/services/ingest/audio_pipeline.py`、`app/static/modules/api.js`；这两处会影响转写稳定性和长请求体验，需要重新做小步实现。
- 不抢救：`.planning/*`、单纯去 emoji/字体的 UI 文案差异，除非老板明确要回到这版视觉。

### 1e62

**未合并差异文件清单**：见上方公共 `diff -rq` 清单，24 条；与 `d398` 逐字节一致。

**关键差异摘要**
- 内容与 `d398` 完全相同，没有独有文件。
- 包含同一套内联回听、旧音频路径容错、VAD 小切片、请求超时、哈希路由差异。
- 这些差异只需要从 `d398` 抢救一次。
- 本目录自身没有额外判断价值。

**价值判断**：无意义（重复副本，不是独立工作）。

**处置建议**：不从该目录抢救；确认 `d398` 已封存或抢救后，可直接 `rm -rf ~/.codex/worktrees/1e62/openmy-clean`。

### 1e67

**未合并差异文件清单**：见上方公共 `diff -rq` 清单，24 条；与 `d398` 逐字节一致。

**关键差异摘要**
- 根目录 `openmy/` 包确实与远端一致，但完整仓库仍有 `app/`、`src/openmy/`、测试和计划文档差异。
- 内容与 `d398` 完全相同，没有独有文件。
- 包含同一套内联回听、旧音频路径容错、VAD 小切片、请求超时、哈希路由差异。
- 这些差异只需要从 `d398` 抢救一次。

**价值判断**：无意义（重复副本，不是独立工作）。

**处置建议**：不从该目录抢救；确认 `d398` 已封存或抢救后，可直接 `rm -rf ~/.codex/worktrees/1e67/openmy-clean`。

### 8058

**未合并差异文件清单**：见上方公共 `diff -rq` 清单，24 条；与 `d398` 逐字节一致。

**关键差异摘要**
- 内容与 `d398` 完全相同，没有独有文件。
- 包含同一套内联回听、旧音频路径容错、VAD 小切片、请求超时、哈希路由差异。
- 这些差异只需要从 `d398` 抢救一次。
- 本目录自身没有额外判断价值。

**价值判断**：无意义（重复副本，不是独立工作）。

**处置建议**：不从该目录抢救；确认 `d398` 已封存或抢救后，可直接 `rm -rf ~/.codex/worktrees/8058/openmy-clean`。

### 8285

**未合并差异文件清单**：见上方公共 `diff -rq` 清单，24 条；与 `d398` 逐字节一致。

**关键差异摘要**
- 内容与 `d398` 完全相同，没有独有文件。
- 包含同一套内联回听、旧音频路径容错、VAD 小切片、请求超时、哈希路由差异。
- 这些差异只需要从 `d398` 抢救一次。
- 本目录自身没有额外判断价值。

**价值判断**：无意义（重复副本，不是独立工作）。

**处置建议**：不从该目录抢救；确认 `d398` 已封存或抢救后，可直接 `rm -rf ~/.codex/worktrees/8285/openmy-clean`。

### d94b

**未合并差异文件清单**：见上方公共 `diff -rq` 清单，24 条；与 `d398` 逐字节一致。

**关键差异摘要**
- 内容与 `d398` 完全相同，没有独有文件。
- 包含同一套内联回听、旧音频路径容错、VAD 小切片、请求超时、哈希路由差异。
- 这些差异只需要从 `d398` 抢救一次。
- 本目录自身没有额外判断价值。

**价值判断**：无意义（重复副本，不是独立工作）。

**处置建议**：不从该目录抢救；确认 `d398` 已封存或抢救后，可直接 `rm -rf ~/.codex/worktrees/d94b/openmy-clean`。

### f6f7

**未合并差异文件清单**：见上方公共 `diff -rq` 清单，24 条；与 `d398` 逐字节一致。

**关键差异摘要**
- 内容与 `d398` 完全相同，没有独有文件。
- 包含同一套内联回听、旧音频路径容错、VAD 小切片、请求超时、哈希路由差异。
- 这些差异只需要从 `d398` 抢救一次。
- 本目录自身没有额外判断价值。

**价值判断**：无意义（重复副本，不是独立工作）。

**处置建议**：不从该目录抢救；确认 `d398` 已封存或抢救后，可直接 `rm -rf ~/.codex/worktrees/f6f7/openmy-clean`。

### fb9b

**未合并差异文件清单**：见上方公共 `diff -rq` 清单，24 条；与 `d398` 逐字节一致。

**关键差异摘要**
- 内容与 `d398` 完全相同，没有独有文件。
- 包含同一套内联回听、旧音频路径容错、VAD 小切片、请求超时、哈希路由差异。
- 这些差异只需要从 `d398` 抢救一次。
- 本目录自身没有额外判断价值。

**价值判断**：无意义（重复副本，不是独立工作）。

**处置建议**：不从该目录抢救；确认 `d398` 已封存或抢救后，可直接 `rm -rf ~/.codex/worktrees/fb9b/openmy-clean`。

## 抢救优先级

### 第一优先级：小修复，可直接摘取后补测

- `app/audio_api.py`
- `tests/unit/test_app_server.py`
- `src/openmy/services/query/context_query.py`

理由：都是小范围修复，用户影响明确；尤其旧音频路径容错直接对应 `openmy-clean` 已删除后的历史数据回放问题。

### 第二优先级：真功能，但不要整文件覆盖

- `app/static/modules/inline-review.js`
- `app/static/css/inline-review.css`
- `app/index.html`
- `app/static/app.js`
- `app/static/modules/daily.js`
- `app/static/modules/subtitle-overlay.js`
- `app/static/modules/router.js`
- `app/static/modules/state.js`
- `tests/unit/test_web_smoke.py`

理由：卡片内联回听是一个完整产品方向，但接线跨多个前端文件；当前远端已经有全屏字幕回看和后续主页改造，不能直接覆盖，只能开新分支按当前主线重新接。

### 第三优先级：只保留思路，不建议直接搬

- `src/openmy/services/ingest/audio_pipeline.py`
- `app/static/modules/api.js`

理由：VAD 小切片会改变转写产物形状，请求超时会影响上传和任务接口；这两项影响范围大，需要独立设计和测试，不适合从僵尸 worktree 整文件抢救。

### 可丢弃

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- 单纯去 Google Font、去 emoji、改卡片文案的视觉差异

理由：这些不是当前远端主线的可靠状态来源，也不是必须抢救的功能代码。

## TL;DR 处置矩阵

| worktree | 处置 |
|---|---|
| `d398` | 抢救 `app/audio_api.py`、`tests/unit/test_app_server.py`、`src/openmy/services/query/context_query.py`；评估内联回听相关文件后删 |
| `1e62` | 删 |
| `1e67` | 删 |
| `8058` | 删 |
| `8285` | 删 |
| `d94b` | 删 |
| `f6f7` | 删 |
| `fb9b` | 删 |
