// search.js — Spotlight 搜索
import { state } from './state.js';
import { fetchJson } from './api.js';
import { escapeHtml, highlightQuerySnippet, truncateSummary } from './utils.js';
import { closeSidebar } from './sidebar.js';
import { loadDate, scrollToSegment } from './daily.js';
import { openSettings, closeSettingsOverlay } from './settings.js';
import { formatFriendlyDate } from './dates.js';

export function recentSpotlightResults() {
  return state.allDates.slice(0, 5).map((item) => ({
    date: item.date,
    time: item.timeline?.[0]?.time || '',
    context: truncateSummary(item.summary || item.timeline?.[0]?.preview || ''),
  }));
}

export function renderSpotlightResults(items, query = '') {
  const container = document.getElementById('spotlightResults');
  if (!items.length) {
    container.innerHTML = query
      ? '<div class="spotlight-empty">找不到相关的上下文</div>'
      : `
        <div class="spotlight-empty">
          <div style="font-size:13px;color:var(--text-secondary);">试试输入关键词搜索所有录音</div>
          <div style="margin-top:8px;font-size:12px;color:var(--text-light);">支持搜索日期、项目名、对话内容</div>
        </div>
      `;
    return;
  }

  const grouped = items.reduce((acc, item) => {
    acc[item.date] = acc[item.date] || [];
    acc[item.date].push(item);
    return acc;
  }, {});
  let index = 0;
  container.innerHTML = Object.entries(grouped).map(([date, entries]) => `
    <div class="spotlight-group-label">${escapeHtml(formatFriendlyDate(date))}</div>
    ${entries.map((item) => {
      const itemIndex = index++;
      const hasAudio = item.has_audio || item.source_type === 'audio';
      const friendlyDate = formatFriendlyDate(item.date);
      return `
        <button class="spotlight-result-item ${itemIndex === state.spotlightIndex ? 'active' : ''}" data-spotlight-index="${itemIndex}" onclick="jumpToSearchResult('${escapeHtml(item.date)}', '${escapeHtml(item.time || '')}', '${escapeHtml(query)}')">
          <strong style="display:block;margin-bottom:4px;color:var(--text);font-size:13px">${escapeHtml(friendlyDate)}${item.time ? ` · ${escapeHtml(item.time)}` : ''}${hasAudio ? '<span class="search-audio-badge">录音</span>' : ''}</strong>
          <div class="muted" style="font-size:12px;line-height:1.5">${highlightQuerySnippet(item.context || item.raw_context || '', query)}</div>
        </button>
      `;
    }).join('')}
  `).join('');
}

export function setSpotlightSelection(nextIndex) {
  state.spotlightIndex = nextIndex;
  document.querySelectorAll('.spotlight-result-item').forEach((node) => {
    node.classList.toggle('active', Number(node.dataset.spotlightIndex) === state.spotlightIndex);
  });
}

export function handleSpotlightKeydown(event) {
  if (!document.getElementById('spotlightOverlay').classList.contains('active')) return;
  const items = Array.from(document.querySelectorAll('.spotlight-result-item'));
  if (!items.length) return;

  if (event.key === 'ArrowDown') {
    event.preventDefault();
    setSpotlightSelection((state.spotlightIndex + 1) % items.length);
    items[state.spotlightIndex]?.scrollIntoView({ block: 'nearest' });
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    setSpotlightSelection((state.spotlightIndex - 1 + items.length) % items.length);
    items[state.spotlightIndex]?.scrollIntoView({ block: 'nearest' });
  } else if (event.key === 'Enter' && state.spotlightIndex >= 0) {
    event.preventDefault();
    items[state.spotlightIndex]?.click();
  }
}

export function openSpotlight() {
  const overlay = document.getElementById('spotlightOverlay');
  const input = document.getElementById('spotlightInput');
  overlay.classList.add('active');
  input.value = '';
  input.focus();
  runSearchSpotlight('');
}

export function closeSpotlight(e) {
  if (e && e.target !== document.getElementById('spotlightOverlay')) return;
  document.getElementById('spotlightOverlay').classList.remove('active');
  state.searchResults = [];
  state.spotlightIndex = -1;
}

document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    openSpotlight();
  }
  if ((e.metaKey || e.ctrlKey) && e.key === ',') {
    e.preventDefault();
    const overlay = document.getElementById('settingsOverlay');
    if (overlay.classList.contains('active')) {
      closeSettingsOverlay();
    } else {
      openSettings();
    }
  }
  if (e.key === 'Escape') {
    closeSpotlight();
    closeSettingsOverlay();
    closeSidebar();
  }
});

export async function runSearchSpotlight(query) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    state.searchResults = [];
    state.spotlightIndex = -1;
    renderSpotlightResults([], '');
    return;
  }

  state.searchResults = await fetchJson(`/api/search?q=${encodeURIComponent(normalizedQuery)}`, []);
  if (!state.searchResults.length) {
    state.spotlightIndex = -1;
    renderSpotlightResults([], normalizedQuery);
    return;
  }
  state.spotlightIndex = 0;
  renderSpotlightResults(state.searchResults, normalizedQuery);
}

export async function jumpToSearchResult(date, time, query = '') {
  closeSpotlight();
  if (state.currentDate !== date) {
    await loadDate(date, time, query);
  } else {
    requestAnimationFrame(() => scrollToSegment(time, query));
  }
}
