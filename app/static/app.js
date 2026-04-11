const PIPELINE_KIND_LABELS = {
  context: '刷新上下文',
  clean: '清理文本',
  roles: '识别对象',
  distill: '整理摘要',
  briefing: '生成日报',
  run: '重新运行',
};

const PIPELINE_STATUS_LABELS = {
  queued: '排队中',
  running: '运行中',
  succeeded: '已完成',
  failed: '失败',
};

const state = {
  allDates: [],
  stats: null,
  route: 'home',
  currentDate: '',
  currentData: null,
  currentMeta: null,
  currentBriefing: null,
  context: {},
  loops: [],
  projects: [],
  decisions: [],
  corrections: [],
  searchResults: [],
  spotlightIndex: -1,
  jobs: [],
  selectedJobId: '',
  selectedJobDetail: null,
  handledCompletedJobs: new Set(),
  chartInstances: [],
  contextQuery: {
    kind: 'project',
    query: '',
    result: null,
    loading: false,
  },
  screenSettings: {
    enabled: true,
    participation_mode: 'summary_only',
    exclude_apps: [],
    exclude_domains: [],
    exclude_window_keywords: [],
  },
};

let searchTimer = null;

function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('visible'), 2600);
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function plainText(value) {
  return String(value || '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/<[^>]+>/g, '')
    .trim();
}

function fmtText(value) {
  const safe = escapeHtml(value || '');
  return safe.split(/\n+/).map((paragraph) => paragraph.trim() ? `<p>${paragraph}</p>` : '').join('');
}

function fmtNum(value) {
  const number = Number(value || 0);
  if (number >= 10000) return `${(number / 10000).toFixed(1)}万`;
  if (number >= 1000) return `${(number / 1000).toFixed(1)}k`;
  return String(number);
}

function renderEmptyState(text) {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

function renderEventList(items, renderItem, emptyText) {
  if (!items || !items.length) {
    return renderEmptyState(emptyText);
  }
  return items.map(renderItem).join('');
}

function renderContextQueryResult() {
  const queryState = state.contextQuery || {};
  const result = queryState.result;
  if (queryState.loading) {
    return `
      <div id="contextQueryResults" class="search-stack">
        <div class="event-item">正在查询结构化上下文...</div>
      </div>
      <div id="contextQueryEvidence" class="search-stack"></div>
    `;
  }

  if (!result) {
    const projectPreset = state.projects[0]?.title || 'OpenMy';
    const loopPreset = state.loops[0]?.title || '';
    return `
      <div id="contextQueryResults" class="search-stack">
        <div class="event-item">还没开始查。你可以直接查项目、待办、证据。</div>
        <div class="inline-actions" style="margin-top:8px;flex-wrap:wrap">
          <button class="action-btn" type="button" onclick="runContextQuery('project', '${escapeHtml(projectPreset)}')">查项目</button>
          <button class="action-btn" type="button" onclick="runContextQuery('open', '')">查未关闭待办</button>
          <button class="action-btn" type="button" onclick="runContextQuery('closed', '')">查已关闭事项</button>
          ${loopPreset ? `<button class="action-btn" type="button" onclick="runContextQuery('evidence', '${escapeHtml(loopPreset)}')">查证据</button>` : ''}
        </div>
      </div>
      <div id="contextQueryEvidence" class="search-stack"></div>
    `;
  }

  const currentHits = result.current_hits || [];
  const historyHits = result.history_hits || [];
  const dailyRollups = result.daily_rollups || [];
  const conflicts = result.conflicts || [];
  const evidence = result.evidence || [];
  const temporal = result.temporal_buckets || {};

  const hitBlock = (title, items, emptyText) => `
    <div>
      <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">${title}</div>
      ${items.length ? items.map((item) => `
        <div class="event-item">
          <div><strong>${escapeHtml(item.title || item.summary || item.id || '')}</strong></div>
          <div class="muted">${escapeHtml(plainText(item.summary || ''))}</div>
          <div class="muted" style="font-size:12px">${escapeHtml([item.date, item.time, item.current_state || item.status].filter(Boolean).join(' · '))}</div>
        </div>
      `).join('') : `<div class="empty-state">${escapeHtml(emptyText)}</div>`}
    </div>
  `;

  return `
    <div id="contextQueryResults" class="search-stack">
      <div class="callout" style="margin-bottom:16px">
        <div class="callout-body">${escapeHtml(result.summary || '暂无结果')}</div>
      </div>

      <div class="briefing-grid" style="margin-bottom:12px">
        ${hitBlock('当前命中', currentHits, '当前没有命中')}
        ${hitBlock('历史命中', historyHits, '历史没有命中')}
      </div>

      <div class="briefing-grid" style="margin-bottom:12px">
        ${hitBlock('跨日汇总', dailyRollups.map((item) => ({ title: item.date, summary: item.summary })), '暂无跨日汇总')}
        ${hitBlock('时态裁决', [
          { title: `进行中 ${temporal.current?.length || 0} 条`, summary: 'current' },
          { title: `未来 ${temporal.future?.length || 0} 条`, summary: 'future' },
          { title: `过去 ${temporal.past?.length || 0} 条`, summary: 'past' },
          { title: `已关闭 ${temporal.closed?.length || 0} 条`, summary: 'closed' },
        ], '暂无时态结果')}
      </div>

      <div>
        <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">冲突识别</div>
        ${conflicts.length ? conflicts.map((item) => `
          <div class="event-item">
            <div><strong>${escapeHtml(item.title || item.canonical_key || '')}</strong></div>
            <div class="muted">${escapeHtml(item.state_reason || item.conflict_type || '')}</div>
            <div class="muted" style="font-size:12px">${escapeHtml((item.variants || []).join(' / '))}</div>
          </div>
        `).join('') : '<div class="empty-state">当前没有结构化冲突</div>'}
      </div>
    </div>
    <div id="contextQueryEvidence" class="search-stack" style="margin-top:16px">
      <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">证据回链</div>
      ${evidence.length ? evidence.map((item) => `
        <button class="event-item" type="button" onclick="jumpToEvidence('${escapeHtml(item.date || '')}', '${escapeHtml(item.time_range || '')}', '${escapeHtml(queryState.query || '')}')">
          <div><strong>scene_id</strong> ${escapeHtml(item.scene_id || 'unknown')}</div>
          <div class="muted"><strong>quote</strong> ${escapeHtml(plainText(item.quote || item.scene_summary || item.source_path || ''))}</div>
          <div class="muted" style="font-size:12px">${escapeHtml([item.date, item.time_range].filter(Boolean).join(' · '))}</div>
        </button>
      `).join('') : '<div class="empty-state">没有可回链的证据</div>'}
    </div>
  `;
}

function formatPipelineKind(value) {
  return PIPELINE_KIND_LABELS[value] || value || '未知任务';
}

function formatPipelineStatus(value) {
  return PIPELINE_STATUS_LABELS[value] || value || '未知状态';
}

function formatPipelineStep(value) {
  if (!value) return '—';
  return PIPELINE_KIND_LABELS[value] || value;
}

function renderPipelineJobDetail() {
  const detail = state.selectedJobDetail;
  if (!detail) {
    return renderEmptyState('选择一条运行记录查看详情。');
  }
  return `
    <div class="event-item"><strong>流程</strong><br>${escapeHtml(formatPipelineKind(detail.kind))}</div>
    <div class="event-item"><strong>状态</strong><br>${escapeHtml(formatPipelineStatus(detail.status))}</div>
    <div class="event-item"><strong>当前步骤</strong><br>${escapeHtml(formatPipelineStep(detail.current_step))}</div>
    <div class="event-item"><strong>结果文件</strong><br>${escapeHtml((detail.artifacts || []).join(' / ') || '暂无')}</div>
    <pre class="job-log">${escapeHtml((detail.log_lines || []).join('\n') || '暂无日志')}</pre>
  `;
}

function parseIsoDate(dateStr) {
  const [year, month, day] = String(dateStr || '').split('-').map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

function formatShortDate(dateStr) {
  const date = parseIsoDate(dateStr);
  return `${date.getMonth() + 1}.${date.getDate()}`;
}

function formatRangeLabel(start, end) {
  return `${formatShortDate(start)}–${formatShortDate(end)}`;
}

function truncateSummary(text, maxLength = 20) {
  const summary = plainText(text || '');
  if (!summary) return '暂无摘要';
  return summary.length > maxLength ? `${summary.slice(0, maxLength)}…` : summary;
}

function latestDateInfo() {
  return [...state.allDates].sort((a, b) => b.date.localeCompare(a.date))[0] || null;
}

function filterDateRange(startDate, endDate) {
  return [...state.allDates]
    .filter((item) => item.date >= startDate && item.date <= endDate)
    .sort((a, b) => b.date.localeCompare(a.date));
}

function latestWeekDates() {
  const latest = latestDateInfo();
  if (!latest) return [];
  const anchor = parseIsoDate(latest.date);
  const day = anchor.getDay() || 7;
  const start = new Date(anchor);
  start.setDate(anchor.getDate() - day + 1);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const startLabel = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
  const endLabel = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`;
  return filterDateRange(startLabel, endLabel);
}

function latestMonthDates() {
  const latest = latestDateInfo();
  if (!latest) return [];
  const anchor = parseIsoDate(latest.date);
  const startLabel = `${anchor.getFullYear()}-${String(anchor.getMonth() + 1).padStart(2, '0')}-01`;
  return filterDateRange(startLabel, latest.date);
}

function countKeywordDays(keyword, dates) {
  if (!keyword) return 0;
  const pattern = keyword.toLowerCase();
  return dates.filter((item) => {
    const haystacks = [
      item.summary,
      ...(item.events || []).map((event) => event.what || event.summary || ''),
      ...(item.decisions || []).map((decision) => decision.decision || decision.what || ''),
      ...(item.todos || []).map((todo) => todo.task || todo.what || ''),
    ];
    return haystacks.some((entry) => String(entry || '').toLowerCase().includes(pattern));
  }).length;
}

function uniqueTextItems(items, limit = 4) {
  const values = [];
  const seen = new Set();
  items.forEach((item) => {
    const normalized = plainText(item || '');
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    values.push(normalized);
  });
  return values.slice(0, limit);
}

function setRoute(route) {
  state.route = route;
  document.getElementById('settingsBtn')?.classList.remove('active');
  renderSidebar();
}

function renderChipList(items, emptyText) {
  if (!items.length) {
    return `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
  }
  return `<div class="summary-chip-list">${items.map((item) => `<span class="summary-chip">${escapeHtml(item)}</span>`).join('')}</div>`;
}

function rerenderSettingsOverlay() {
  const overlay = document.getElementById('settingsOverlay');
  if (!overlay?.classList.contains('active')) return;
  const content = document.getElementById('settingsContent');
  if (!content) return;
  content.innerHTML = renderSettingsHTML();
  applySettingsUI();
}

async function fetchJson(url, fallback = undefined) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      if (fallback !== undefined) return fallback;
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    if (fallback !== undefined) return fallback;
    showToast(`请求失败：${error.message}`);
    throw error;
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `${response.status} ${response.statusText}`);
  }
  return data;
}

async function init() {
  const spotlightInput = document.getElementById('spotlightInput');
  spotlightInput.addEventListener('input', (event) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearchSpotlight(event.target.value.trim()), 200);
  });
  spotlightInput.addEventListener('keydown', handleSpotlightKeydown);

  applySettings();
  await loadSidebar();
  await Promise.all([
    loadContext(),
    loadScreenContextSettings(),
    refreshCorrectionsFeed(),
    refreshPipelineJobs(),
  ]);
  renderHomePage();

  setInterval(refreshPipelineJobs, 5000);
}

async function loadScreenContextSettings() {
  state.screenSettings = await fetchJson('/api/settings/screen-context', {
    enabled: true,
    participation_mode: 'summary_only',
    exclude_apps: [],
    exclude_domains: [],
    exclude_window_keywords: [],
  });
  rerenderSettingsOverlay();
}

async function loadSidebar() {
  const [dates, stats] = await Promise.all([
    fetchJson('/api/dates', []),
    fetchJson('/api/stats', { total_dates: 0, total_segments: 0, total_words: 0, role_distribution: {} }),
  ]);

  state.allDates = dates || [];
  state.stats = stats || {};
  renderSidebar();
}

function renderSidebar() {
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
  if (!state.allDates.length) {
    dateList.innerHTML = renderEmptyState('暂无可用阅读数据');
    return;
  }

  dateList.innerHTML = state.allDates.map((item) => `
    <button class="date-item ${state.route === 'date' && item.date === state.currentDate ? 'active' : ''}" type="button" onclick="loadDate('${escapeHtml(item.date)}')">
      <span>${escapeHtml(item.date)}</span>
      <span class="meta">${item.segments}条</span>
    </button>
  `).join('');
}

function renderHomePage() {
  closeSidebar();
  setRoute('home');
  state.currentDate = '';
  const main = document.getElementById('main');
  if (!state.allDates.length) {
    main.innerHTML = `
      <div class="home-page">
        <h1>OpenMy</h1>
        <div class="home-meta">还没有可读数据。先跑一次 quick-start（快速开始）把录音喂进来。</div>
      </div>
    `;
    return;
  }

  const weekDates = latestWeekDates();
  const latest = latestDateInfo();
  const activeProjects = (state.context.active_projects || []).map((item) => item.title || item.project_id).filter(Boolean);
  const projectItems = activeProjects.slice(0, 3).map((name) => `${name}(${countKeywordDays(name, weekDates)}d)`);
  const decisionItems = (state.context.recent_decisions || []).slice(0, 3).map((item) => plainText(item.decision || item.summary || ''));
  const loopItems = (state.context.open_loops || []).slice(0, 3).map((item) => plainText(item.title || item.loop_id || ''));

  main.innerHTML = `
    <div class="home-page">
      <h1>OpenMy</h1>
      <div class="home-meta">本周 ${formatRangeLabel(weekDates[weekDates.length - 1]?.date || latest.date, weekDates[0]?.date || latest.date)} · ${weekDates.length}天 · ${weekDates.reduce((sum, item) => sum + (item.segments || 0), 0)}条记录</div>

      <div class="home-block">
        <div class="section-kicker">待办</div>
        ${renderChipList(loopItems, '当前没有待办')}
      </div>
      <div class="home-block">
        <div class="section-kicker">项目</div>
        ${renderChipList(projectItems, '当前没有项目')}
      </div>
      <div class="home-block">
        <div class="section-kicker">决策</div>
        ${renderChipList(decisionItems, '当前没有决策')}
      </div>
      <div class="home-block">
        <div class="section-kicker">每日记录</div>
        <div class="daily-link-list">
          ${weekDates.map((item) => `
            <button class="daily-link-item" type="button" onclick="loadDate('${escapeHtml(item.date)}')">
              <span class="daily-link-date">${escapeHtml(formatShortDate(item.date))}</span>
              <span class="daily-link-summary">${escapeHtml(truncateSummary(item.summary || item.timeline?.[0]?.preview || ''))}</span>
              <span class="daily-link-count">${item.segments || 0}条</span>
            </button>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

function renderReportPage(title, dates, extraMeta = '') {
  const main = document.getElementById('main');
  if (!dates.length) {
    main.innerHTML = `<div class="report-page"><h1>${escapeHtml(title)}</h1><div class="report-meta">当前没有可汇总的数据。</div></div>`;
    return;
  }

  const activeProjects = (state.context.active_projects || []).map((item) => item.title || item.project_id).filter(Boolean);
  const projectItems = activeProjects.slice(0, 4).map((name) => `${name}(${countKeywordDays(name, dates)}d)`);
  const decisionItems = uniqueTextItems(
    dates.flatMap((item) => (item.decisions || []).map((decision) => decision.decision || decision.what || '')),
    4,
  );
  const loopItems = uniqueTextItems(
    dates.flatMap((item) => (item.todos || []).map((todo) => todo.task || todo.what || '')),
    4,
  );
  const summaryText = uniqueTextItems(dates.map((item) => item.summary || ''), 3).join(' ');

  main.innerHTML = `
    <div class="report-page">
      <h1>${escapeHtml(title)}</h1>
      <div class="report-meta">${escapeHtml(extraMeta)}</div>
      ${summaryText ? `<section class="summary-callout"><p>${escapeHtml(summaryText)}</p></section>` : ''}

      <div class="report-block">
        <div class="section-kicker">项目</div>
        ${renderChipList(projectItems, '当前没有项目')}
      </div>
      <div class="report-block">
        <div class="section-kicker">决策</div>
        ${renderChipList(decisionItems, '当前没有决策')}
      </div>
      <div class="report-block">
        <div class="section-kicker">待跟进</div>
        ${renderChipList(loopItems, '当前没有待跟进')}
      </div>
      <div class="report-block">
        <div class="section-kicker">每日概要</div>
        <div class="daily-link-list">
          ${dates.map((item) => `
            <button class="daily-link-item" type="button" onclick="loadDate('${escapeHtml(item.date)}')">
              <span class="daily-link-date">${escapeHtml(formatShortDate(item.date))}</span>
              <span class="daily-link-summary">${escapeHtml(truncateSummary(item.summary || item.timeline?.[0]?.preview || ''))}</span>
              <span class="daily-link-count">${item.segments || 0}条</span>
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
    renderReportPage('周报', [], '');
    return;
  }
  const totalSegments = dates.reduce((sum, item) => sum + (item.segments || 0), 0);
  renderReportPage(
    `周报 ${formatRangeLabel(dates[dates.length - 1].date, dates[0].date)}`,
    dates,
    `${dates.length}天 · ${totalSegments}条记录`,
  );
}

function renderMonthlyReport() {
  closeSidebar();
  setRoute('monthly');
  state.currentDate = '';
  const dates = latestMonthDates();
  if (!dates.length) {
    renderReportPage('月报', [], '');
    return;
  }
  const totalSegments = dates.reduce((sum, item) => sum + (item.segments || 0), 0);
  renderReportPage(
    `月报 ${dates[0].date.slice(0, 7)}`,
    dates,
    `本月 ${dates.length}天有记录 · ${totalSegments}条记录`,
  );
}

async function loadContext() {
  const [context, loops, projects, decisions] = await Promise.all([
    fetchJson('/api/context', {}),
    fetchJson('/api/context/loops', []),
    fetchJson('/api/context/projects', []),
    fetchJson('/api/context/decisions', []),
  ]);

  state.context = context || {};
  state.loops = loops || [];
  state.projects = projects || [];
  state.decisions = decisions || [];

  rerenderSettingsOverlay();
  if (state.route === 'home') {
    renderHomePage();
  } else if (state.route === 'weekly') {
    renderWeeklyReport();
  } else if (state.route === 'monthly') {
    renderMonthlyReport();
  }
}

async function runContextQuery(kind = '', query = '') {
  const kindEl = document.getElementById('contextQueryKind');
  const inputEl = document.getElementById('contextQueryInput');
  const finalKind = kind || kindEl?.value || state.contextQuery.kind || 'project';
  const finalQuery = query !== '' ? query : (inputEl?.value || '').trim();

  state.contextQuery.kind = finalKind;
  state.contextQuery.query = finalQuery;
  state.contextQuery.loading = true;
  rerenderSettingsOverlay();

  const params = new URLSearchParams({
    kind: finalKind,
    limit: '8',
    evidence: '1',
  });
  if (finalQuery) {
    params.set('q', finalQuery);
  }

  try {
    state.contextQuery.result = await fetchJson(`/api/context/query?${params.toString()}`, {
      summary: '查询失败',
      current_hits: [],
      history_hits: [],
      daily_rollups: [],
      temporal_buckets: { current: [], future: [], past: [], closed: [] },
      conflicts: [],
      evidence: [],
    });
  } finally {
    state.contextQuery.loading = false;
    rerenderSettingsOverlay();
  }
}

async function jumpToEvidence(date, timeRange = '', query = '') {
  const time = String(timeRange || '').split('-', 1)[0] || '';
  if (!date) {
    return;
  }
  await loadDate(date, time, query);
}

async function loadDate(date, focusTime = '', focusQuery = '') {
  closeSidebar();
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

function renderDayLayout() {
  const detail = state.currentData;
  const meta = state.currentMeta || {};
  if (!detail) return;

  const summaryText = plainText(state.currentBriefing?.summary || meta.daily_summary || state.context.status_line || '');
  const headerMeta = [
    detail.date,
    `${detail.segments.length}条记录`,
    `${fmtNum(detail.word_count || 0)}字`,
  ];

  document.getElementById('main').innerHTML = `
    <article class="daily-article">
      <header class="page-header">
        <div class="page-title">${escapeHtml(detail.date)}</div>
        <div class="page-meta">${headerMeta.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}</div>
      </header>
      ${summaryText ? `<section class="summary-callout"><p>${escapeHtml(summaryText)}</p></section>` : ''}
      ${renderMetaPanels(meta)}
      <section class="article-section">
        <h2>详细记录</h2>
        <div class="record-list">
          ${detail.segments.map((segment) => `
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

function renderMetaPanels(meta) {
  const groups = [
    { key: 'events', title: '发生了什么', dot: '#2eaadc' },
    { key: 'intents', title: '打算做什么', dot: '#0f7b6c' },
    { key: 'facts', title: '记住了什么', dot: '#64748b' },
    { key: 'decisions', title: '决定了什么', dot: '#d9730d' },
  ];

  const cards = groups.map((group) => {
    const items = meta?.[group.key] || [];
    return `<section class="meta-section" style="--section-color:${group.dot}">
      <div class="prop-card">
      <div class="prop-card-title"><span class="dot" style="background:${group.dot}"></span>${group.title} <span class="prop-count">${items.length}</span></div>
      ${items.length ? items.map((item) => {
        const time = escapeHtml(item.time || '');
        const project = escapeHtml(item.project || item.topic || '');
        const summary = escapeHtml(plainText(item.summary || item.what || item.task || item.content || item.decision || item.fact || item.intent || ''));
        return `<div class="prop-item">
          ${time ? `<span class="time-tag">${time}</span>` : ''}
          ${project ? `<span class="project-tag">${project}</span>` : ''}
          ${summary}
        </div>`;
      }).join('') : '<div class="empty-state">暂无</div>'}
      </div>
    </section>`;
  }).filter(Boolean);

  return cards.length ? `<div class="props-grid">${cards.join('')}</div>` : '';
}

function getSegmentDistillation(segment, meta) {
  const highlights = [];
  (meta.events || []).filter((item) => item.time === segment.time).forEach((item) => {
    highlights.push(`<strong>${escapeHtml(item.project || '事件')}</strong> ${escapeHtml(plainText(item.summary || item.what || ''))}`);
  });
  (meta.decisions || []).filter((item) => item.time === segment.time).forEach((item) => {
    highlights.push(`<strong>${escapeHtml(item.project || '决策')}</strong> ${escapeHtml(plainText(item.what || item.decision || ''))}`);
  });
  (meta.todos || []).filter((item) => item.time === segment.time).forEach((item) => {
    highlights.push(`<strong>${escapeHtml(item.project || '待办')}</strong> ${escapeHtml(plainText(item.task || ''))}`);
  });
  const preview = escapeHtml(plainText(segment.summary || segment.preview || segment.text || ''));
  if (highlights.length > 0) {
    return `${preview ? `<div>${preview}</div>` : ''}<div class="muted" style="margin-top:8px;font-size:14px;line-height:1.7">${highlights.join('<br>')}</div>`;
  }
  if (segment.summary) return escapeHtml(plainText(segment.summary));
  return escapeHtml(plainText(segment.preview || ''));
}

function initCharts() {
  if (!state.currentData) return;
  state.chartInstances.forEach((chart) => chart.destroy());
  state.chartInstances = [];



  const timeCounts = {};
  state.currentData.segments.forEach((segment) => {
    const hour = `${String(segment.time).split(':')[0]}:00`;
    timeCounts[hour] = (timeCounts[hour] || 0) + plainText(segment.text || '').length;
  });

  const timeCanvas = document.getElementById('chartTime');
  if (timeCanvas) {
    const sortedHours = Object.keys(timeCounts).sort();
    state.chartInstances.push(new Chart(timeCanvas, {
      type: 'bar',
      data: {
        labels: sortedHours,
        datasets: [{
          label: '字数',
          data: sortedHours.map((hour) => timeCounts[hour]),
          backgroundColor: '#2eaadc',
          borderRadius: 4,
        }],
      },
      options: { plugins: { legend: { display: false } }, maintainAspectRatio: false },
    }));
  }
}

function optionMarkup(items, getter) {
  if (!items || !items.length) {
    return '<option value="">暂无可选项</option>';
  }
  return items.map((item) => {
    const value = getter(item);
    return `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`;
  }).join('');
}

function toggleRawText(button) {
  const rawNode = button.parentElement.nextElementSibling;
  const visible = !rawNode.classList.contains('visible');
  rawNode.classList.toggle('visible', visible);
  button.innerHTML = visible ? '隐藏原文' : '显示原文';
  button.style.color = visible ? '#fff' : 'var(--text-secondary)';
  button.style.background = visible ? 'var(--text)' : 'var(--bg-sidebar)';
}

function scrollToSegment(time, query = '') {
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

async function refreshCorrectionsFeed() {
  const payload = await fetchJson('/api/corrections', { corrections: [] });
  state.corrections = payload.corrections || [];
  renderSidebarDict();
  rerenderSettingsOverlay();
}

async function submitTypoCorrection() {
  const wrong = document.getElementById('typoWrong')?.value.trim() || '';
  const right = document.getElementById('typoRight')?.value.trim() || '';
  const context = document.getElementById('typoContext')?.value.trim() || '';
  if (!wrong || !right) {
    showToast('原文和改成内容都不能为空');
    return;
  }
  try {
    await postJson('/api/correct/typo', {
      wrong,
      right,
      context,
      date: state.currentDate,
      sync_vocab: true,
    });
    showToast(`已保存校正：${wrong} → ${right}`);
    await refreshCorrectionsFeed();
    if (state.currentDate) {
      await loadDate(state.currentDate);
    }
  } catch (error) {
    showToast(error.message);
  }
}

function toggleAccordion(titleEl) {
  const body = titleEl.nextElementSibling;
  if (!body) return;
  const isHidden = body.style.display === 'none';
  body.style.display = isHidden ? 'block' : 'none';
  const arrow = titleEl.querySelector('span');
  if (arrow) arrow.textContent = isHidden ? '▲ 收起' : '▼ 展开';
}

async function submitContextAction(url, payload, successMessage) {
  try {
    await postJson(url, payload);
    showToast(successMessage);
    await loadContext();
    rerenderSettingsOverlay();
  } catch (error) {
    showToast(error.message);
  }
}

function splitSettingList(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

async function updateScreenContextMode(mode) {
  try {
    state.screenSettings = await postJson('/api/settings/screen-context', {
      enabled: mode !== 'off',
      participation_mode: mode,
    });
    showToast(`屏幕上下文已切换为：${mode === 'off' ? '关闭' : mode === 'full' ? '参与上下文' : '只保留摘要'}`);
    rerenderSettingsOverlay();
  } catch (error) {
    showToast(error.message);
  }
}

async function saveScreenContextExclusions() {
  try {
    state.screenSettings = await postJson('/api/settings/screen-context', {
      exclude_apps: splitSettingList(document.getElementById('screenExcludeApps')?.value),
      exclude_domains: splitSettingList(document.getElementById('screenExcludeDomains')?.value),
      exclude_window_keywords: splitSettingList(document.getElementById('screenExcludeWindows')?.value),
    });
    showToast('屏幕上下文规则已保存');
    rerenderSettingsOverlay();
  } catch (error) {
    showToast(error.message);
  }
}

function toggleSidebar() {
  document.querySelector('.app')?.classList.toggle('sidebar-open');
}

function closeSidebar() {
  document.querySelector('.app')?.classList.remove('sidebar-open');
}

function highlightQuerySnippet(text, query) {
  const safe = escapeHtml(plainText(text || ''));
  if (!query) return safe;
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return safe.replace(new RegExp(`(${escapedQuery})`, 'gi'), '<mark class="search-highlight">$1</mark>');
}

function recentSpotlightResults() {
  return state.allDates.slice(0, 5).map((item) => ({
    date: item.date,
    time: item.timeline?.[0]?.time || '',
    context: truncateSummary(item.summary || item.timeline?.[0]?.preview || ''),
  }));
}

function renderSpotlightResults(items, query = '') {
  const container = document.getElementById('spotlightResults');
  if (!items.length) {
    container.innerHTML = '<div class="spotlight-empty">找不到相关的上下文</div>';
    return;
  }

  const grouped = items.reduce((acc, item) => {
    acc[item.date] = acc[item.date] || [];
    acc[item.date].push(item);
    return acc;
  }, {});
  let index = 0;
  container.innerHTML = Object.entries(grouped).map(([date, entries]) => `
    <div class="spotlight-group-label">${escapeHtml(date)}</div>
    ${entries.map((item) => {
      const itemIndex = index++;
      return `
        <button class="spotlight-result-item ${itemIndex === state.spotlightIndex ? 'active' : ''}" data-spotlight-index="${itemIndex}" onclick="jumpToSearchResult('${escapeHtml(item.date)}', '${escapeHtml(item.time || '')}', '${escapeHtml(query)}')">
          <strong style="display:block;margin-bottom:4px;color:var(--text);font-size:13px">${escapeHtml(item.date)}${item.time ? ` · ${escapeHtml(item.time)}` : ''}</strong>
          <div class="muted" style="font-size:12px;line-height:1.5">${highlightQuerySnippet(item.context || item.raw_context || '', query)}</div>
        </button>
      `;
    }).join('')}
  `).join('');
}

function setSpotlightSelection(nextIndex) {
  state.spotlightIndex = nextIndex;
  document.querySelectorAll('.spotlight-result-item').forEach((node) => {
    node.classList.toggle('active', Number(node.dataset.spotlightIndex) === state.spotlightIndex);
  });
}

function handleSpotlightKeydown(event) {
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

function openSpotlight() {
  const overlay = document.getElementById('spotlightOverlay');
  const input = document.getElementById('spotlightInput');
  overlay.classList.add('active');
  input.value = '';
  input.focus();
  runSearchSpotlight('');
}

function closeSpotlight(e) {
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

async function runSearchSpotlight(query) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    state.searchResults = recentSpotlightResults();
    state.spotlightIndex = state.searchResults.length ? 0 : -1;
    renderSpotlightResults(state.searchResults, '');
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

async function jumpToSearchResult(date, time, query = '') {
  closeSpotlight();
  if (state.currentDate !== date) {
    await loadDate(date, time, query);
  } else {
    requestAnimationFrame(() => scrollToSegment(time, query));
  }
}

async function createPipelineJob(kind) {
  const explicitDate = document.getElementById('pipelineDateInput')?.value.trim() || '';
  const payload = { kind };
  if (kind !== 'context') {
    payload.target_date = explicitDate || state.currentDate || '';
  }

  try {
    const job = await postJson('/api/pipeline/jobs', payload);
    state.selectedJobId = job.job_id;
    showToast(`已开始：${formatPipelineKind(kind)}`);
    await refreshPipelineJobs();
  } catch (error) {
    showToast(error.message);
  }
}

async function refreshPipelineJobs() {
  state.jobs = await fetchJson('/api/pipeline/jobs', []);
  if (state.selectedJobId && !state.jobs.find((job) => job.job_id === state.selectedJobId)) {
    state.selectedJobId = '';
    state.selectedJobDetail = null;
  }
  if (!state.selectedJobId && state.jobs.length) {
    state.selectedJobId = state.jobs[0].job_id;
  }
  if (state.selectedJobId) {
    await loadPipelineJobDetail(state.selectedJobId, false);
  }
  
  // Pipeline UI Live Updates
  const settingsList = document.getElementById('pipelineJobsList');
  if (settingsList) {
    settingsList.innerHTML = renderEventList(state.jobs, (job) => `<button class="job-item ${job.job_id===state.selectedJobId?'active':''}" type="button" onclick="loadPipelineJobDetail('${escapeHtml(job.job_id)}')">
      <strong>${escapeHtml(formatPipelineKind(job.kind))}</strong>
      <div class="muted">${escapeHtml(job.target_date||'全局')} · ${escapeHtml(formatPipelineStatus(job.status))}</div>
    </button>`, '还没有运行记录。');
  }
  const detailNode = document.getElementById('pipelineJobDetail');
  if (detailNode) {
    detailNode.innerHTML = renderPipelineJobDetail();
  }

  // Global Indicator Logic
  const activeJobs = state.jobs.filter(j => j.status === 'pending' || j.status === 'running');
  const indicator = document.getElementById('globalJobIndicator');
  if (indicator) {
    if (activeJobs.length > 0) {
      document.getElementById('globalJobText').textContent = `正在后台执行 ${activeJobs.length} 个分析任务...`;
      indicator.style.display = 'flex';
    } else {
      indicator.style.display = 'none';
    }
  }
}

async function loadPipelineJobDetail(jobId, rerender = true) {
  const detail = await fetchJson(`/api/pipeline/jobs/${jobId}`, null);
  if (!detail) return;
  state.selectedJobId = jobId;
  state.selectedJobDetail = detail;

  if (detail.status === 'succeeded' && !state.handledCompletedJobs.has(detail.job_id)) {
    state.handledCompletedJobs.add(detail.job_id);
    await handleJobCompletion(detail);
  }

  if (rerender) rerenderSettingsOverlay();
  const detailNode = document.getElementById('pipelineJobDetail');
  if (detailNode) {
    detailNode.innerHTML = renderPipelineJobDetail();
  }
}

async function handleJobCompletion(job) {
  if (job.kind === 'context') {
    await loadContext();
    showToast('上下文已刷新');
    return;
  }
  if (job.target_date && job.target_date === state.currentDate) {
    await loadDate(state.currentDate);
    showToast(`${formatPipelineKind(job.kind)}已完成，并已刷新当前日期`);
  }
}

// === Settings Page ===
function openSettings() {
  const overlay = document.getElementById('settingsOverlay');
  const content = document.getElementById('settingsContent');
  document.getElementById('settingsBtn')?.classList.add('active');
  content.innerHTML = renderSettingsHTML();
  overlay.classList.add('active');
  applySettingsUI();
}

function closeSettingsOverlay(e) {
  if (e) e.stopPropagation();
  const overlay = document.getElementById('settingsOverlay');
  overlay.classList.remove('active');
  document.getElementById('settingsBtn')?.classList.remove('active');
}

function renderSettingsHTML() {
  return `
  <div class="settings-page" style="padding:0">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
      <h2 style="margin:0;font-size:20px;">设置</h2>
      <button class="cp-close" onclick="closeSettingsOverlay()" style="background:none;border:none;font-size:14px;color:var(--text-secondary);cursor:pointer;line-height:1">关闭</button>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">外观模式</div>
      <div class="settings-row">
        <div><label>主题</label><div class="desc">切换浅色和深色外观</div></div>
        <div class="setting-options" id="themeOptions">
          <button class="setting-opt" data-val="light" onclick="saveSetting('theme','light')">浅色</button>
          <button class="setting-opt" data-val="dark" onclick="saveSetting('theme','dark')">深色</button>
          <button class="setting-opt" data-val="auto" onclick="saveSetting('theme','auto')">跟随系统</button>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">字号</div>
      <div class="settings-row">
        <div><label>正文字号</label><div class="desc">调整全局文字大小</div></div>
        <div class="setting-options" id="fontSizeOptions">
          <button class="setting-opt" data-val="small" onclick="saveSetting('font-size','small')">小</button>
          <button class="setting-opt" data-val="medium" onclick="saveSetting('font-size','medium')">中</button>
          <button class="setting-opt" data-val="large" onclick="saveSetting('font-size','large')">大</button>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">主题色</div>
      <div class="settings-row">
        <div><label>强调色</label><div class="desc">按钮和链接的颜色</div></div>
        <div class="setting-options" id="accentOptions" style="gap:10px">
          <button class="color-swatch" data-val="blue" style="background:#3b82f6" onclick="saveSetting('accent','blue')" title="蓝色"></button>
          <button class="color-swatch" data-val="purple" style="background:#8b5cf6" onclick="saveSetting('accent','purple')" title="紫色"></button>
          <button class="color-swatch" data-val="green" style="background:#059669" onclick="saveSetting('accent','green')" title="绿色"></button>
          <button class="color-swatch" data-val="amber" style="background:#d97706" onclick="saveSetting('accent','amber')" title="琥珀"></button>
          <button class="color-swatch" data-val="pink" style="background:#ec4899" onclick="saveSetting('accent','pink')" title="粉色"></button>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">语言</div>
      <div class="settings-row">
        <div><label>界面语言</label><div class="desc">更多语言即将支持</div></div>
        <div class="setting-options" id="langOptions">
          <button class="setting-opt active" data-val="zh">中文</button>
          <button class="setting-opt" data-val="en" disabled style="opacity:0.4;cursor:not-allowed">English (soon)</button>
        </div>
      </div>
    </div>

    <details class="settings-section">
      <summary class="settings-section-title" style="cursor:pointer">Agent Query 工作台</summary>
      <div class="form-stack" style="margin-top:16px">
        <div class="settings-query-grid">
          <select id="contextQueryKind" class="field-select">
            <option value="project" ${(state.contextQuery.kind || 'project') === 'project' ? 'selected' : ''}>项目</option>
            <option value="person" ${state.contextQuery.kind === 'person' ? 'selected' : ''}>人物</option>
            <option value="open" ${state.contextQuery.kind === 'open' ? 'selected' : ''}>未关闭待办</option>
            <option value="closed" ${state.contextQuery.kind === 'closed' ? 'selected' : ''}>已关闭事项</option>
            <option value="evidence" ${state.contextQuery.kind === 'evidence' ? 'selected' : ''}>证据</option>
          </select>
          <input id="contextQueryInput" class="field-input" type="text" value="${escapeHtml(state.contextQuery.query || '')}" placeholder="查项目、人物、待办或证据" onkeydown="if(event.key==='Enter') runContextQuery()">
          <button class="action-btn primary" type="button" onclick="runContextQuery()">查询</button>
        </div>
        ${renderContextQueryResult()}
      </div>
    </details>

    <div class="settings-section">
      <div class="settings-section-title">记忆库修整：纠正 AI 归档错误</div>
      <div class="settings-memory-grid">
        <div>
          <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:8px">待办事项</div>
          <select id="closeLoopSelect" class="field-select" style="margin-bottom:8px">${optionMarkup(state.loops, (item) => item.title || item.loop_id)}</select>
          <div class="inline-actions">
            <button class="action-btn" type="button" onclick="submitContextAction('/api/context/loops/close', { query: document.getElementById('closeLoopSelect').value, status: 'done' }, '已标记完成')">标记完成</button>
            <button class="action-btn" type="button" onclick="submitContextAction('/api/context/loops/reject', { query: document.getElementById('closeLoopSelect').value }, '已彻底移除')">强制移除</button>
          </div>
        </div>
        <div>
          <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:8px">项目管理</div>
          <select id="mergeProjectSource" class="field-select" style="margin-bottom:4px">${optionMarkup(state.projects, (item) => item.title || item.project_id)}</select>
          <select id="mergeProjectTarget" class="field-select" style="margin-bottom:8px">${optionMarkup(state.projects, (item) => item.title || item.project_id)}</select>
          <div class="inline-actions">
            <button class="action-btn" type="button" onclick="submitContextAction('/api/context/projects/merge', { source: document.getElementById('mergeProjectSource').value, target: document.getElementById('mergeProjectTarget').value }, '已合并项目')">合并除重</button>
            <button class="action-btn" type="button" onclick="submitContextAction('/api/context/projects/reject', { query: document.getElementById('mergeProjectSource').value }, '已设为无关项目')">强制移除</button>
          </div>
        </div>
        <div>
          <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:8px">决策树管理</div>
          <select id="rejectDecisionSelect" class="field-select" style="margin-bottom:8px">${optionMarkup(state.decisions, (item) => item.decision || item.topic || item.decision_id)}</select>
          <div class="inline-actions">
            <button class="action-btn" type="button" onclick="submitContextAction('/api/context/decisions/reject', { query: document.getElementById('rejectDecisionSelect').value }, '已移出该决策')">强制移除</button>
          </div>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">数据重制与分析引擎</div>
      <div class="form-stack">
        <div class="pipeline-stepbar">
          <span>清理</span>
          <span>识别</span>
          <span>摘要</span>
          <span>日报</span>
          <span>重跑</span>
        </div>
        <div>
          <label class="form-label" for="pipelineDateInput">指定处理日期</label>
          <input id="pipelineDateInput" class="field-input" type="text" value="${escapeHtml(state.currentDate || '')}" placeholder="格式: YYYY-MM-DD（留空则为当前日）">
          <div class="desc" style="margin-top:6px;">如果当天的数据分析出现异常或中断，可手动强制系统重新分析：</div>
        </div>
        <div class="inline-actions" style="flex-wrap:wrap">
          <button class="action-btn" type="button" onclick="if(confirm('确认重新「清理杂音文本」吗？该操作将重置并覆盖现有时间线状态。')) createPipelineJob('clean')">清理杂音文本</button>
          <button class="action-btn" type="button" onclick="if(confirm('确认重新「识别对话角色」吗？')) createPipelineJob('roles')">识别对话角色</button>
          <button class="action-btn" type="button" onclick="if(confirm('确认重新「提取时间线摘要」吗？')) createPipelineJob('distill')">提取时间线摘要</button>
          <button class="action-btn" type="button" onclick="if(confirm('确认重新「生成今日概览」吗？')) createPipelineJob('briefing')">生成今日概览</button>
          <button class="action-btn primary" type="button" onclick="if(confirm('危险操作：系统将清空今日数据并从头开始完整分析一次，确认执行吗？')) createPipelineJob('run')" style="background:var(--warning);color:#000;border-color:var(--warning)">一键重新分析全天</button>
          <span style="width:12px;"></span>
          <button class="action-btn primary" type="button" onclick="if(confirm('确认刷新「全局系统缓存」吗？系统将用最新整理的项目和待办状态重建缓存。')) createPipelineJob('context')">刷新全局系统缓存</button>
        </div>
      </div>
      <div style="margin-top:16px">
        <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:8px">最近运行 <button class="action-btn" type="button" onclick="refreshPipelineJobs()" style="margin-left:8px">刷新</button></div>
        <div id="pipelineJobsList" class="search-stack">${renderEventList(state.jobs, (job) => `<button class="job-item ${job.job_id===state.selectedJobId?'active':''}" type="button" onclick="loadPipelineJobDetail('${escapeHtml(job.job_id)}')">
          <strong>${escapeHtml(formatPipelineKind(job.kind))}</strong>
          <div class="muted">${escapeHtml(job.target_date||'全局')} · ${escapeHtml(formatPipelineStatus(job.status))}</div>
        </button>`, '还没有运行记录。')}</div>
        <div id="pipelineJobDetail" style="margin-top:12px">${renderPipelineJobDetail()}</div>
      </div>
    </div>
  </div>`;
}

function applySettings() {
  const theme = localStorage.getItem('openmy-theme') || 'light';
  const fontSize = localStorage.getItem('openmy-font-size') || 'medium';
  const accent = localStorage.getItem('openmy-accent') || 'blue';
  const html = document.documentElement;
  if (theme === 'auto') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    html.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    html.setAttribute('data-theme', theme);
  }
  if (fontSize !== 'medium') { html.setAttribute('data-font-size', fontSize); } else { html.removeAttribute('data-font-size'); }
  if (accent !== 'blue') { html.setAttribute('data-accent', accent); } else { html.removeAttribute('data-accent'); }
}

function saveSetting(key, value) {
  localStorage.setItem('openmy-' + key, value);
  applySettings();
  applySettingsUI();
}

function applySettingsUI() {
  const theme = localStorage.getItem('openmy-theme') || 'light';
  const fontSize = localStorage.getItem('openmy-font-size') || 'medium';
  const accent = localStorage.getItem('openmy-accent') || 'blue';
  document.querySelectorAll('#themeOptions .setting-opt').forEach(b => b.classList.toggle('active', b.dataset.val === theme));
  document.querySelectorAll('#fontSizeOptions .setting-opt').forEach(b => b.classList.toggle('active', b.dataset.val === fontSize));
  document.querySelectorAll('#accentOptions .color-swatch').forEach(b => b.classList.toggle('active', b.dataset.val === accent));
}

// Listen for system theme changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (localStorage.getItem('openmy-theme') === 'auto') applySettings();
});

// === Sidebar Dictionary ===
function renderSidebarDict() {
  const countEl = document.getElementById('dictCount');
  const listEl = document.getElementById('sidebarDictList');
  if (!countEl || !listEl) return;
  const items = state.corrections || [];
  countEl.textContent = items.length;
  if (!items.length) {
    listEl.innerHTML = '<div style="padding:8px 0;font-size:11px;color:var(--text-light)">还没有校正记录</div>';
    return;
  }
  listEl.innerHTML = items.map(item => `
    <div class="sidebar-dict-item">
      <span class="dict-wrong">${escapeHtml(item.wrong)}</span>
      <span class="dict-arrow-icon">→</span>
      <span class="dict-right">${escapeHtml(item.right)}</span>
    </div>
  `).join('');
}

function toggleSidebarDict() {
  const btn = document.querySelector('.sidebar-dict-toggle');
  const list = document.getElementById('sidebarDictList');
  btn.classList.toggle('open');
  list.classList.toggle('open');
}

// === Inline Correction Popover ===
document.addEventListener('mouseup', (e) => {
  const selection = window.getSelection();
  const selectedText = selection?.toString().trim();
  if (!selectedText || selectedText.length < 2 || selectedText.length > 50) return;
  const targetEl = e.target;
  if (targetEl.closest('input, textarea, button, select, .correction-popover, .spotlight-modal')) return;
  if (!targetEl.closest('.seg-raw, .seg-distilled, .record-card, .briefing-card, .spotlight-result-item, .event-item, .prop-item, .time-block')) return;
  openCorrectionPopover(selectedText, e.clientX, e.clientY);
});

function openCorrectionPopover(wrongText, mouseX, mouseY) {
  const popover = document.getElementById('correctionPopover');
  const wrongEl = document.getElementById('cpWrongText');
  const rightInput = document.getElementById('cpRightInput');
  wrongEl.textContent = wrongText;
  rightInput.value = '';
  popover.style.display = 'block';
  const rect = popover.getBoundingClientRect();
  let top = mouseY + 12;
  let left = mouseX - 24;
  if (top + rect.height > window.innerHeight) top = mouseY - rect.height - 12;
  if (left + rect.width > window.innerWidth) left = window.innerWidth - rect.width - 16;
  if (left < 8) left = 8;
  popover.style.top = top + 'px';
  popover.style.left = left + 'px';
  setTimeout(() => rightInput.focus(), 50);
}

function closeCorrectionPopover() {
  document.getElementById('correctionPopover').style.display = 'none';
}

async function submitInlineCorrection() {
  const wrong = document.getElementById('cpWrongText').textContent.trim();
  const right = document.getElementById('cpRightInput').value.trim();
  if (!right) { showToast('请输入正确的文本'); return; }
  if (wrong === right) { showToast('纠正前后相同'); return; }
  try {
    await postJson('/api/correct/typo', {
      wrong, right, context: '', date: state.currentDate, sync_vocab: true,
    });
    closeCorrectionPopover();
    showToast(`已纠正：${wrong} → ${right}`);
    await refreshCorrectionsFeed();
    if (state.currentDate) await loadDate(state.currentDate);
  } catch (err) { showToast(err.message); }
}

document.getElementById('cpRightInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); submitInlineCorrection(); }
  if (e.key === 'Escape') closeCorrectionPopover();
});

document.addEventListener('mousedown', (e) => {
  const popover = document.getElementById('correctionPopover');
  if (popover.style.display !== 'none' && !popover.contains(e.target)) {
    closeCorrectionPopover();
  }
});

init();
