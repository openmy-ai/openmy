# Codex 任务：OpenMy PR1.5 — CEO Review 增量

> 优先级：🟡 高 | 前置：PR1 合并后执行 | 工作目录：/Users/zhousefu/Desktop/openmy-clean

## 背景

PR1（Drop Zone + 进度面板）是基础框架。本 PR 追加 CEO Review 的增强 + 产品洞察，把"能用"升级为"想用"。

## 依赖 PR1 已完成的能力

- `POST /api/upload` 已实现
- `POST /api/pipeline/jobs` 支持 `audio_files` 参数
- 进度面板 UI 已嵌入首页
- JobRunner 支持 steps/progress

---

## 第一部分：技术增强（6 项）

### 1. Opus 压缩替代 MP3（架构级别变更）

**真机测试数据（247 MB WAV, DJI Mic）：**
- MP3: 7.4 MB, 22 秒
- **Opus 32k: 6.4 MB, 8.7 秒（更小且快 2.5 倍）**

#### 改动 1a：`POST /api/upload` 追加压缩逻辑
- 上传后不存原文件，用 ffmpeg 压缩到 inbox：
  ```bash
  ffmpeg -y -i input -ac 1 -ar 16000 -c:a libopus -b:a 32000 ~/.openmy/inbox/{timestamp}_{name}.ogg
  ```
- 返回增加字段：`original_size`, `compressed_size`, `duration_seconds`

#### 改动 1b：`audio_pipeline.py` 压缩编码切换
- `prepare_audio_chunks()` 中的 `normalize_source()` 函数
- `libmp3lame -qscale:a 4` → `libopus -b:a 32000`
- 输出扩展名 `.mp3` → `.ogg`
- 注意：`SILENCE_FILTER` 保持不变，只改压缩编码器

### 2. 浏览器通知 + 完成提示音

#### 改动 2a：`app.js` — 请求通知权限
- 首次加载页面时 `Notification.requestPermission()`
- 不要弹模态框，用 subtle 提示（如首页底部小字）

#### 改动 2b：`app.js` — 完成回调
- 在 `refreshPipelineJobs()` 中，检测到 job 从 `running` 变为 `succeeded`：
  ```js
  new Notification('OpenMy', { body: '处理完成！点击查看结果', icon: '/static/icons/logo.svg' });
  new Audio('data:audio/wav;base64,...').play();  // 短提示音
  ```

### 3. 完成后自动刷新首页数据

#### 改动 3：`app.js` — `refreshPipelineJobs()` 检测完成
- Job `status` 从 `running` 变为 `succeeded` 时：
  1. 重新 `loadSidebar()`（刷新日期列表）
  2. 如果在首页，重新 `renderHomePage()`
  3. 显示 toast："处理完成，今日记录已更新"

### 4. Demo 模式

#### 改动 4a：`POST /api/demo` 端点
- 触发内置 demo 音频的 pipeline
- 复用 `cli.py` 中已有的 demo 逻辑
- 返回 job_id

#### 改动 4b：Drop Zone UI 增加 Demo 按钮
- Drop Zone 底部："没有录音？试试 3 分钟 Demo ▶"
- 点击调用 `POST /api/demo`，显示进度面板

### 5. 时间预估 + 成本提示

#### 改动 5a：`POST /api/upload` 返回预估
- 基于 `duration_seconds` 计算：
  - `estimated_minutes`: duration * 处理倍率（约 0.3x 实时）
  - `estimated_cost_cny`: duration / 60 * 单价（Gemini ~¥0.026/分钟）
- 返回字段：`estimated_minutes`, `estimated_cost_cny`

#### 改动 5b：前端显示预估
- 上传完成后、pipeline 启动前，显示：
  "预计耗时 ~18 分钟 | 预计费用 ¥0.8"
- 用户确认后才启动（或 3 秒后自动启动）

### 6. 智能文件名显示

#### 改动 6：`app.js` — 文件名解析
- `TX01_MIC028_20260413_154517_orig.wav` → "4月13日 15:45 录音"
- 正则：`/TX\d+_MIC\d+_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/`
- 其他文件名保持原样

---

## 第二部分：产品洞察（5 项 — CEO Review 深度思考）

### 7. 🔴 渐进式结果（Progressive Results）

**问题：** 用户拖入文件后等 20 分钟才看到结果。注意力早就走了。

**方案：** 每个 pipeline 步骤完成后，立刻把部分结果推到前端：

```
转写完成（~2分钟） → 立刻显示原始文字（用户马上能开始读！）
清洗完成（~1分钟） → 页面自动更新为清洗版
蒸馏完成（~3分钟） → 摘要出现在顶部
提取完成（~2分钟） → 决策/待办/事件补全
```

**用户感知从等 20 分钟变成等 2 分钟。**

#### 改动 7a：后端 — 每步完成后写中间结果
- `transcribe_audio_files()` 完成后 → 立即写 `transcript.raw.md`
- `clean()` 完成后 → 立即写 `transcript.md`
- `distill()` 完成后 → 立即写 `meta.json` 中的 `daily_summary`
- `extract()` 完成后 → 补全 `meta.json` 的 events/decisions/facts

#### 改动 7b：前端 — 进度面板内嵌预览
- 转写完成后，进度面板下方出现"初步转写"预览（前 500 字）
- 点击可展开全文
- 后续步骤完成后，预览自动升级

### 8. 🔴 今日最值得记住的一句话（Insight Card）

**问题：** 处理完 30 分钟录音，结果页信息太多，用户不知道看哪里。

**方案：** 在 distill 阶段，让 LLM 额外提取"今日最值得记住的一句话"，显示为首页顶部的精美卡片。

#### 改动 8a：后端 — `meta.json` 新增 `highlight_quote` 字段
- distill prompt 追加："请从今天的对话中提取最值得记住的一句原话"
- 写入 `meta.json` 的 `highlight_quote` 字段（含 time, text, project）

#### 改动 8b：前端 — 首页 Insight Card
```html
<div class="insight-card">
  <div class="insight-label">💡 今天最值得记住的</div>
  <blockquote>"我觉得 OpenMy 的价值不在转写，在于让 Agent 读懂我的上下文"</blockquote>
  <div class="insight-meta">15:45 · OpenMy 项目</div>
  <button class="share-btn">分享</button>
</div>
```

#### 改动 8c：分享功能
- "分享"按钮 → Canvas 生成精美引用卡片图（品牌色 + 引用文字 + 日期）
- 下载为 PNG → 用户一键发小红书/朋友圈
- **这就是引流裂变点**

### 9. 🟡 隐私声明（Trust Badge）

**问题：** 用户把私密录音拖进网页界面，心理有顾虑。

#### 改动 9：Drop Zone 底部常驻隐私提示
```
🔒 所有处理在本机完成，音频不离开你的电脑
```
- 如果使用云端 STT，变为："音频会发送给 {provider} 进行转写，不会永久存储"
- 读取 `onboarding.current_provider`，根据 `LOCAL_STT_PROVIDERS` 判断是本地还是云端

### 10. 🟡 批量上传按日期分组

**问题：** DJI Mic 里有一周 14 个文件，用户只想处理今天的 3 个。

#### 改动 10：多文件上传后显示分组选择
```
检测到 14 个录音文件：

📅 4月7日（3个，45分钟）     [处理这天]
📅 4月6日（2个，30分钟）     [处理这天]
📅 更早（9个，4.5小时）      [仅展开]

                      [全部处理] [跳过]
```
- 从文件名解析日期（DJI 命名规则 `_YYYYMMDD_`）
- 其他来源的文件按修改时间分组

### 11. 🟢 Before/After 对比视图（引流杀手锏）

**问题：** 引流视频需要一个直观的"钩子画面"。

#### 改动 11：结果页增加 Before/After 开关
- 切换按钮："原文 ↔ 整理后"
- 左边：原始转写（杂乱、重复、口头禅）
- 右边：处理后结果（清晰、结构化）
- **截图效果极佳 → 发小红书标题："30分钟录音 → 3分钟看完"**

---

## 不要做的事

- 不要改 PR1 已有的 Drop Zone / 进度面板基础结构
- 不要做 inbox watch / 设备检测 / Auto-Process（那是 PR2/PR3）
- 不要改 CLI

## 测试要求

1. 单元测试：Opus 压缩后文件存在且 < 原文件 1/10
2. 单元测试：时间/成本预估计算
3. 单元测试：DJI 文件名解析 + 日期分组
4. 单元测试：`highlight_quote` 字段在 meta.json 中正确写入
5. 集成测试：上传 → 压缩 → pipeline 触发 → 渐进式结果 → 完成通知
6. 现有测试必须全部通过：`python3 -m pytest tests/ -q`

## 验证步骤

1. 拖入 247MB WAV → 确认 Opus 压缩到 inbox（< 10MB, < 15 秒）
2. 转写完成后 → 确认前端立刻显示初步文字（不用等全部完成）
3. 全部完成 → 确认浏览器弹通知 + 提示音
4. 确认首页出现 Insight Card（最值得记住的一句话）
5. 点分享 → 确认生成引用卡片图
6. Drop Zone 底部 → 确认隐私声明可见
7. 拖入多个文件 → 确认按日期分组显示
8. 点 Demo 按钮 → 确认 pipeline 启动
9. 结果页 → Before/After 切换正常
