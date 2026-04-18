// reports.js — 周报和月报
import { state } from './state.js';
import { setRoute } from './router.js';
import { closeSidebar } from './sidebar.js';
import { buildWeeklySlots, countKeywordDays, deriveProjectItemsFromDates, formatFriendlyDate, formatRangeLabel, latestMonthDates, latestWeekDates, uniqueTextItems } from './dates.js';
import { escapeHtml, fmtNum, truncateSummary } from './utils.js';

export function renderReportPage(title, dates, extraMeta = '', isWeekly = false) {
  const main = document.getElementById('main');
  if (!dates.length) {
    main.innerHTML = `<div class="report-page"><h1>${escapeHtml(title)}</h1><div class="report-meta">当前没有可汇总的数据。</div></div>`;
    return;
  }

  const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#2563EB';
  const displayDates = isWeekly ? buildWeeklySlots(dates) : dates;
  const totalSegments = displayDates.reduce((sum, item) => sum + (item.segments || 0), 0);
  const totalWords = displayDates.reduce((sum, item) => sum + (item.word_count || 0), 0);
  const activeDays = displayDates.filter((item) => item.segments > 0).length;

  const activeProjects = (state.context.active_projects || []).map((item) => item.title || item.project_id).filter(Boolean);
  const projectItems = activeProjects.length ? activeProjects.slice(0, 4).map((name) => `${name}(${countKeywordDays(name, displayDates)}d)`) : deriveProjectItemsFromDates(displayDates, 4).map((item) => `${item.label}(${item.meta.replace(' 天出现', 'd')})`);
  const decisionItems = uniqueTextItems(
    displayDates.flatMap((item) => (item.decisions || []).map((decision) => decision.decision || decision.what || '')),
    4,
  );
  const loopItems = uniqueTextItems(
    displayDates.flatMap((item) => (item.todos || []).map((todo) => todo.task || todo.what || '')),
    4,
  );

  const allSummaries = displayDates.map((item) => item.summary || item.timeline?.[0]?.preview || '').filter(Boolean);
  const highlightText = allSummaries.length
    ? allSummaries.reduce((longest, current) => (longest.length > current.length ? longest : current), '').slice(0, 200)
    : '';

  const maxSegments = Math.max(...displayDates.map((item) => item.segments || 0), 1);
  const sparseNote = isWeekly && activeDays <= 1
    ? `这周目前只录到 ${activeDays || 0} 天，我先把 7 天骨架铺出来，免得周报只剩一根孤零零的柱子。`
    : '';
  const highlightLabel = isWeekly ? '本周高亮' : '本月高亮';

  main.innerHTML = `
    <div class="report-page">
      <h1>${escapeHtml(title)}</h1>
      <div class="report-meta">${escapeHtml(extraMeta)}</div>

      <div class="stats-row" style="margin-top:24px">
        <div class="stat-card">
          <div class="stat-card-value">${activeDays}</div>
          <div class="stat-card-label">活跃天数</div>
          ${displayDates.length > activeDays ? `<div class="stat-card-delta negative">${displayDates.length}天中</div>` : ''}
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

      ${sparseNote ? `<div class="week-sparse-note">${escapeHtml(sparseNote)}</div>` : ''}

      ${isWeekly ? `
      <div class="section-kicker" style="margin-bottom:12px">每日活跃度</div>
      <div class="week-heatmap">
        ${displayDates.map((item) => {
          const segments = item.segments || 0;
          const percent = Math.round((segments / maxSegments) * 100);
          const dayLabel = formatFriendlyDate(item.date).replace(/[0-9]+月/, '').trim();
          return `
            <div class="week-heatmap-day ${segments > 0 ? 'active' : 'is-empty'}">
              <div class="heatmap-label">${escapeHtml(dayLabel || '')}</div>
              <div class="heatmap-bar-wrapper">
                <div class="heatmap-bar" style="height:${Math.max(percent, 6)}%;${segments > 0 ? `background:${accent};` : ''}"></div>
              </div>
              <div class="heatmap-count">${segments}</div>
            </div>`;
        }).join('')}
      </div>` : ''}

      ${highlightText ? `
      <div class="week-highlight">
        <div class="week-highlight-label" style="color:${accent}">${highlightLabel}</div>
        <div class="week-highlight-text">${escapeHtml(truncateSummary(highlightText, 90))}</div>
      </div>` : ''}

      ${projectItems.length ? `<div class="report-block">
        <div class="section-kicker">项目</div>
        <div class="chip-list-v2">${projectItems.map((item) => `<span class="chip-v2">${escapeHtml(item)}</span>`).join('')}</div>
      </div>` : ''}

      ${decisionItems.length ? `<div class="report-block">
        <div class="section-kicker">决策</div>
        <div class="chip-list-v2">${decisionItems.map((item) => `<span class="chip-v2">${escapeHtml(item)}</span>`).join('')}</div>
      </div>` : ''}

      ${loopItems.length ? `<div class="report-block">
        <div class="section-kicker">待跟进</div>
        <div class="chip-list-v2">${loopItems.map((item) => `<span class="chip-v2">${escapeHtml(item)}</span>`).join('')}</div>
      </div>` : ''}

      <div class="report-block">
        <div class="section-kicker">每日概要</div>
        <div class="daily-link-list-v2">
          ${displayDates.map((item) => `
            <button class="daily-link-v2" type="button" ${item.isPlaceholder ? 'disabled' : `onclick="loadDate('${escapeHtml(item.date)}')"`}>
              <span class="dl-date">${escapeHtml(formatFriendlyDate(item.date))}</span>
              <span class="dl-summary">${escapeHtml(item.isPlaceholder ? '这一天还没有录音' : truncateSummary(item.summary || item.timeline?.[0]?.preview || ''))}</span>
              <span class="dl-count">${item.segments || 0}条</span>
            </button>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}


export function renderWeeklyReport() {
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


export function renderMonthlyReport() {
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
