// daily.js — 日详情页
import { state } from './state.js';
import { fetchJson } from './api.js';
import { setRoute } from './router.js';
import { renderSidebar, closeSidebar } from './sidebar.js';
import { buildDailySummary, formatPageDate, looksWeakSummary } from './dates.js';
import { escapeHtml, fmtNum, fmtText, plainText, showToast } from './utils.js';
import { renderScenePlaybackControl, stopScenePlayback, syncScenePlaybackUi } from './playback.js';

function renderLoadingSkeleton() {
  return `
    <div class="loading-skeleton">
      <div class="skeleton-line skeleton-title"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line skeleton-short"></div>
    </div>
  `;
}

function normalizeRoleKey(rawRole) {
  if (!rawRole) return '';
  const value = typeof rawRole === 'string'
    ? rawRole
    : rawRole.scene_type || rawRole.category || rawRole.scene_type_label || rawRole.addressed_to || rawRole.relation_label || '';
  const normalized = String(value).trim().toLowerCase();

  if (!normalized) return '';
  if (normalized === 'ai' || normalized === 'ai助手' || normalized === '助手') return 'ai';
  if (normalized === 'merchant' || ['商家', '服务员', '客服'].some((item) => normalized.includes(item))) return 'merchant';
  if (normalized === 'pet' || normalized.includes('宠物')) return 'pet';
  if (normalized === 'self' || ['自己', '自言自语', '备忘'].some((item) => normalized.includes(item))) return 'self';
  if (normalized === 'interpersonal' || ['伴侣', '家人', '朋友', '同事', '聊天', '人际'].some((item) => normalized.includes(item))) return 'interpersonal';
  return '';
}

function getInlineProjectStyle(item, meta) {
  const hintedRole = (meta?.role_hints || []).find((hint) => hint?.time && hint.time === item.time)?.role;
  const roleKey = normalizeRoleKey(item.role || hintedRole);
  return roleKey
    ? `background:var(--role-${roleKey}-bg);color:var(--role-${roleKey})`
    : 'background:var(--bg-tag);color:var(--text-secondary)';
}

export async function loadDate(date, focusTime = '', focusQuery = '') {
  closeSidebar();
  stopScenePlayback();
  const main = document.getElementById('main');
  if (main) {
    main.innerHTML = renderLoadingSkeleton();
  }
  // Template routes: /api/date/${date}/meta and /api/date/${date}/briefing
  const [detail, meta, briefing] = await Promise.all([
    fetchJson(`/api/date/${date}`, null),
    fetchJson(`/api/date/${date}/meta`, null),
    fetchJson(`/api/date/${date}/briefing`, null),
  ]);

  if (!detail) {
    showToast(`日期 ${date} 不存在`);
    return;
  }

  setRoute('date');
  state.currentDate = date;
  state.currentData = detail;
  state.currentMeta = meta || detail.meta || {};
  state.currentBriefing = briefing || null;
  renderSidebar();
  renderDayLayout();
  window.scrollTo({ top: 0, behavior: 'auto' });

  if (focusTime) {
    requestAnimationFrame(() => scrollToSegment(focusTime, focusQuery));
  }
}

export function renderDayLayout() {
  const detail = state.currentData;
  const meta = state.currentMeta || {};
  if (!detail) return;

  const summaryText = buildDailySummary(detail, meta);
  const times = detail.segments.map((segment) => segment.time).filter(Boolean).sort();
  const timeSpan = times.length >= 2 ? `${times[0]} - ${times[times.length - 1]}` : (times[0] || '');
  const summaryHint = looksWeakSummary(meta.daily_summary || state.currentBriefing?.summary || '')
    ? '这段摘要还是有点空，我先把洞察、决定和待办拼成一句更像人话的小结。'
    : '';

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
        ${summaryHint ? `<div class="summary-hint">${escapeHtml(summaryHint)}</div>` : ''}
      </section>` : ''}

      ${renderMetaPanels(meta)}

      <section class="article-section">
        <h2 class="collapsible-header" type="button" onclick="toggleSection(this)">
          详细记录 <span class="collapse-arrow">▶</span>
        </h2>
        <div class="record-list collapsed">
          ${detail.segments.map((segment) => `
            <div class="record-item" data-segment-time="${escapeHtml(segment.time)}">
              <div class="record-time">${escapeHtml(segment.time)}</div>
              <div class="record-body">
                <span class="record-dot"></span>
                <div class="record-card">
                  <div class="record-summary seg-distilled">${getSegmentDistillation(segment, meta)}</div>
                  ${renderScenePlaybackControl(segment)}
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
        <div class="chart-card" style="max-width:100%"><h3>时段热度</h3><canvas id="chartTime" style="height:240px"></canvas></div>
      </section>

      <div class="day-footer">
        <button class="action-btn" type="button" onclick="renderHomePage()">← 返回首页</button>
        <button class="action-btn" type="button" onclick="window.scrollTo({top:0,behavior:'smooth'})">↑ 回到顶部</button>
      </div>
    </article>
  `;
  document.getElementById('settingsBtn')?.classList.remove('active');
  syncScenePlaybackUi();
  setTimeout(initCharts, 0);
}


export function renderScreenActivity(events) {
  if (!events || !events.length) return '';
  return `
    <section class="article-section">
      <h2>屏幕活动</h2>
      <div class="screen-activity-list">
        ${events.map((item) => {
          const timeStart = item.first_seen ? new Date(item.first_seen).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '';
          const timeEnd = item.last_seen ? new Date(item.last_seen).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '';
          const timeRange = timeStart === timeEnd ? timeStart : `${timeStart} – ${timeEnd}`;
          return `
            <div class="screen-activity-item">
              <span class="screen-activity-app">${escapeHtml(item.app)}</span>
              <span class="screen-activity-time">${escapeHtml(timeRange)}</span>
            </div>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

export function renderMetaPanels(meta) {
  const groups = [
    { key: 'events', title: '发生了什么', dot: '#2eaadc' },
    { key: 'intents', title: '打算做什么', dot: '#0f7b6c' },
    { key: 'facts', title: '记住了什么', dot: '#64748b' },
    { key: 'decisions', title: '决定了什么', dot: '#d9730d' },
  ];

  const cards = groups.map((group) => {
    const items = meta?.[group.key] || [];
    if (!items.length) return '';
    return `<section class="meta-section" style="--section-color:${group.dot}">
      <div class="prop-card">
      <div class="prop-card-title"><span class="dot" style="background:${group.dot}"></span>${group.title} <span class="prop-count">${items.length}</span></div>
      ${items.map((item) => {
        const time = escapeHtml(item.time || '');
        const project = escapeHtml(item.project || item.topic || '');
        const summary = escapeHtml(plainText(item.summary || item.what || item.task || item.content || item.decision || item.fact || item.intent || ''));
        const projectStyle = getInlineProjectStyle(item, meta);
        return `<div class="prop-item">
          ${time ? `<span class="time-tag">${time}</span>` : ''}
          ${summary}${project ? ` <span class="inline-project" style="${projectStyle}">(${project})</span>` : ''}
        </div>`;
      }).join('')}
      </div>
    </section>`;
  }).filter(Boolean);

  return cards.length ? `<div class="props-grid">${cards.join('')}</div>` : '';
}

export function getSegmentDistillation(segment, meta) {
  if (segment.summary) return escapeHtml(plainText(segment.summary));
  return escapeHtml(plainText(segment.preview || segment.text || '').slice(0, 200));
}

export function toggleSection(header) {
  const content = header?.nextElementSibling;
  const arrow = header?.querySelector('.collapse-arrow');
  if (!content || !arrow) return;
  const isCollapsed = content.classList.toggle('collapsed');
  arrow.textContent = isCollapsed ? '▶' : '▼';
}

export function initCharts() {
  if (!state.currentData) return;
  if (typeof Chart === 'undefined') return;
  state.chartInstances.forEach((chart) => chart.destroy());
  state.chartInstances = [];

  const timeCounts = {};
  state.currentData.segments.forEach((segment) => {
    const hourText = String(segment.time || '').split(':')[0];
    if (!/^\d{1,2}$/.test(hourText)) return;
    const hour = `${hourText.padStart(2, '0')}:00`;
    timeCounts[hour] = (timeCounts[hour] || 0) + plainText(segment.text || '').length;
  });

  const timeCanvas = document.getElementById('chartTime');
  if (timeCanvas) {
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#2eaadc';
    const labels = Array.from({ length: 24 }, (_, h) => `${h}`);
    const values = labels.map((_, i) => {
      const key = `${String(i).padStart(2, '0')}:00`;
      return timeCounts[key] || 0;
    });
    state.chartInstances.push(new Chart(timeCanvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: '字数',
          data: values,
          backgroundColor: values.map((value) => (value > 0 ? accent : 'rgba(148, 163, 184, 0.35)')),
          borderRadius: 6,
          barPercentage: 0.6,
          borderSkipped: false,
          minBarLength: 4,
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              autoSkip: false,
              maxRotation: 0,
              minRotation: 0,
              font: { size: 11 },
              callback: function(value, index) {
                return index % 3 === 0 ? index + '时' : '';
              },
            },
          },
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
          },
        },
      },
    }));
  }
}

export function optionMarkup(items, getter) {
  if (!items || !items.length) {
    return '<option value="">暂无可选项</option>';
  }
  return items.map((item) => {
    const value = getter(item);
    return `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`;
  }).join('');
}

export function toggleRawText(button) {
  const rawNode = button.parentElement.nextElementSibling;
  const visible = !rawNode.classList.contains('visible');
  rawNode.classList.toggle('visible', visible);
  button.innerHTML = visible ? '隐藏原文' : '显示原文';
  button.style.color = visible ? '#fff' : 'var(--text-secondary)';
  button.style.background = visible ? 'var(--text)' : 'var(--bg-sidebar)';
}

export function scrollToSegment(time, query = '') {
  document.querySelectorAll('.highlight-target').forEach(n => n.classList.remove('highlight-target'));
  const nodes = Array.from(document.querySelectorAll('[data-segment-time]'));
  const target = nodes.find((node) => node.dataset.segmentTime === time);
  if (!target) return;
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  target.classList.add('highlight-target');

  const rawNode = target.querySelector('.seg-raw');
  const btnNode = target.querySelector('.raw-btn');
  if (rawNode && !rawNode.classList.contains('visible')) {
    rawNode.classList.add('visible');
    if (btnNode) {
      btnNode.innerHTML = '隐藏原文';
      btnNode.style.color = '#fff';
      btnNode.style.background = 'var(--text)';
    }
  }

  if (query && rawNode) {
    let originalHtml = rawNode.dataset.originalHtml;
    if (!originalHtml) {
      originalHtml = rawNode.innerHTML;
      rawNode.dataset.originalHtml = originalHtml;
    }
    try {
      const escapeRegExp = (string) => string.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
      const escapedQuery = escapeRegExp(query);
      const regex = new RegExp(`(${escapedQuery})`, 'gi');
      rawNode.innerHTML = originalHtml.replace(regex, '<mark class="search-highlight">$1</mark>');
    } catch(e) {
      console.error(e);
    }
  }
}
