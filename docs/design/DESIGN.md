# OpenMy Design System — DESIGN.md

> 第一版 | 2026-04-13
> 风格: Warm-Productivity (参考 Stratify)
> 约束: 纯 HTML/CSS/JS，无外部框架

---

## 设计原则

1. **温暖但高效** — 不是冷峻工具，是贴心助手
2. **卡片即功能** — 每个功能模块是独立的 Card
3. **渐进披露** — 不一次性倒出所有信息
4. **数据有人情味** — 数字要有上下文（"比上周多 2 条"而非只是 "5"）
5. **零学习成本** — 第一次打开就知道该做什么

---

## 色彩系统

### 浅色主题 (默认)

```css
:root {
  /* === 背景层次 === */
  --bg-canvas:        #F0F4F8;     /* 页面底色 — 柔和灰蓝 */
  --bg-surface:       #FFFFFF;     /* 卡片/面板 — 纯白 */
  --bg-sidebar:       #FFFFFF;     /* 侧边栏 */
  --bg-warm:          #FFF8E1;     /* 提示/高亮底色 — 温暖米黄 */
  --bg-warm-hover:    #FFF3CD;     /* 提示 hover */
  --bg-success-subtle:#ECFDF5;     /* 成功状态底色 */
  --bg-error-subtle:  #FEF2F2;     /* 错误状态底色 */
  
  /* === 主色 === */
  --accent:           #4F46E5;     /* Indigo-600 — 品牌识别色 */
  --accent-hover:     #4338CA;     /* Indigo-700 */
  --accent-light:     #EEF2FF;     /* Indigo-50 — 淡底色 */
  --accent-border:    #C7D2FE;     /* Indigo-200 — 边框 */
  
  /* === 文字 === */
  --text-primary:     #111827;     /* 主文字 — 接近黑色但不纯黑 */
  --text-secondary:   #6B7280;     /* 辅助文字 */
  --text-tertiary:    #9CA3AF;     /* 灰色提示文字 */
  --text-accent:      #4F46E5;     /* 强调文字 */
  --text-warm:        #92400E;     /* 暖色高亮文字 (amber-800) */
  
  /* === 边框 === */
  --border:           #E5E7EB;     /* 主要边框 */
  --border-light:     #F3F4F6;     /* 极淡边框 */
  --border-focus:     #4F46E5;     /* 聚焦边框 */
  
  /* === 语义色 === */
  --success:          #059669;     /* 绿 */
  --warning:          #D97706;     /* 橙 */
  --error:            #DC2626;     /* 红 */
  --info:             #2563EB;     /* 蓝 */
  
  /* === 阴影 === */
  --shadow-sm:        0 1px 2px rgba(0,0,0,0.05);
  --shadow-md:        0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -1px rgba(0,0,0,0.04);
  --shadow-lg:        0 10px 25px -3px rgba(0,0,0,0.08), 0 4px 6px -2px rgba(0,0,0,0.03);
  --shadow-xl:        0 20px 40px -5px rgba(0,0,0,0.12);
}
```

### 深色主题

```css
[data-theme="dark"] {
  --bg-canvas:        #0F172A;
  --bg-surface:       #1E293B;
  --bg-sidebar:       #1E293B;
  --bg-warm:          #422006;
  --bg-warm-hover:    #451A03;
  --bg-success-subtle:#064E3B;
  --bg-error-subtle:  #7F1D1D;
  
  --accent:           #818CF8;     /* Indigo-400 */
  --accent-hover:     #A5B4FC;     /* Indigo-300 */
  --accent-light:     #312E81;     /* Indigo-900 */
  --accent-border:    #4338CA;
  
  --text-primary:     #F1F5F9;
  --text-secondary:   #94A3B8;
  --text-tertiary:    #64748B;
  --text-accent:      #818CF8;
  --text-warm:        #FDE68A;
  
  --border:           #334155;
  --border-light:     #1E293B;
  --border-focus:     #818CF8;
  
  --shadow-sm:        0 1px 2px rgba(0,0,0,0.3);
  --shadow-md:        0 4px 6px rgba(0,0,0,0.4);
  --shadow-lg:        0 10px 25px rgba(0,0,0,0.5);
  --shadow-xl:        0 20px 40px rgba(0,0,0,0.6);
}
```

---

## 字体

```css
/* Google Fonts 加载 */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --font-display:  'Plus Jakarta Sans', -apple-system, sans-serif;
  --font-body:     'DM Sans', -apple-system, sans-serif;
  --font-mono:     'JetBrains Mono', 'SF Mono', monospace;
}
```

### 字号体系

| 用途 | 类名 | 字号 | Weight | 字体 |
|---|---|---|---|---|
| 页面大标题 | `.text-hero` | 48px | 700 | display |
| 标题 | `.text-heading` | 24px | 600 | display |
| 小标题 | `.text-subheading` | 18px | 600 | display |
| 正文 | `.text-body` | 15px | 400 | body |
| 辅助文字 | `.text-caption` | 13px | 400 | body |
| 极小文字 | `.text-micro` | 11px | 500 | body |
| 数据数字 | `.text-data` | 32px | 700 | display |
| 代码/标签 | `.text-mono` | 13px | 400 | mono |

---

## 间距

```css
:root {
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
}
```

---

## 圆角

```css
:root {
  --radius-sm:  6px;   /* 小按钮、标签 */
  --radius-md:  10px;  /* 输入框 */
  --radius-lg:  16px;  /* 卡片 */
  --radius-xl:  20px;  /* Modal */
  --radius-full: 999px; /* Pill 标签 */
}
```

---

## 组件规范

### Card (卡片)

```css
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--border-focus);
}

/* 暖色卡片 (高亮/提示) */
.card--warm {
  background: var(--bg-warm);
  border-color: #F59E0B20;
}
```

### Pill 标签

```css
.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-body);
}

.pill--success {
  color: var(--success);
  background: #05966910;
  border: 1px solid #05966920;
}

.pill--error {
  color: var(--error);
  background: #DC262610;
  border: 1px solid #DC262620;
}

.pill--warning {
  color: var(--warning);
  background: #D9770610;
  border: 1px solid #D9770620;
}

.pill--neutral {
  color: var(--text-secondary);
  background: #6B728010;
  border: 1px solid #6B728020;
}
```

### 侧边栏

```
宽度: 260px (展开) / 60px (收缩)
背景: var(--bg-sidebar)
边框: 右侧 1px solid var(--border-light)
动画: width 300ms cubic-bezier(0.4, 0, 0.2, 1)

导航项:
  高度: 40px
  padding: 8px 16px
  圆角: 8px
  hover: background var(--accent-light)
  active: background var(--accent-light), color var(--accent), font-weight 600
```

### 欢迎区域

```
标题: "你好！今天是 X月Y日 👋"
  字体: var(--font-display)
  字号: 48px
  Weight: 700
  颜色: var(--text-primary)
  背景高亮: 浅蓝色 #DBEAFE40 (类似 Stratify)
  
副标题: "这是你的个人上下文引擎"
  字号: 24px
  Weight: 400
  颜色: var(--text-tertiary)
```

---

## 页面布局

### 首页

```
主体 max-width: 840px
居中: margin 0 auto
padding: var(--space-8) var(--space-6)

区块间距: var(--space-6)

布局:
1. 欢迎区 (全宽)
2. 两列卡片: [洞察卡片 60%] [统计卡片 40%]
3. Drop Zone (全宽)
4. 最近录音列表 (全宽)
```

### 日报详情

```
主体 max-width: 840px

布局:
1. 日期标题 + 统计 (X条记录 · Xk字)
2. 核心洞察卡片 (暖色底, 全宽)
3. 概要区块
4. 分类列表: "打算做什么" / "记住了什么" / "做出了什么决定"
   每条有:
   - 左侧 bullet (彩色圆点)
   - 正文
   - 右下 pill 标签 (话题分类)
```

### 周报

```
主体 max-width: 840px

布局:
1. 标题 + 日期范围 + 统计
2. 数字指标行: [活跃天数] [录音数] [字数] — 3列等宽卡片
3. 活跃热力条 (7天横条图)
4. 本周高亮引用 (暖色底)
5. 决策列表
6. 待跟进列表
7. 每日概要折叠列表
```

### 月报

```
类似周报但:
- 热力条变成日历热力图
- 增加话题分布统计
- 月度趋势 (录音量 by week)
```

---

## 动画

```css
/* 页面进入 */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 卡片出现 — 依次延迟 */
.card { animation: fadeUp 0.3s ease forwards; }
.card:nth-child(1) { animation-delay: 0ms; }
.card:nth-child(2) { animation-delay: 80ms; }
.card:nth-child(3) { animation-delay: 160ms; }

/* Hover 微动 */
.card { transition: transform 0.15s ease, box-shadow 0.2s ease; }
.card:hover { transform: translateY(-2px); }

/* 侧边栏收缩 */
.sidebar { transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
```

---

## 设计参考图

参见 `docs/design/stratify-frames/` 目录:
- `01-home-full.jpg` — 首页完整布局
- `02-cards-detail.jpg` — 卡片细节(圆角、边框)
- `03-bottom-bar-expanded.jpg` — 底部输入栏
- `04-source-modal.jpg` — 资源浏览弹窗
- `05-audio-preview.jpg` — 音频波形预览
- `06-ai-chat-email.jpg` — AI 对话 + 邮件输出
- `07-email-card-full.jpg` — 嵌入式邮件卡片
- `08-home-sidebar-expanded.jpg` — 完整侧边栏
