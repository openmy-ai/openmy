# Visual Upgrade V2 — Homepage, Daily Report, Weekly Report

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade three pages (homepage, daily report, weekly report) with higher information density, Stratify-inspired gradients, stats cards, and data visualization — while preserving all existing functionality.

**Architecture:** Pure CSS additions appended to existing `style.css` + JS function replacements in `app.js`. No new files, no framework changes, no HTML skeleton changes.

**Tech Stack:** Vanilla HTML/CSS/JS, Chart.js (existing), system font stack only

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `app/static/style.css` | Modify (append ~250 lines) | New component styles: welcome hero, stats row, card grid, callout v2, heatmap, etc. |
| `app/static/app.js` | Modify (replace 4 functions) | `renderRecentSummaryHome`, `renderDayLayout`, `renderReportPage`, `renderWeeklyReport`+`renderMonthlyReport` |

**Not touched:** `app/index.html`, sidebar, spotlight, correction system, settings, upload/pipeline, all API endpoints.

---

## Design Constraints (violating any = rejection)

1. White bg `#FFFFFF`, sidebar `#F7F8FA`
2. System font `-apple-system` only — NO Google Fonts
3. Blue accent `#2563EB` via `var(--accent)` — NO purple, NO indigo
4. Border radius `12px` cards / `8px` buttons
5. NO emoji anywhere
6. Dark mode `[data-theme="dark"]` coverage for ALL new styles
7. Multi-accent via CSS variables (`var(--accent)`, `var(--accent-light)`)

---

### Task 1: Baseline — Verify tests pass

**Files:**
- Read: `app/static/style.css`
- Read: `app/static/app.js`

- [ ] **Step 1: Run the full test suite**

```bash
cd ~/Desktop/openmy-clean && python3 -m pytest tests/ -q
```

Expected: 449+ tests pass, 0 failures

- [ ] **Step 2: Back up current files**

```bash
cd ~/Desktop/openmy-clean
cp app/static/style.css app/static/style.css.bak
cp app/static/app.js app/static/app.js.bak
```

- [ ] **Step 3: Start the dev server to verify current state**

```bash
cd ~/Desktop/openmy-clean && python3 app/server.py &
```

Open `http://localhost:8420` and confirm: homepage loads, sidebar shows dates, clicking a date shows the daily report, clicking "周报" shows weekly report.

- [ ] **Step 4: Commit baseline**

```bash
git add -A && git commit -m "chore: backup before visual upgrade v2"
```

---

### Task 2: CSS — Welcome Hero + Stats Row

**Files:**
- Modify: `app/static/style.css` (append at end)

- [ ] **Step 1: Append Welcome Hero CSS**

Add to the end of `app/static/style.css`:

```css
/* ============================================
   VISUAL UPGRADE V2 — 2026-04-14
   ============================================ */

/* --- Welcome Hero Section --- */
.welcome-hero {
  background: linear-gradient(135deg, rgba(147,197,253,0.15) 0%, rgba(167,243,208,0.12) 100%);
  border-radius: var(--radius);
  padding: 40px 32px 32px;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}
.welcome-hero::before {
  content: '';
  position: absolute;
  top: -60px;
  right: -40px;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(147,197,253,0.12) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}
.welcome-title {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--text);
  line-height: 1.3;
  margin-bottom: 6px;
}
.welcome-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  font-weight: 500;
}

[data-theme="dark"] .welcome-hero {
  background: linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(52,211,153,0.06) 100%);
}
```

- [ ] **Step 2: Append Stats Row CSS**

Continue appending to `style.css`:

```css
/* --- Stats Row (3 columns) --- */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  text-align: center;
  transition: box-shadow var(--transition), border-color var(--transition);
}
.stat-card:hover {
  box-shadow: var(--shadow);
  border-color: rgba(37, 99, 235, 0.2);
}
.stat-card-value {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text);
  line-height: 1.2;
}
.stat-card-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 4px;
}
.stat-card-delta {
  font-size: 11px;
  font-weight: 600;
  color: var(--success);
  margin-top: 6px;
}
.stat-card-delta.negative { color: var(--text-light); }
```

- [ ] **Step 3: Verify CSS syntax**

```bash
cd ~/Desktop/openmy-clean && python3 -c "
with open('app/static/style.css') as f:
    css = f.read()
print(f'CSS length: {len(css)} chars')
print(f'Open braces: {css.count(\"{\")}')
print(f'Close braces: {css.count(\"}\")}')
assert css.count('{') == css.count('}'), 'Mismatched braces!'
print('CSS braces balanced OK')
"
```

Expected: "CSS braces balanced OK"

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/openmy-clean && git add app/static/style.css && git commit -m "feat: add welcome hero and stats row CSS"
```

---

### Task 3: CSS — Home Card Grid + Summary Callout V2

**Files:**
- Modify: `app/static/style.css` (append at end)

- [ ] **Step 1: Append Home Card Grid CSS**

```css
/* --- Home Card Grid --- */
.home-card-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}
.home-card-grid--full {
  grid-column: 1 / -1;
}
.home-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition), transform var(--transition);
  cursor: pointer;
  animation: fadeUp 0.3s ease forwards;
}
.home-card:hover {
  box-shadow: var(--shadow);
  transform: translateY(-2px);
}
.home-card:nth-child(2) { animation-delay: 60ms; }
.home-card:nth-child(3) { animation-delay: 120ms; }
.home-card:nth-child(4) { animation-delay: 180ms; }

.home-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.home-card-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.home-card-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--accent-light);
  color: var(--accent);
}
.home-card-body {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text);
}
.home-card-footer {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-light);
  font-weight: 500;
}
```

- [ ] **Step 2: Append Summary Callout V2 CSS**

```css
/* --- Summary Callout V2 --- */
.summary-callout-v2 {
  background: linear-gradient(135deg, rgba(147,197,253,0.12) 0%, rgba(167,243,208,0.08) 100%);
  border: 1px solid rgba(147,197,253,0.2);
  border-radius: var(--radius);
  padding: 24px 28px;
  margin-bottom: 32px;
  position: relative;
}
.summary-callout-v2::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 4px;
  background: var(--accent);
  border-radius: 2px;
}
.summary-callout-v2 .callout-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent);
  margin-bottom: 8px;
}
.summary-callout-v2 p {
  font-size: 16px;
  line-height: 1.75;
  color: var(--text);
  font-weight: 500;
}

[data-theme="dark"] .summary-callout-v2 {
  background: linear-gradient(135deg, rgba(59,130,246,0.06) 0%, rgba(52,211,153,0.04) 100%);
  border-color: rgba(59,130,246,0.15);
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/openmy-clean && git add app/static/style.css && git commit -m "feat: add home card grid and summary callout v2 CSS"
```

---

### Task 4: CSS — Daily Stats Bar + Weekly Heatmap + Remaining Styles

**Files:**
- Modify: `app/static/style.css` (append at end)

- [ ] **Step 1: Append Daily Stats Bar CSS**

```css
/* --- Daily Page Stats Bar --- */
.daily-stats-bar {
  display: flex;
  gap: 24px;
  padding: 16px 0;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border);
}
.daily-stat-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.daily-stat-num {
  font-size: 20px;
  font-weight: 800;
  color: var(--text);
  letter-spacing: -0.02em;
}
.daily-stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}
```

- [ ] **Step 2: Append Weekly Heatmap CSS**

```css
/* --- Weekly Heatmap Bar --- */
.week-heatmap {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
  margin-bottom: 24px;
}
.week-heatmap-day {
  text-align: center;
  border-radius: var(--radius-sm);
  padding: 12px 4px;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  transition: all var(--transition);
}
.week-heatmap-day.active {
  background: var(--accent-light);
  border-color: rgba(37, 99, 235, 0.25);
}
.week-heatmap-day.active .heatmap-bar {
  background: var(--accent);
}
.heatmap-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.heatmap-bar-wrapper {
  height: 60px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.heatmap-bar {
  width: 24px;
  background: var(--border);
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.heatmap-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
  margin-top: 6px;
}
```

- [ ] **Step 3: Append Week Highlight + Context Cards + Drop Zone + Chip + Daily Link V2 + Responsive**

```css
/* --- Weekly Highlight Quote --- */
.week-highlight {
  background: linear-gradient(135deg, rgba(147,197,253,0.12) 0%, rgba(167,243,208,0.08) 100%);
  border: 1px solid rgba(147,197,253,0.2);
  border-radius: var(--radius);
  padding: 24px 28px;
  margin-bottom: 24px;
  position: relative;
}
.week-highlight::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 4px;
  background: var(--accent);
  border-radius: 2px;
}
.week-highlight-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent);
  margin-bottom: 8px;
}
.week-highlight-text {
  font-size: 18px;
  line-height: 1.6;
  color: var(--text);
  font-weight: 600;
  letter-spacing: -0.01em;
}

[data-theme="dark"] .week-highlight {
  background: linear-gradient(135deg, rgba(59,130,246,0.06) 0%, rgba(52,211,153,0.04) 100%);
  border-color: rgba(59,130,246,0.15);
}

/* --- Context Cards (Projects/Loops) --- */
.context-card-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.context-card-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text);
  transition: all var(--transition);
}
.context-card-item:hover {
  background: var(--bg-hover);
  border-color: rgba(37, 99, 235, 0.2);
}

/* --- Drop Zone V2 --- */
.drop-zone-v2 {
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  padding: 32px;
  text-align: center;
  margin-bottom: 24px;
  transition: all var(--transition);
  cursor: pointer;
  background: var(--bg);
}
.drop-zone-v2:hover,
.drop-zone-v2.dragover {
  border-color: var(--accent);
  background: var(--accent-light);
}
.drop-zone-v2 .dz-text {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}
.drop-zone-v2 .dz-hint {
  font-size: 12px;
  color: var(--text-light);
  margin-top: 4px;
}

/* --- Chip V2 --- */
.chip-list-v2 {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip-v2 {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  color: var(--text);
  transition: all var(--transition);
}
.chip-v2:hover {
  background: var(--accent-light);
  border-color: rgba(37, 99, 235, 0.2);
  color: var(--accent);
}

/* --- Daily Link V2 --- */
.daily-link-list-v2 {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.daily-link-v2 {
  display: grid;
  grid-template-columns: 80px 1fr auto;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition);
  text-align: left;
  width: 100%;
  border: none;
  font-family: var(--font-body);
  color: var(--text);
}
.daily-link-v2:hover {
  background: var(--bg-hover);
}
.daily-link-v2 .dl-date {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}
.daily-link-v2 .dl-summary {
  font-size: 14px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.daily-link-v2 .dl-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-light);
  background: var(--bg-hover);
  padding: 3px 10px;
  border-radius: 999px;
}

/* --- Responsive for V2 components --- */
@media (max-width: 900px) {
  .stats-row { grid-template-columns: 1fr; }
  .home-card-grid { grid-template-columns: 1fr; }
  .week-heatmap { grid-template-columns: repeat(7, 1fr); gap: 4px; }
  .welcome-hero { padding: 24px 20px 20px; }
  .welcome-title { font-size: 22px; }
  .daily-link-v2 { grid-template-columns: 60px 1fr auto; }
}
```

- [ ] **Step 4: Verify CSS braces balance**

```bash
cd ~/Desktop/openmy-clean && python3 -c "
with open('app/static/style.css') as f:
    css = f.read()
print(f'CSS length: {len(css)} chars')
assert css.count('{') == css.count('}'), f'Mismatched braces: {css.count(\"{\")} open vs {css.count(\"}\")} close'
print('CSS braces balanced OK')
"
```

Expected: "CSS braces balanced OK"

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/openmy-clean && git add app/static/style.css && git commit -m "feat: add heatmap, highlight, context cards, chip v2, responsive CSS"
```

---

### Task 5: JS — Replace renderRecentSummaryHome (Homepage)

**Files:**
- Modify: `app/static/app.js:824-847` (replace function body)

- [ ] **Step 1: Locate the function**

```bash
cd ~/Desktop/openmy-clean && grep -n "function renderRecentSummaryHome" app/static/app.js
```

Expected: line ~824

- [ ] **Step 2: Replace renderRecentSummaryHome**

Replace the entire `renderRecentSummaryHome` function (from `function renderRecentSummaryHome(visibleDates) {` to its closing `}`) with:

```javascript
function renderRecentSummaryHome(visibleDates) {
  const main = document.getElementById('main');
  const recentDates = visibleDates.slice(0, 7);
  const today = new Date();
  const monthDay = `${today.getMonth() + 1}月${today.getDate()}日`;

  const todayItem = recentDates.find(item => item.date === today.toISOString().slice(0, 10));
  const todaySummary = todayItem
    ? truncateSummary(todayItem.summary || todayItem.timeline?.[0]?.preview || '')
    : '';

  const totalSegments = recentDates.reduce((s, i) => s + (i.segments || 0), 0);
  const totalWords = recentDates.reduce((s, i) => s + (i.word_count || 0), 0);
  const activeDays = recentDates.filter(i => i.segments > 0).length;

  const projects = (state.context.active_projects || []).slice(0, 4);
  const loops = (state.context.open_loops || state.loops || []).slice(0, 4);

  main.innerHTML = `
    <div class="home-page">
      <div class="welcome-hero">
        <div class="welcome-title">你好！今天是 ${escapeHtml(monthDay)}</div>
        <div class="welcome-subtitle">这是你最近 7 天的上下文概览</div>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-card-value">${activeDays}</div>
          <div class="stat-card-label">活跃天数</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-value">${totalSegments}</div>
          <div class="stat-card-label">录音段数</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-value">${fmtNum(totalWords)}</div>
          <div class="stat-card-label">总字数</div>
        </div>
      </div>

      <div class="home-card-grid">
        <div class="home-card home-card-grid--full" ${todayItem ? `onclick="loadDate('${escapeHtml(todayItem.date)}')"` : ''}>
          <div class="home-card-header">
            <span class="home-card-title">今日摘要</span>
            ${todayItem ? `<span class="home-card-badge">${todayItem.segments}条记录</span>` : ''}
          </div>
          <div class="home-card-body">
            ${todaySummary ? escapeHtml(todaySummary) : '<span class="text-muted">今天还没有录音</span>'}
          </div>
        </div>

        ${projects.length ? `
        <div class="home-card">
          <div class="home-card-header">
            <span class="home-card-title">活跃项目</span>
            <span class="home-card-badge">${projects.length}</span>
          </div>
          <div class="context-card-list">
            ${projects.map(p => `<div class="context-card-item"><span>${escapeHtml(p.title || p.project_id || '')}</span></div>`).join('')}
          </div>
        </div>` : ''}

        ${loops.length ? `
        <div class="home-card">
          <div class="home-card-header">
            <span class="home-card-title">待跟进</span>
            <span class="home-card-badge">${loops.length}</span>
          </div>
          <div class="context-card-list">
            ${loops.map(l => `<div class="context-card-item"><span>${escapeHtml(l.task || l.what || l.text || '')}</span></div>`).join('')}
          </div>
        </div>` : ''}
      </div>

      <div id="homePipelineSlot">${renderHomePipelineSlotCard(getHomePipelineJob())}</div>

      ${typeof renderHomeDropZone === 'function' ? renderHomeDropZone() : ''}

      <div class="section-kicker" style="margin-bottom:12px">最近录音</div>
      <div class="daily-link-list-v2">
        ${recentDates.map(item => `
          <button class="daily-link-v2" type="button" onclick="loadDate('${escapeHtml(item.date)}')">
            <span class="dl-date">${escapeHtml(formatFriendlyDate(item.date))}</span>
            <span class="dl-summary">${item.segments ? escapeHtml(truncateSummary(item.summary || item.timeline?.[0]?.preview || '')) : '<span class="text-muted">仅屏幕截图</span>'}</span>
            <span class="dl-count">${item.segments ? item.segments + '条' : '截屏'}</span>
          </button>
        `).join('')}
      </div>

      <div style="text-align:center;padding:24px 0">
        <button class="report-btn" type="button" onclick="state.showWikiHome=true;renderHomePage()">使用说明</button>
      </div>
    </div>
  `;
}
```

- [ ] **Step 3: Verify no syntax errors**

```bash
cd ~/Desktop/openmy-clean && node -c app/static/app.js && echo "JS syntax OK"
```

Expected: "JS syntax OK"

- [ ] **Step 4: Browser verify homepage**

Open `http://localhost:8420`. Confirm:
- Welcome hero with light blue-green gradient shows today's date
- 3 stat cards show numbers
- Today's summary card present
- Recent recordings list renders with new grid style
- "使用说明" button works

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/openmy-clean && git add app/static/app.js && git commit -m "feat: upgrade homepage with welcome hero, stats, and card grid"
```

---

### Task 6: JS — Replace renderDayLayout (Daily Report)

**Files:**
- Modify: `app/static/app.js:1031-1082` (replace function body)

- [ ] **Step 1: Locate the function**

```bash
cd ~/Desktop/openmy-clean && grep -n "function renderDayLayout" app/static/app.js
```

Expected: line ~1031

- [ ] **Step 2: Replace renderDayLayout**

Replace the entire `renderDayLayout` function with:

```javascript
function renderDayLayout() {
  const detail = state.currentData;
  const meta = state.currentMeta || {};
  if (!detail) return;

  const summaryText = plainText(meta.daily_summary || state.currentBriefing?.summary || state.context.status_line || '');

  const times = detail.segments.map(s => s.time).filter(Boolean).sort();
  const timeSpan = times.length >= 2 ? `${times[0]} - ${times[times.length - 1]}` : (times[0] || '');

  document.getElementById('main').innerHTML = `
    <article class="daily-article">
      <header class="page-header">
        <div class="page-title">${escapeHtml(formatPageDate(detail.date))}</div>
      </header>

      <div class="daily-stats-bar">
        <div class="daily-stat-item">
          <span class="daily-stat-num">${detail.segments.length}</span>
          <span class="daily-stat-label">条记录</span>
        </div>
        <div class="daily-stat-item">
          <span class="daily-stat-num">${fmtNum(detail.word_count || 0)}</span>
          <span class="daily-stat-label">字</span>
        </div>
        ${timeSpan ? `<div class="daily-stat-item">
          <span class="daily-stat-num" style="font-size:16px">${escapeHtml(timeSpan)}</span>
          <span class="daily-stat-label">时间跨度</span>
        </div>` : ''}
      </div>

      ${summaryText ? `
      <section class="summary-callout-v2">
        <div class="callout-label">AI 摘要</div>
        <p>${escapeHtml(summaryText)}</p>
      </section>` : ''}

      ${renderMetaPanels(meta)}

      <section class="article-section">
        <h2 class="collapsible-header" type="button" onclick="toggleSection(this)">
          详细记录 <span class="collapse-arrow">▶</span>
        </h2>
        <div class="record-list collapsed">
          ${detail.segments.map(segment => `
            <div class="record-item" data-segment-time="${escapeHtml(segment.time)}">
              <div class="record-time">${escapeHtml(segment.time)}</div>
              <div class="record-body">
                <span class="record-dot"></span>
                <div class="record-card">
                  <div class="record-summary seg-distilled">${getSegmentDistillation(segment, meta)}</div>
                  <div class="record-toggle"><button class="raw-btn" type="button" onclick="toggleRawText(this)">显示原文</button></div>
                  <div class="record-raw seg-raw">${fmtText(segment.text || '')}</div>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      ${renderScreenActivity(detail.screen_events)}

      <section class="article-section">
        <h2>数据图表</h2>
        <div class="charts-grid">
          <div class="chart-card"><h3>时段热度</h3><canvas id="chartTime"></canvas></div>
        </div>
      </section>
    </article>
  `;
  document.getElementById('settingsBtn')?.classList.remove('active');
  setTimeout(initCharts, 0);
}
```

- [ ] **Step 3: Verify JS syntax**

```bash
cd ~/Desktop/openmy-clean && node -c app/static/app.js && echo "JS syntax OK"
```

- [ ] **Step 4: Browser verify daily report**

Click any date in the sidebar. Confirm:
- Stats bar shows record count, word count, time span
- AI summary uses new gradient callout with blue left border
- Meta panels (events/intents/facts/decisions) unchanged
- Collapsible records work
- Charts render

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/openmy-clean && git add app/static/app.js && git commit -m "feat: upgrade daily report with stats bar and summary callout v2"
```

---

### Task 7: JS — Replace renderReportPage + renderWeeklyReport + renderMonthlyReport (Weekly/Monthly)

**Files:**
- Modify: `app/static/app.js:849-934` (replace three functions)

- [ ] **Step 1: Locate the functions**

```bash
cd ~/Desktop/openmy-clean && grep -n "function renderReportPage\|function renderWeeklyReport\|function renderMonthlyReport" app/static/app.js
```

Expected: lines ~849, ~902, ~919

- [ ] **Step 2: Replace all three functions**

Replace `renderReportPage`, `renderWeeklyReport`, and `renderMonthlyReport` with:

```javascript
function renderReportPage(title, dates, extraMeta = '', isWeekly = false) {
  const main = document.getElementById('main');
  if (!dates.length) {
    main.innerHTML = `<div class="report-page"><h1>${escapeHtml(title)}</h1><div class="report-meta">当前没有可汇总的数据。</div></div>`;
    return;
  }

  const totalSegments = dates.reduce((sum, item) => sum + (item.segments || 0), 0);
  const totalWords = dates.reduce((sum, item) => sum + (item.word_count || 0), 0);
  const activeDays = dates.filter(item => item.segments > 0).length;

  const activeProjects = (state.context.active_projects || []).map(item => item.title || item.project_id).filter(Boolean);
  const projectItems = activeProjects.slice(0, 4).map(name => `${name}(${countKeywordDays(name, dates)}d)`);
  const decisionItems = uniqueTextItems(
    dates.flatMap(item => (item.decisions || []).map(d => d.decision || d.what || '')),
    4,
  );
  const loopItems = uniqueTextItems(
    dates.flatMap(item => (item.todos || []).map(t => t.task || t.what || '')),
    4,
  );

  const allSummaries = dates.map(item => item.summary || '').filter(Boolean);
  const highlightText = allSummaries.length > 0
    ? allSummaries.reduce((a, b) => a.length > b.length ? a : b, '').slice(0, 200)
    : '';

  const maxSegments = Math.max(...dates.map(d => d.segments || 0), 1);

  main.innerHTML = `
    <div class="report-page">
      <h1>${escapeHtml(title)}</h1>
      <div class="report-meta">${escapeHtml(extraMeta)}</div>

      <div class="stats-row" style="margin-top:24px">
        <div class="stat-card">
          <div class="stat-card-value">${activeDays}</div>
          <div class="stat-card-label">活跃天数</div>
          ${dates.length > activeDays ? `<div class="stat-card-delta negative">${dates.length}天中</div>` : ''}
        </div>
        <div class="stat-card">
          <div class="stat-card-value">${totalSegments}</div>
          <div class="stat-card-label">录音段数</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-value">${fmtNum(totalWords)}</div>
          <div class="stat-card-label">总字数</div>
        </div>
      </div>

      ${isWeekly ? `
      <div class="section-kicker" style="margin-bottom:12px">每日活跃度</div>
      <div class="week-heatmap">
        ${dates.slice().reverse().map((item, i) => {
          const seg = item.segments || 0;
          const pct = Math.round((seg / maxSegments) * 100);
          const dayLabel = formatFriendlyDate(item.date);
          return `
            <div class="week-heatmap-day ${seg > 0 ? 'active' : ''}">
              <div class="heatmap-label">${escapeHtml(dayLabel)}</div>
              <div class="heatmap-bar-wrapper">
                <div class="heatmap-bar" style="height:${Math.max(pct, 6)}%"></div>
              </div>
              <div class="heatmap-count">${seg}</div>
            </div>`;
        }).join('')}
      </div>` : ''}

      ${highlightText ? `
      <div class="week-highlight">
        <div class="week-highlight-label">${isWeekly ? '本周高亮' : '本月高亮'}</div>
        <div class="week-highlight-text">${escapeHtml(truncateSummary(highlightText))}</div>
      </div>` : ''}

      ${projectItems.length ? `<div class="report-block">
        <div class="section-kicker">项目</div>
        <div class="chip-list-v2">${projectItems.map(p => `<span class="chip-v2">${escapeHtml(p)}</span>`).join('')}</div>
      </div>` : ''}

      ${decisionItems.length ? `<div class="report-block">
        <div class="section-kicker">决策</div>
        <div class="chip-list-v2">${decisionItems.map(d => `<span class="chip-v2">${escapeHtml(d)}</span>`).join('')}</div>
      </div>` : ''}

      ${loopItems.length ? `<div class="report-block">
        <div class="section-kicker">待跟进</div>
        <div class="chip-list-v2">${loopItems.map(l => `<span class="chip-v2">${escapeHtml(l)}</span>`).join('')}</div>
      </div>` : ''}

      <div class="report-block">
        <div class="section-kicker">每日概要</div>
        <div class="daily-link-list-v2">
          ${dates.map(item => `
            <button class="daily-link-v2" type="button" onclick="loadDate('${escapeHtml(item.date)}')">
              <span class="dl-date">${escapeHtml(formatFriendlyDate(item.date))}</span>
              <span class="dl-summary">${escapeHtml(truncateSummary(item.summary || item.timeline?.[0]?.preview || ''))}</span>
              <span class="dl-count">${item.segments || 0}条</span>
            </button>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

function renderWeeklyReport() {
  closeSidebar();
  setRoute('weekly');
  state.currentDate = '';
  const dates = latestWeekDates();
  if (!dates.length) {
    renderReportPage('周报', [], '', true);
    return;
  }
  renderReportPage(
    `周报 ${formatRangeLabel(dates[dates.length - 1].date, dates[0].date)}`,
    dates,
    `${dates.length}天有记录`,
    true,
  );
}

function renderMonthlyReport() {
  closeSidebar();
  setRoute('monthly');
  state.currentDate = '';
  const dates = latestMonthDates();
  if (!dates.length) {
    renderReportPage('月报', [], '', false);
    return;
  }
  renderReportPage(
    `月报 ${dates[0].date.slice(0, 7)}`,
    dates,
    `本月 ${dates.length}天有记录`,
    false,
  );
}
```

- [ ] **Step 3: Verify JS syntax**

```bash
cd ~/Desktop/openmy-clean && node -c app/static/app.js && echo "JS syntax OK"
```

- [ ] **Step 4: Browser verify weekly report**

Click "周报" in sidebar. Confirm:
- 3 stat cards (active days, segments, words)
- 7-day heatmap bar chart renders
- Highlight quote with gradient background
- Chips render with pill style
- Daily summary list uses new grid layout
- Click individual day still works

- [ ] **Step 5: Browser verify monthly report**

Click "月报" in sidebar. Confirm:
- Same stat cards
- No heatmap (only for weekly)
- Highlight shows "本月高亮" label
- All other sections render

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/openmy-clean && git add app/static/app.js && git commit -m "feat: upgrade weekly and monthly reports with stats, heatmap, and highlight"
```

---

### Task 8: Full Regression — Dark Mode + Mobile + Tests

**Files:**
- Read: all modified files

- [ ] **Step 1: Test dark mode**

In browser at `localhost:8420`, open Settings, switch to dark mode. Check ALL three pages:
- Welcome hero gradient is subtle dark (not washed out)
- Summary callout v2 gradient adapts
- Week highlight gradient adapts
- All text readable
- No hard-coded colors bleeding through

- [ ] **Step 2: Test mobile viewport**

In browser DevTools, toggle device toolbar (Cmd+Shift+M), set width to 375px. Check:
- Stats row stacks to single column
- Card grid stacks to single column
- Heatmap stays 7-column but compresses
- Welcome hero text shrinks
- Daily links readable

- [ ] **Step 3: Test existing features**

Verify these still work:
- Cmd+K spotlight search
- Click date → daily report
- Select text in daily report → correction popover appears
- Upload drop zone works (drag a file)
- Settings panel opens/closes
- Theme color switcher (try purple, green, amber)

- [ ] **Step 4: Run full test suite**

```bash
cd ~/Desktop/openmy-clean && python3 -m pytest tests/ -q
```

Expected: 449+ tests pass, 0 failures

- [ ] **Step 5: Final commit**

```bash
cd ~/Desktop/openmy-clean && git add -A && git commit -m "test: verify visual upgrade v2 — all tests pass"
```

---

## Acceptance Criteria Checklist

Must pass ALL:

1. [ ] Homepage has Welcome Hero gradient with today's date
2. [ ] Homepage has 3 stat cards (active days, segments, words)
3. [ ] Homepage has today summary card
4. [ ] Homepage has project/loop cards when context data exists
5. [ ] Daily report has stats bar (count, words, time span)
6. [ ] Daily report AI summary uses gradient callout v2
7. [ ] Daily report meta panels unchanged
8. [ ] Weekly report has 3 stat cards
9. [ ] Weekly report has 7-day heatmap
10. [ ] Weekly report has highlight quote
11. [ ] Dark mode correct for all new elements
12. [ ] Mobile layout doesn't break (≤900px)
13. [ ] All existing features work (search, correction, upload, settings)
14. [ ] `python3 -m pytest tests/ -q` all green

Must NOT:
- Import Google Fonts
- Use emoji
- Use purple as default accent
- Modify API endpoints
- Modify index.html structure
