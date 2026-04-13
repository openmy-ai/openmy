# Codex 任务：OpenMy PR1 — Drop Zone + 进度面板

> 优先级：🔴 最高 | 目标分支：main | 工作目录：/Users/zhousefu/Desktop/openmy-clean

## 背景

OpenMy Web UI（`localhost:8420`）需要一个实时进度面板，解决"用户转写20分钟盯着空白页面就卸了"的留存问题。同时增加 Drop Zone 让用户直接拖入音频文件。

设计已定稿。有可交互 HTML mockup 可参考。

## 参考资料（先读这些）

1. **设计 spec**：`/Users/zhousefu/Desktop/openmy-final-check/docs/specs/2026-04-14-smart-inlet-design.md`（重点看模块 5：实时进度面板）
2. **前端 mockup（可交互）**：`/Users/zhousefu/Desktop/openmy-final-check/docs/mockups/progress-panel.html`
3. **首页嵌入演示**：`/Users/zhousefu/Desktop/openmy-final-check/docs/mockups/progress-in-homepage.html`
4. **现有后端**：`/Users/zhousefu/Desktop/openmy-clean/app/job_runner.py`（JobRunner 已有 set_step/log）
5. **现有前端**：`/Users/zhousefu/Desktop/openmy-clean/app/static/app.js` + `style.css` + `index.html`
6. **现有 API**：`/Users/zhousefu/Desktop/openmy-clean/app/pipeline_api.py`

## 实现清单

### 后端改动

#### 1. 扩展 `app/job_runner.py`
- `JobHandle` 新增 `set_steps(steps: list)` 支持阶段追踪
- 新增 `pause()`, `resume()`, `cancel()`, `skip_step()` 控制方法
- `to_dict()` 输出新增字段：`steps`, `progress_pct`, `eta_seconds`, `source_file`, `can_pause`, `can_skip`
- Step 数据结构见 spec 模块 5

#### 2. 新增 API 端点（`app/pipeline_api.py`）
- `POST /api/upload` — 接收 multipart 音频，存到 `data/inbox/{timestamp}_{filename}`，返回 `{ file_path, size_bytes }`，limit 500MB
- `POST /api/pipeline/jobs/{id}/pause`
- `POST /api/pipeline/jobs/{id}/resume`
- `POST /api/pipeline/jobs/{id}/skip`
- `POST /api/pipeline/jobs/{id}/cancel`

#### 3. 修改 `POST /api/pipeline/jobs`
- 新增 `audio_files` 参数，支持 Web UI 直接指定文件路径

#### 4. Pipeline 阶段调用
在 pipeline 各阶段（转写→清洗→场景切分→蒸馏）调用 `handle.step()`，传入：
- `name`: transcribe / clean / segment / distill
- `label`: 转写 / 清洗 / 场景切分 / 蒸馏
- `result_summary`: 人话描述，如 "检测到 3 段对话"、"去掉 47% 噪音"

### 前端改动

#### 5. 修改 `app/static/app.js` — 首页状态机
```
页面加载 → GET /api/pipeline/jobs
  ├── 有活跃 job → 显示进度面板（1秒轮询刷新）
  └── 无活跃 job → 显示 Drop Zone
       ├── 用户拖入文件 → POST /api/upload → POST /api/pipeline/jobs → 进度面板出现
       └── 有历史日期 → 正常渲染日期列表
```

#### 6. 进度面板 UI（从 mockup 移植）
参照 `progress-panel.html` 的设计，实现：
- 4 阶段步骤可视化：✅ 完成 / 🔄 进行中（转圈动画）/ ⬜ 等待
- 总进度条 + 百分比 + ETA
- 人话结果摘要（不是"完成"，是"检测到 3 段对话"）
- 实时日志滚动（最新在上，出错变红）
- 操作按钮：暂停 / 取消 / 跳过当前步骤
- 完成状态：自动显示"查看日报"按钮
- 复用 OpenMy 现有设计语言（色板、字体、暗色模式支持）

#### 7. Drop Zone UI
- 虚线边框区域
- 拖入时高亮
- 支持点击浏览文件
- 接受格式：.wav .mp3 .m4a .aac .mp4 .mov .flac .ogg .webm

#### 8. 修改 `app/static/style.css`
- 新增 Drop Zone 样式
- 新增进度面板样式（从 mockup 的 CSS 移植）

## 不要做的事

- 不要改 CLI（cli.py / commands/）
- 不要动 STT provider 层
- 不要加新依赖到 pyproject.toml
- 不要改 README
- 不要做 inbox watch / 设备检测（那是 PR2/PR3）

## 测试要求

1. 单元测试：`JobRunner` steps 字段正确流转
2. 单元测试：progress_pct 和 eta_seconds 计算
3. 单元测试：upload API 接受/拒绝各种文件格式
4. 单元测试：pause/resume/cancel/skip 状态转换
5. 现有测试必须全部通过：`python3 -m pytest tests/ -q`

## 验证步骤

完成后逐步验证：
1. 打开 `http://localhost:8420/`
2. 确认首页显示 Drop Zone（无活跃任务时）
3. 拖入一个小 WAV 文件（<1MB）
4. 确认上传成功、pipeline 启动、进度面板出现
5. 确认进度面板实时更新（步骤推进、百分比增长）
6. 确认 pipeline 完成后面板显示完成状态 + "查看日报"按钮
7. 点击"查看日报"，确认跳转正确

## Git 规范

- Commit messages 用英文 Conventional Commits
- 建议按功能拆成多个 commit（后端 → 前端 → 测试）
