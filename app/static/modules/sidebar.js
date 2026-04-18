// sidebar.js — 侧边栏
import { state } from './state.js';
import { fetchJson } from './api.js';
import { escapeHtml, fmtNum, renderEmptyState } from './utils.js';
import { formatFriendlyDate, getVisibleDates } from './dates.js';

export async function loadSidebar() {
  const [dates, stats] = await Promise.all([
    fetchJson('/api/dates', []),
    fetchJson('/api/stats', { total_dates: 0, total_segments: 0, total_words: 0, role_distribution: {} }),
  ]);

  state.allDates = dates || [];
  state.stats = stats || {};
  renderSidebar();
}

export function renderSidebar() {
  const stats = state.stats || {};
  document.getElementById('stats').innerHTML = `
    <span class="stat-item"><span class="stat-num">${stats.total_dates || 0}</span>天</span>
    <span class="stat-item"><span class="stat-num">${stats.total_segments || 0}</span>条</span>
    <span class="stat-item"><span class="stat-num">${fmtNum(stats.total_words || 0)}</span>字</span>
  `;

  document.getElementById('homeBtn')?.classList.toggle('active', state.route === 'home');
  document.getElementById('weeklyBtn')?.classList.toggle('active', state.route === 'weekly');
  document.getElementById('monthlyBtn')?.classList.toggle('active', state.route === 'monthly');

  const dateList = document.getElementById('dateList');
  const visibleDates = getVisibleDates();
  if (!visibleDates.length) {
    dateList.innerHTML = renderEmptyState('暂无记录');
    return;
  }

  dateList.innerHTML = visibleDates.map((item) => `
    <button class="date-item ${state.route === 'date' && item.date === state.currentDate ? 'active' : ''}" type="button" onclick="loadDate('${escapeHtml(item.date)}')">
      <span>${escapeHtml(formatFriendlyDate(item.date))}</span>
      <span class="meta">${item.segments}条</span>
    </button>
  `).join('');
}



export function toggleSidebar() {
  document.querySelector('.app')?.classList.toggle('sidebar-open');
}

export function closeSidebar() {
  document.querySelector('.app')?.classList.remove('sidebar-open');
}
