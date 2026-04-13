# Stratify 设计参考 — 从视频逐帧提取

> 来源: stratify.com 演示视频 (37帧分析)
> 提取日期: 2026-04-13
> 目的: OpenMy 前端重设计的核心参考，防止上下文压缩丢失

## 1. 整体美学

### 色彩体系
```
页面背景:     #EEF2F7 (灰蓝色，非纯白，有温度感)
窗口背景:     #FFFFFF (纯白，浮在灰蓝底上，macOS 窗口效果)
侧边栏:       #FFFFFF (和主体同白，用细分割线区分)
卡片背景:     #FFFFFF
卡片边框:     #E8ECF1 (极淡灰，1px solid，圆角 ~16px)
暖黄高亮:     #FFF8E1 → #FFF3CD (Previously viewed files 卡片底色)
金色文字高亮: #D4A017 → #B8860B (AI 输出中的关键引用文字)
按钮主色:     #4F46E5 (Indigo/紫蓝，不是普通蓝)
成功/绿:      #059669 (Emerald)
警告/红:      #DC2626
标签背景:     很淡的对应色 + 描边 pill
```

### 字体观察
```
标题字体:     大号 sans-serif，weight ~400-500，极大字号 (~48-56px)
              "Welcome, Sam!" 用了略圆的 sans-serif
              二级标题 "How can I help you today?" 更轻 (~300 weight)
正文:         ~14-15px, sans-serif, #374151 (深灰不纯黑)
辅助文本:     ~12-13px, #9CA3AF
分类标题:     ~12px UPPERCASE, letter-spacing 0.05em, 700 weight, #6B7280
```

### 圆角体系
```
卡片圆角:     ~16px (大)
内部元素:     ~8-12px (按钮、标签)
头像:         50% (圆形)
标签 pill:    999px (全圆)
modal:        ~20px (更大)
```

### 阴影体系
```
卡片:         很微弱，几乎只有 border
modal:        大阴影 + 毛玻璃背景 (backdrop-filter: blur)
hover:        阴影稍微加深
```

---

## 2. 布局结构 (6 大组件)

### 2.1 侧边栏 (Sidebar)
```
宽度:         ~240px (展开态)
可收缩:       有 « 按钮，收缩为仅图标态 (~60px)

展开态内容:
├── 用户头像 + 名字 "Sam Smith"
├── 导航链接 (带右侧图标):
│   ├── Home        🏠
│   ├── New Chat    ↻
│   ├── My Tasks    📋
│   ├── My Meetings 📹
│   ├── Saved Files 📄
│   └── Shared with me 🔗
├── 分割线
├── 对话历史 (按时间分组):
│   ├── Today
│   │   ├── Research Assistance Request
│   │   ├── Summarizing Last Meeting
│   │   └── Prioritizing Tasks Request
│   └── Yesterday
│       └── Document Summary Request
├── 分割线
├── Pro 升级提示卡 (底部):
│   └── "Only 5 AI reports left" + Upgrade Now 按钮
└── Settings / ... 按钮

收缩态:
├── 仅图标垂直排列
├── hover 展开 tooltip
└── 保持可点击
```

**OpenMy 映射:**
- Home → 首页
- New Chat → (暂不需要)
- My Tasks → 可映射为"待跟进"
- My Meetings → "最近录音"
- 对话历史 → 日期列表 (已有)

### 2.2 首页 (Home Dashboard)
```
布局: 垂直堆叠，居中对齐，max-width ~800px

┌──────────────────────────────────────────────┐
│  Welcome, Sam! 👋                            │  ← 大字欢迎，浅蓝高亮背景
│  How can I help you today?                   │  ← 副标题，更轻的灰色
├──────────────────────────────────────────────┤
│                                              │
│  ┌─ Previously viewed files ─┐ ┌─ ✦ Summarize your  ─┐
│  │  📊 Miro - Product...    │ │   last meeting       │
│  │  🎨 Figma - UX Research  │ │  👤 UX Strategy      │
│  │  📕 R2 Strategic Goals   │ │  1 Apr 2025, 14:00   │
│  └── 暖黄底色 #FFF8E1 ──────┘ └────────白卡片─────────┘
│                                              │
│  ┌─ Suggested Task ──────────┐ ┌─ Suggested Task ─────┐
│  │  Conduct UX Research      │ │ Write a prospect     │
│  │                           │ │ email                │
│  └───────白卡片，边框 dashed──┘ └──────────────────────┘
│                                              │
│  ┌─ 📋 My Tasks  13  🔍 ──── ✨ Prioritize Tasks ──┐
│  │  🔴 Design Meeting · 2pm · 🟢 Join now          │
│  │  🟥 Refine UI... · ⚠️ Urgent · ⏰ By today      │
│  │  🔵 Prepare prototype · ⏳ In progress · By tmr  │
│  │  🔵 Collaborate... · ○ To do · By tomorrow       │
│  └──────────────────────────────────────────────────┘
│                                              │
│  ┌─ 底部输入栏 (固定) ──────────────────────────────┐
│  │ ✕ │ @ Select sources │ 🔗 Upload Files │         │
│  │ 🌐 Search Web ⚪ │ Ask or search for anything... │
│  └──────────────────────────────────────────────────┘
└──────────────────────────────────────────────┘
```

### 2.3 资源浏览弹窗 (Source Modal)
```
触发: 点击 "@ Select sources"
样式: 居中 modal，白色，大圆角 ~20px，毛玻璃背景

┌──────────────────────────────────────────────┐
│  🔍 Search for sources to chat with...       │
├──────────────────────────────────────────────┤
│  [All] [Documents] [Reports] [Images]        │  ← 水平 Tab 条
│  [Video] [Notes] [Audio]                     │
├──────────────────────────────────────────────┤
│                                              │
│  Documents (15)        │  Images (3)         │  ← 两列布局
│  📕 google-cert.pdf    │  [缩略图][缩略图]    │
│  📊 R2 Strategic...    │  [缩略图]            │
│  📙 UX Research...ppt  │                     │
│  📕 Accessibility...   │  Audio (4)           │
│  [show more ∨]         │  🎤 0:12 ▓▓▓░░ ▶   │
│                         │  🎤 0:19 ▓▓▓▓░ ▶   │
│  Reports (15)           │  🎤 0:15 ▓▓░░░ ▶   │
│  3,245   3.7%   2m35s   │  🎤 0:15 ▓▓░░░ ▶   │
│  SignUps  Conv   AvgSes │                     │
│  [show more ∨]         │                     │
└──────────────────────────────────────────────┘

关键设计细节:
- Documents 每行: 图标 + 文件名 + 文件大小(灰色)
- Reports: 内联数字指标卡 + mini 条形图(黄色)
- Images: 缩略图网格，圆角，右下角显示文件大小
- Audio: 波形可视化条 + 时长 + 播放按钮 ▶
```

### 2.4 AI 对话页面 (Chat View)
```
布局: 全宽，sidebar收缩为图标态

侧边栏收缩态图标:
├── 👤 用户头像
├── 🏠 Home
├── ↻ New Chat
├── 📋 Tasks
├── 📹 Meetings
├── 📄 Files
└── 🔗 Share

对话区域:
├── AI 回复（无气泡，直接白底文字）:
│   "Sure! Here's a draft Gmail summary..."
│   关键文字用金色高亮
├── 思考指示: "✦ Thought for 5 sec"
├── 来源指示器（左侧圆形图标列）:
│   📝 写作图标
│   🤗 表情
│   😊 表情
│   🌐 网页
├── 嵌入式卡片:
│   ┌─ Gmail ───────── Send ──────┐ ┌─ MAIL NAVIGATION ─┐
│   │ To: [everyone in UX team]   │ │ ✅ Strategic Focus│
│   │ Subject: Meeting Summary    │ │ 📝 Key objectives│
│   │                             │ │ ↗ Action Items   │
│   │ Hi Team,                    │ │ 📋 Summary       │
│   │ Thanks for everyone...      │ └──────────────────┘
│   │                             │
│   │ ✅ Strategic Focus Areas    │  ← 绿色高亮标题
│   │ Growth Optimization: ...    │
│   │                             │
│   │ 📝 Key Supporting Obj:      │  ← 黄绿色高亮标题
│   │ Launch regional...          │
│   └─────────────────────────────┘
└── 底部:
    [+] 💛 Looks good? Send it now ☉ │ Ask or search...  🔵

底部 CTA 按钮:
- 黄色渐变背景 "Looks good? Send it now"
- 带勾选图标
- 和输入栏同行
```

### 2.5 标签系统 (Tag/Pill Design)
```
状态标签:
- 🔴 Urgent:      红色文字 + 红色背景 pill (很淡)
- ⏰ By today:    橘色文字 + 橘色背景 pill
- ⏳ In progress: 绿色文字 + 绿色背景 pill
- ○ To do:        灰色文字 + 灰色背景 pill
- ⏰ By tomorrow: 灰色文字 + 灰色背景 pill
- 🟢 Join now:    绿色文字 + 绿色边框 pill

标签样式:
padding: 4px 10px
border-radius: 999px
font-size: 12px
font-weight: 500
border: 1px solid (对应颜色的20%不透明度)
background: (对应颜色的5-10%不透明度)
```

### 2.6 底部输入栏 (Command Bar)
```
位置: 固定在底部，全宽
高度: ~56px
背景: 半透明白 + blur

展开态:
├── ✕ 关闭按钮
├── @ Select sources (紫色，active态)
├── 🔗 Upload Files
├── 🌐 Search Web (带 toggle 开关)
├── 输入框: "Ask or search for anything. Use @ to tag..."
└── 🔵 发送按钮 (蓝色圆形)

收起态:
├── + 按钮 (紫色)
├── 输入框
└── 灰色发送按钮
```

---

## 3. 交互细节

### 动画
```
页面切换:     淡入 + 微上移 (fadeUp ~8px, 200ms)
卡片 hover:   阴影加深 + border-color 变化 (200ms)
sidebar 收缩: 宽度动画 (300ms ease)
modal 弹出:   scale(0.98) → scale(1) + opacity (200ms)
思考动画:     "Thought for 5 sec" + 三个跳动圆点
```

### 可点击反馈
```
卡片:         cursor:pointer, hover 阴影
标签:         cursor:pointer, hover 颜色加深
按钮:         cursor:pointer, hover opacity:0.9
列表项:       cursor:pointer, hover 背景色变化
```

---

## 4. OpenMy 映射方案 (Stratify → OpenMy)

| Stratify 组件 | OpenMy 对应 | 改造方案 |
|---|---|---|
| Welcome, Sam! 👋 | 首页标题 | "你好！今天是 X月Y日" + 副标题 |
| Previously viewed files | 最近录音 | 最近处理的录音卡片，带时长+日期 |
| Summarize last meeting | 今日洞察 | 从最新日报提取的 highlight card |
| Suggested Task | 智能建议 | "处理新录音" / "查看周报" |
| My Tasks | — | 暂不实现，不是核心功能 |
| @ Select sources | 增强版 Spotlight | 搜索全部录音/日报/周报 |
| Upload Files / Drop Zone | Drop Zone | 已在做 (PR1) |
| AI Chat | 未来功能 | v2 考虑 — "和录音对话" |
| 底部输入栏 | 增强搜索 | 常驻底部搜索 → v2 考虑 |
| 嵌入式 Gmail 卡片 | Insight Card | 提取今日最值得记住的一句话 |
| Reports 数字指标 | 周报统计 | 活跃天数/录音数/字数统计卡 |
| Audio 波形 | 录音预览 | 内联音频波形 + 播放按钮 |
| Tag/Pill 系统 | 录音状态标签 | 处理中/已完成/失败 状态 pill |

---

## 5. 不采用的 Stratify 元素

| 元素 | 原因 |
|---|---|
| Pro 升级提示 | OpenMy 是开源的，不需要付费提示 |
| "Only 5 AI reports left" | 无此限制 |
| Gmail/邮件集成 | 超出范围 |
| Search Web toggle | OpenMy 不联网搜索 |
| 完整 Chat 对话界面 | v2/v3 才考虑，v1 专注展示 |
