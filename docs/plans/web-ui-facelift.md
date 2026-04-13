# Web UI Facelift — Design Plan

> Status: CEO Reviewed + Approved
> Date: 2026-04-13
> Mode: Selective Expansion (3 expansions accepted)
> Scope: Homepage smart switch + drag-upload + watchdog entry + reading page polish

## Iron Rules

1. **Do NOT change CSS variables, colors, fonts, border-radius, or button styles.** The current design is good. Use it as-is.
2. **No emoji anywhere in the UI.** Not in headings, not in cards, not in labels. Zero emoji.
3. **No new color tokens.** Use existing `--accent`, `--bg-hover`, `--border`, etc.
4. **Keep the existing sidebar, search, stats, nav tabs, date list, settings, and correction dictionary exactly as they are.**
5. **All buttons and cards must be interactive** — every element that looks clickable must actually do something.

## Constraints

- Frontend files: `app/index.html`, `app/static/style.css`, `app/static/app.js`
- Backend files (new): upload API endpoint, watchdog config API endpoint
- Keep all existing API endpoints unchanged
- All tests must remain green after changes
- Button styling must match existing `.report-btn` / `.action-btn` patterns

## Architecture

```
app.js (renderHomePage)
  ├── if hasData → Recent Summary View (new)
  │     ├── Last N days: date + one-line summary + count
  │     ├── [帮助] button → switch to Wiki view
  │     └── calls existing APIs: /api/dates, /api/context, /api/stats
  │
  └── if !hasData → Wiki Documentation View (new)
        ├── Title + tagline (static)
        ├── Quick Start (3 steps, all clickable)
        │     ├── Step 1: drag-upload zone → POST /api/upload (NEW)
        │     ├── Step 2: one-line status or link to settings
        │     └── Step 3: link to date list
        ├── Features (6 cards, all clickable → existing functions)
        ├── Engines list (clickable → settings)
        ├── Watchdog setup entry → POST /api/settings/watchdog (NEW)
        ├── Commands table (display only)
        └── Footer links (GitHub, docs, issues)

server.py / http_handlers.py (new endpoints)
  ├── POST /api/upload — accept audio file, save to data/{date}/, trigger day.run
  └── GET/POST /api/settings/watchdog — get/set watched directory path
```

## 1. Homepage — Smart Switch

### Logic

```javascript
function renderHomePage() {
  const hasData = getVisibleDates().length > 0;
  if (hasData) {
    renderRecentSummaryView();  // new
  } else {
    renderWikiDocView();        // new
  }
}
```

### 1A. Wiki Documentation View (no data)

**Title + tagline:**
- "OpenMy"
- "把你每天说的话变成可搜索、可回顾的个人上下文。录音 → 转写 → 整理 → 浏览，全部在本地完成。"

**Section: 快速开始**
Three clickable step cards:
1. "准备一段录音" → reveals drag-upload zone (see Section 5)
2. "运行转写" → `openSettings('transcription')` to pick engine
3. "回来看结果" → scroll sidebar date list into view or highlight it

**Section: 能做什么**
Six feature cards in 2-column grid. Each is a button:
- "音频转文字" → `openSettings('transcription')`
- "自动整理" → show brief tooltip/explanation (no navigation target)
- "全文搜索" → `openSpotlight()`
- "屏幕记录" → `openSettings('screen')` (existing screen context settings)
- "纠错词典" → `toggleSidebarDict()`
- "周报月报" → `renderWeeklyReport()`

No emoji. Text labels only. Use existing `--bg-hover` background, existing border/radius.

**Section: 转写引擎**
List 6 engines with "本地"/"云端" tags. Each row clickable → `openSettings('transcription')`.

**Section: 监视目录 (NEW)**
Entry point for watchdog setup (see Section 6).

**Section: 常用命令**
Simple table: command → description. Monospace font for command column. Not clickable.

**Section: 底部链接**
GitHub, 完整文档, 反馈问题 — plain text links.

### 1B. Recent Summary View (has data)

Simple list of recent days:

```
最近记录

4月8日    复盘 OpenMy 转写准确率，收拢产品方向...    4条 · 1.5k字
4月12日   仅屏幕截图
4月13日   仅屏幕截图

                                              [帮助]
```

- Each day is a clickable row → `loadDate(date)`
- Show up to 7 most recent dates
- Bottom-right corner: [帮助] button → switches to Wiki view
- Use existing date list item styling patterns

### 1C. Onboarding handling
- Move ALL onboarding UI out of homepage into settings overlay
- Delete `renderHomeOnboardingCard()` from homepage rendering
- If onboarding incomplete, show one line at top: "还没配置转写引擎 →" linking to settings

### 1D. Empty state
The Wiki view IS the empty state. No special case needed.

## 2. Reading Page — Visual Polish Only

Keep existing rendering logic. Only improve clarity:

- **Timeline time labels**: slightly bolder, left-aligned
- **Segment separation**: subtle spacing or thin divider between segments
- **Role badges**: slightly more prominent using existing role color tokens
- **Briefing callout**: if daily briefing exists, show at top in callout using `--accent-light` bg
- **Correction marks**: dotted underline + pointer cursor on correctable text

Do NOT change: color scheme, font sizes, button styles, any behavior.

## 3. Sidebar — Minimal Changes

- Add status dot next to each date: green = has briefing, yellow = transcript only, gray = screens only
- Use existing CSS color tokens (`--success`, `--warning`, `--text-light`)
- Everything else stays exactly the same

## 4. Copywriting Cleanup

| Before | After |
|--------|-------|
| 网页首配入口 | (removed) |
| 暂无可用阅读数据 | (replaced by Wiki view) |
| 还没有可读数据。先把首配路线定下来... | (replaced by Wiki view) |
| 当前没有待办 | 暂无 |
| 当前没有项目 | 暂无 |
| 当前没有决策 | 暂无 |

## 5. Drag-Upload Zone (NEW — Expansion 1)

### Frontend
- In the Wiki view, Step 1 "准备一段录音" click reveals a drag-drop zone
- Accepts: .mp3, .m4a, .wav, .flac
- On drop: upload file via `POST /api/upload`, show progress, then auto-navigate to the new date when processing completes
- File validation: check extension before upload, reject with clear message
- Max file size: validate client-side (e.g., 500MB limit)

### Backend
- `POST /api/upload` — new endpoint
- Accept multipart file upload
- Save to `data/{today}/` directory
- Trigger `day.run` pipeline for that date (use existing JobRunner)
- Return job_id so frontend can poll progress via existing `/api/pipeline/jobs`

### Edge cases
- What if file is too large? → client-side rejection with message
- What if file format is wrong? → client-side extension check
- What if upload fails mid-way? → show error toast, clean up partial file
- What if day.run fails after upload? → job status shows failure, user can retry from settings

## 6. Watchdog Directory Setup (NEW — Expansion 3)

### Frontend
- In Wiki view, a "监视录音文件夹" section with:
  - Current watched path (or "未设置")
  - A text input to set/change the path
  - Enable/disable toggle
- In settings overlay, same UI accessible from there too

### Backend
- `GET /api/settings/watchdog` — return current config
- `POST /api/settings/watchdog` — set path + enabled status
- Store in project `.env` or a `watchdog_config.json` in data/
- Actual watchdog daemon integration: if `openmy` CLI already has watchdog support, just write the config. If not, this is the config UI only — daemon implementation is out of scope for this PR.

### Edge cases
- Path doesn't exist → validate and show error
- Path not readable → validate and show error
- Path is on external drive → warn but allow

## Execution Order

1. **Wiki documentation view** (core homepage content)
2. **Smart switch logic** (if/else in renderHomePage)
3. **Recent summary view** (old user homepage)
4. **Upload API + drag zone** (expansion 1)
5. **Watchdog config UI + API** (expansion 3)
6. **Sidebar status dots** (small)
7. **Reading page polish** (detail)
8. **Copy cleanup** (parallel with any step)
9. **Help button on summary view** (expansion 2, trivial)

## Out of Scope

- No CSS variable changes
- No new color palette
- No font changes
- No button style redesign
- No framework migration
- No new pages or routes (everything is in the existing SPA)
- No watchdog daemon implementation (config UI only, unless CLI already supports it)
- No mobile-specific redesign
