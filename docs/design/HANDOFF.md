# OpenMy 前端重构交接文档

> **作者**：CC (Antigravity)
> **日期**：2026-04-13
> **目的**：给接手前端重构的 Agent（小克 / Codex）一份完整的上下文交接，避免再次瞎胡干。

---

## 一、当前状况总结

### 文件地图

| 文件 | 用途 | 状态 |
|-----|------|------|
| `app/index.html` | **生产 HTML 骨架** | 稳定可用，是重构底子 |
| `app/static/style.css` | **生产 CSS (859行)** | 完善，有暗色模式、多主题色、圆角体系 |
| `app/static/app.js` | **生产 JS (1932行)** | 完善，全量 API 绑定 |
| `docs/design/preview.html` | **设计预览页（半成品）** | 被多次推翻，当前状态差，仅作参考 |

> [!CAUTION]
> `preview.html` 当前版本是一个**失败的产物**。它在多个维度上不如生产页 (`app/`)。
> 正确做法是**以 `app/` 为基础进化**，而不是另起炉灶。

---

## 二、后端 API 完整清单

以下是 `app/http_handlers.py` 中已实现的全部 API。**前端重构必须保留对这些端点的完整调用**。

### GET 端点

| 端点 | 功能 | 返回 | 前端用途 |
|-----|------|------|---------|
| `/api/health` | 健康检查 | `{status:"ok"}` | 连通性检测 |
| `/api/context` | 活跃上下文快照 | 包含 open_loops, active_projects, recent_decisions, today_focus | Wiki/上下文面板 |
| `/api/onboarding` | 新手引导状态 | stage, choices, current_provider, headline 等 | **新手引导流程核心** |
| `/api/dates` | 全部日期列表 | 每日的 segments 数、word_count、summary、events、decisions 等 | 侧边栏日期列表 + 首页最近记录 |
| `/api/search?q=xxx` | 全文搜索 | 匹配的 date/time/context（含 `<mark>` 高亮） | **搜索弹窗（Spotlight）** |
| `/api/stats` | 全局统计 | total_dates, total_words, total_segments, role_distribution | 侧边栏统计数字 |
| `/api/date/{date}` | 日期详情 | segments（含 role/summary）, meta, scenes, screen_events | 日期详情页 |
| `/api/date/{date}/meta` | 日期元数据 | daily_summary, events, decisions, todos, insights | 日期元数据面板 |
| `/api/date/{date}/briefing` | 日报 | AI 生成的每日简报 | 日报卡片 |
| `/api/briefing/{date}` | 同上 | 同上 | 同上 |
| `/api/corrections` | 校正词典 | `{corrections: [{wrong, right, count, ...}]}` | **校正词典展示** |
| `/api/pipeline/jobs` | 任务列表 | 所有 pipeline 任务 | 处理进度面板 |
| `/api/pipeline/jobs/{id}` | 单个任务详情 | 任务各步骤状态 | 任务详情弹窗 |
| `/api/context/loops` | 开放循环 | 待关闭的 open loops | 上下文面板 |
| `/api/context/projects` | 活跃项目 | 项目列表 | 上下文面板 |
| `/api/context/decisions` | 近期决策 | 决策列表 | 上下文面板 |
| `/api/context/query` | 上下文查询 | kind/q/limit/evidence 参数 | 上下文智能搜索 |
| `/api/settings/screen-context` | 屏幕识别设置 | enabled, participation_mode 等 | 设置面板 |

### POST 端点

| 端点 | 功能 | 请求体 | 前端用途 |
|-----|------|-------|---------|
| `/api/upload` | 上传录音文件 | multipart/form-data | **拖拽上传核心** |
| `/api/correct` | 提交纠错 | `{wrong, right, date, context, sync_vocab}` | **内联纠错弹窗** |
| `/api/correct/typo` | 同上 | 同上 | 同上 |
| `/api/pipeline/jobs` (POST) | 创建处理任务 | `{file_path, kind, ...}` | 启动 AI 分析 |
| `/api/pipeline/jobs/{id}/{action}` | 控制任务 | 暂停/取消/重启 | 任务操作按钮 |
| `/api/onboarding/select` | 选择转写引擎 | `{provider: "funasr"}` | **新手引导选择引擎** |
| `/api/context/loops/close` | 关闭循环 | `{id}` | 上下文操作 |
| `/api/context/loops/reject` | 拒绝循环 | `{id}` | 上下文操作 |
| `/api/context/projects/merge` | 合并项目 | `{id}` | 上下文操作 |
| `/api/context/projects/reject` | 拒绝项目 | `{id}` | 上下文操作 |
| `/api/context/decisions/reject` | 拒绝决策 | `{id}` | 上下文操作 |
| `/api/settings/screen-context` (POST) | 更新屏幕设置 | ScreenContextSettings | 设置面板保存 |

---

## 三、前端现有核心功能

以下功能在 `app/static/app.js` 中已经完整实现，**必须全部保留**：

### 1. 纠错系统 (Correction System)
- **触发方式**：用户在日期详情页中**选中文字**后，弹出纠错气泡 (`correctionPopover`)
- **实现**：`showCorrectionPopover(wrongText, dateStr)` → 用户输入正确文字 → `submitInlineCorrection()` → POST `/api/correct`
- **效果**：纠错后会自动替换当天转写文件中的所有匹配项，并同步到词库 `vocab.txt`
- **侧边栏展示**：`校正词典` 折叠面板，显示所有已纠正的词条及其计数

### 2. 录音文件拖入 (Drop Zone & Upload)
- **实现**：`renderHomeDropZone()` → 支持拖拽和点击上传
- **上传流程**：`handleHomeFileDrop(files)` → POST `/api/upload` → 得到 `file_path` → POST `/api/pipeline/jobs` 创建处理任务
- **进度追踪**：上传后自动轮询 `/api/pipeline/jobs/{id}`，在首页用 `renderHomePipelineSlotCard(job)` 展示实时进度
- **全局指示器**：右上角圆角胶囊 `globalJobIndicator`，显示"AI 正在分析中..."

### 3. 新手引导 (Onboarding)
- **状态机**：`choose_provider` → `complete_profile` → `init_vocab` → `ready`
- **实现**：`renderHomeOnboardingCard()` 基于 `/api/onboarding` 返回的 `stage` 动态渲染
- **核心交互**：用户在黄底区域选择 STT Provider → POST `/api/onboarding/select` → 页面刷新
- **STT 引擎选项**：funasr（本地中文）、faster-whisper（本地通用）、dashscope（云端中文）、gemini（云端省事）、groq（云端速度）、deepgram（云端英文）

### 4. 全文搜索 (Spotlight)
- **触发**：`Cmd+K` 快捷键 或 点击侧边栏搜索框
- **实现**：`openSpotlight()` → `searchTimer` 防抖 → GET `/api/search?q=xxx` → `renderSpotlightResults()`
- **搜索结果**：包含日期、时间段、上下文（含 `<mark>` 高亮匹配文字）

### 5. 设置面板 (Settings)
- **触发**：点击底部"设置"按钮 → `openSettings()` → 覆盖层弹窗
- **功能**：主题切换（亮/暗/自动）、主题色选择（蓝/紫/绿/橙/粉）、字号（小/中/大）
- **渲染**：`renderSettingsHTML()` 生成全部设置表单

### 6. 日报/周报/月报
- **日报**：点击日期 → `renderDayLayout()` → 展示时间段、AI 摘要、洞察、决策、待办
- **周报**：`renderWeeklyReport()` → 合并本周数据 → 折线图（Chart.js）
- **月报**：`renderMonthlyReport()` → 合并本月数据

---

## 四、设计系统约束（配色/字体/圆角）

### CSS Design Tokens（来自 `app/static/style.css`）

```css
/* 基础色板 — 禁止添加新颜色 */
--bg: #FFFFFF;              /* 主背景 */
--bg-hover: #F8F9FA;        /* 悬停态 */
--bg-active: #F1F5F9;       /* 激活态 */
--bg-sidebar: #F7F8FA;      /* 侧边栏 */
--text: #1A1A1A;            /* 主文字 */
--text-secondary: #6B7280;  /* 次要文字 */
--text-light: #9CA3AF;      /* 辅助文字 */
--border: #E5E7EB;          /* 边框 */
--accent: #2563EB;          /* 主色 */
--accent-light: #EFF6FF;    /* 主色浅底 */

/* 语义色 */
--success: #059669;
--warning: #d97706;
--error: #dc2626;

/* 圆角体系 — 两级 */
--radius: 12px;             /* 卡片/弹窗 */
--radius-sm: 8px;           /* 按钮/标签 */

/* 字体 — 纯原生栈，禁止引入外部字体 */
--font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;

/* 过渡 */
--transition: 0.25s cubic-bezier(0.16, 1, 0.3, 1);
```

### 铁律
1. **禁止使用任何外部字体**（Google Fonts 等），必须用 macOS 原生字体栈
2. **禁止使用 emoji 作为图标**，已有 SVG 图标在 `app/static/icons/` 目录
3. **暗色模式必须完整支持** — `[data-theme="dark"]` 变量已定义
4. **多主题色必须保留** — 蓝/紫/绿/橙/粉 五个选项

### 视觉对标（Stratify 参考的关键细节）

| 元素 | Stratify 做法 | 我们应该做的 |
|-----|-------------|-----------|
| 欢迎标题背景 | 极浅渐变（蓝→绿，约 8-12% 不透明度），药丸形 `border-radius: 999px`，padding 宽松 `8px 24px` | 照做，**不要用深蓝实底** |
| 副标题 | 40px+ 大字，黑色，简洁有力 | 保持 `How can I help you today?` 的气场感 |
| 卡片 | 纯白底 + 极淡边框 `rgba(0,0,0,0.06)` + hover 时微阴影 | 照做 |
| 侧边栏 | 头像+名字在顶部，导航菜单中间，日期列表在下面 | **日期列表不能丢** |
| 按钮过渡 | `cubic-bezier` 缓动，hover 时轻微 scale | 照做 |

---

## 五、preview.html 中值得保留的组件

以下组件在 `preview.html` 中实现了，思路是对的，但需要在生产代码基础上重新实现：

### 1. 搜索弹窗中的音频波形时间轴
- **设计**：搜索结果中如果命中音频转写内容，展示一个内嵌的可拖拽波形时间轴
- **HTML 类名**：`.audio-player`, `.waveform`, `.waveform-bar`, `.timeline-scrubber`
- **状态**：纯 CSS 模拟，未接真实音频 API

### 2. 用户资料系统
- **设计**：侧边栏左上角放用户头像（32px 圆形）+ 用户名
- **存储**：`localStorage.getItem('openmy_user_profile')` → `{name, avatar}`
- **弹窗**：点击头像弹出资料编辑弹窗（上传照片 + 修改名字）
- **头像压缩**：Canvas 重采样至 256x256，JPEG 0.85 质量

### 3. Onboarding 进度追踪条
- **设计**：三步横向进度条 `[✅ 系统就绪] — [⏳ 拖入录音] — [体验纠错]`
- **HTML 类名**：`.onboarding-tracker`, `.onboarding-step`, `.onboarding-divider`

### 4. 纠错侧边抽屉 (Drawer)
- **设计**：点击纠错条目后，从右侧滑出抽屉面板
- **上半部分**：原始音频波形 + 转写原文
- **下半部分**：可编辑的纠正后文本
- **HTML 类名**：`.drawer-backdrop`, `.correction-drawer`

---

## 六、推荐重构路线

> [!IMPORTANT]
> **以 `app/static/style.css` + `app/static/app.js` + `app/index.html` 为基础**，在现有生产代码上叠加新功能。不要另起炉灶。

### Phase 1：视觉微调（不动功能）
1. 在 `renderHomePage()` 返回的 HTML 中，给标题加上 Stratify 风格的浅渐变药丸背景
2. 调整首页卡片间距和圆角
3. 给按钮加 `cubic-bezier` 过渡动画

### Phase 2：功能集成
1. 将"用户资料系统"集成到 `app/index.html` 的侧边栏顶部（替换 Logo 区域或并列）
2. 将"音频波形搜索结果"集成到 `renderSpotlightResults()` 中
3. 将"纠错侧边抽屉"集成到纠错流程中（替换现有的 `correctionPopover`，或者在 popover 基础上增加 drawer 模式）

### Phase 3：新手引导优化
1. 将 Onboarding 进度条融入现有的 `renderHomeOnboardingCard()` 而不是另起炉灶
2. 保持与后端 `/api/onboarding` 的状态同步

---

## 七、文件交叉引用

```
openmy-clean/
├── app/
│   ├── index.html              ← 生产 HTML（基础骨架）
│   ├── http_handlers.py        ← 所有 API 路由
│   ├── payloads.py             ← API 数据构建逻辑
│   ├── pipeline_api.py         ← Pipeline 任务 API
│   ├── pipeline_runner.py      ← Pipeline 后台执行
│   ├── server.py               ← HTTP Server 启动
│   ├── upload.py               ← 上传处理
│   ├── context_api.py          ← 上下文操作 API
│   └── static/
│       ├── style.css           ← 生产 CSS (859行, 完善)
│       ├── app.js              ← 生产 JS (1932行, 完善)
│       ├── icons/              ← SVG 图标集
│       └── vendor/chart.umd.js ← Chart.js 图表库
├── docs/
│   └── design/
│       └── preview.html        ← 设计预览（半废品，仅参考）
└── src/openmy/resources/
    ├── corrections.json        ← 校正词典数据
    └── vocab.txt               ← 词库文件
```
