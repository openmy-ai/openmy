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
  currentDate: '',
  currentData: null,
  currentMeta: null,
  currentBriefing: null,
  currentView: 'briefing',
  activeFilters: new Set(),
  context: {},
  loops: [],
  projects: [],
  decisions: [],
  corrections: [],
  searchResults: [],
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
        <span class="callout-icon">🧭</span>
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
  document.getElementById('spotlightInput').addEventListener('input', (event) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearchSpotlight(event.target.value.trim()), 200);
  });

  applySettings();
  await loadSidebar();
  await Promise.all([
    loadContext(),
    loadScreenContextSettings(),
    refreshCorrectionsFeed(),
    refreshPipelineJobs(),
  ]);

  if (state.currentData) {
    renderDayLayout();
  }

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
  if (document.getElementById('view-overview')) {
    renderOverviewView();
  }
}

async function loadSidebar() {
  const [dates, stats] = await Promise.all([
    fetchJson('/api/dates', []),
    fetchJson('/api/stats', { total_dates: 0, total_segments: 0, total_words: 0, role_distribution: {} }),
  ]);

  state.allDates = dates || [];
  state.stats = stats || {};
  renderSidebar();

  const defaultDate = state.allDates.find((item) => item.is_default)?.date || state.allDates[0]?.date || '';
  if (defaultDate) {
    await loadDate(defaultDate);
  } else {
    document.getElementById('main').innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;min-height:75vh;text-align:center;color:var(--text-secondary);padding:40px;">
        <div style="font-size:72px;margin-bottom:24px;filter:drop-shadow(0 10px 15px rgba(0,0,0,0.1));"></div>
        <h2 style="font-size:32px;color:var(--text);margin-bottom:16px;font-family:var(--font-body);font-weight:800;letter-spacing:-0.03em;">这是你的主场</h2>
        <p style="font-size:1.1rem;max-width:500px;line-height:1.6;margin-bottom:48px">上下文引擎已启动，但目前记忆库是空的。</p>
        <div style="background:var(--bg-hover);padding:32px;border-radius:16px;text-align:left;border:1px solid var(--border);max-width:600px;width:100%;box-shadow:var(--shadow-sm);">
          <div style="font-weight:700;color:var(--text);margin-bottom:16px;font-size:1.1rem;display:flex;align-items:center;gap:8px;">准备给 AI 喂点数据</div>
          <p style="font-size:1rem;margin-bottom:16px;line-height:1.6;">打开本机终端，使用你的某段开会录音或日常语音，运行以下命令：</p>
          <code style="display:block;background:var(--bg);color:var(--text);padding:16px 20px;border-radius:8px;font-family:monospace;font-size:14px;border:1px solid var(--border);">openmy quick-start path/to/your-audio.wav</code>
          <p style="font-size:0.95rem;margin-top:20px;opacity:0.8;display:flex;align-items:center;gap:6px;">处理大约需要几分钟。完成后，刷新本页面即可查看所有的上下文流。</p>
        </div>
      </div>
    `;
  }
}

function renderSidebar() {
  const stats = state.stats || {};
  document.getElementById('stats').innerHTML = `
    <span class="stat-item"><span class="stat-num">${stats.total_dates || 0}</span>天</span>
    <span class="stat-item"><span class="stat-num">${stats.total_segments || 0}</span>段</span>
    <span class="stat-item"><span class="stat-num">${fmtNum(stats.total_words || 0)}</span>字</span>
  `;

  const dateList = document.getElementById('dateList');
  if (!state.allDates.length) {
    dateList.innerHTML = renderEmptyState('暂无可用阅读数据');
    return;
  }

  dateList.innerHTML = state.allDates.map((item) => `
    <button class="date-item ${item.date === state.currentDate ? 'active' : ''}" type="button" onclick="loadDate('${escapeHtml(item.date)}')">
      <span class="icon">📄</span>
      ${escapeHtml(item.date)}
      <span class="meta">${item.segments}段</span>
    </button>
  `).join('');
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

  if (document.getElementById('view-overview')) {
    renderOverviewView();
  }
  if (document.getElementById('view-corrections')) {
    renderCorrectionsView();
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
  renderOverviewView();

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
    renderOverviewView();
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

  state.currentDate = date;
  state.currentData = detail;
  state.currentMeta = meta || detail.meta || {};
  state.currentBriefing = briefing || null;
  renderSidebar();
  renderDayLayout();

  if (focusTime) {
    switchView('timeline');
    requestAnimationFrame(() => scrollToSegment(focusTime, focusQuery));
  }
}

function renderDayLayout() {
  const detail = state.currentData;
  const meta = state.currentMeta || {};
  if (!detail) return;

  let html = '';
  html += `<div class="page-header">
    
    <div class="page-title">${escapeHtml(detail.date)}</div>
    <div class="page-meta">
      <span>${detail.segments.length} 条记录</span>
      <span>${fmtNum(detail.word_count || 0)} 字</span>
      <span>上下文 ${state.context.generated_at ? '已就绪' : '待生成'}</span>
    </div>
  </div>`;

  const calloutText = meta.daily_summary || state.context.status_line || '';
  if (calloutText) {
    html += `<div class="callout">
      
      <div class="callout-body">${escapeHtml(plainText(calloutText))}</div>
    </div>`;
  }

  html += renderMetaPanels(meta);

  html += `<div class="view-tabs">
    <button class="view-tab" id="tab-overview" onclick="switchView('overview')">概览 / 全局记忆库</button>
    <button class="view-tab" id="tab-briefing" onclick="switchView('briefing')">今日日报</button>
    <button class="view-tab" id="tab-timeline" onclick="switchView('timeline')">摘要时间线</button>
    <button class="view-tab" id="tab-table" onclick="switchView('table')">完整逐字稿</button>
    <button class="view-tab" id="tab-charts" onclick="switchView('charts')">数据图表</button>
  </div>`;

  html += '<div id="view-overview" class="view-content"></div>';
  html += '<div id="view-briefing" class="view-content"></div>';
  html += '<div id="view-timeline" class="view-content"></div>';
  html += '<div id="view-table" class="view-content"></div>';
  html += '<div id="view-charts" class="view-content"></div>';

  document.getElementById('main').innerHTML = html;
  document.getElementById('settingsBtn')?.classList.remove('active');
  renderOverviewView();
  renderBriefingView();
  renderTimelineView();
  renderTableView();
  renderChartsView();
  switchView(state.currentView);
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
    return `<div class="prop-card">
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
    </div>`;
  }).filter(Boolean);

  if (!cards.length) return '';
  return `<div class="props-grid">${cards.join('')}</div>`;
}

function renderOverviewView() {
  const node = document.getElementById('view-overview');
  if (!node) return;

  const context = state.context || {};
  const screenMode = state.screenSettings?.participation_mode || 'summary_only';
  const modeLabel = screenMode === 'off' ? '关闭' : screenMode === 'full' ? '参与上下文' : '只保留摘要';

  node.innerHTML = `
    <div class="briefing-banner" style="background:linear-gradient(135deg,#0f766e 0%,#1d4ed8 100%)">
      <h2>全局记忆库</h2>
      <div class="briefing-summary">${escapeHtml(plainText(context.status_line || '最近的上下文还在整理中。'))}</div>
      <div class="briefing-stats-row">
        <div class="briefing-stat"><span class="briefing-stat-num">${state.projects.length}</span><span class="briefing-stat-label">项目</span></div>
        <div class="briefing-stat"><span class="briefing-stat-num">${state.loops.length}</span><span class="briefing-stat-label">待跟进</span></div>
        <div class="briefing-stat"><span class="briefing-stat-num">${state.decisions.length}</span><span class="briefing-stat-label">决策</span></div>
        <div class="briefing-stat"><span class="briefing-stat-num">${(context.today_focus || []).length}</span><span class="briefing-stat-label">今日焦点</span></div>
      </div>
    </div>

    <div class="briefing-grid">
      <div class="briefing-card briefing-card-full">
        <div class="briefing-card-title" onclick="this.parentElement.classList.toggle('collapsed')" style="cursor:pointer">项目 · 跟进 · 决策 <span style="float:right;color:var(--text-light);font-size:12px">▼ 点击展开</span></div>
        <div class="collapsible-body" style="display:none">
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:8px">
            <div>
              <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">项目 (${state.projects.length})</div>
              ${state.projects.map(p => `<div class="event-item">${escapeHtml(p.title || p.project_id)}</div>`).join('') || '<div class="empty-state">暂无</div>'}
            </div>
            <div>
              <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">待跟进 (${state.loops.length})</div>
              ${state.loops.map(l => `<div class="event-item">${escapeHtml(l.title || l.loop_id)}</div>`).join('') || '<div class="empty-state">暂无</div>'}
            </div>
            <div>
              <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">决策 (${state.decisions.length})</div>
              ${state.decisions.slice(0, 5).map(d => `<div class="event-item">${escapeHtml(plainText(d.decision || d.topic || ''))}</div>`).join('') || '<div class="empty-state">暂无</div>'}
            </div>
          </div>
        </div>
      </div>
      <div class="briefing-card briefing-card-full">
        <div class="briefing-card-title">🔎 Agent Query 工作台</div>
        <div class="form-stack" style="margin-top:12px">
          <div style="display:grid;grid-template-columns:180px 1fr auto;gap:12px;align-items:center">
            <select id="contextQueryKind" class="field-select">
              <option value="project" ${(state.contextQuery.kind || 'project') === 'project' ? 'selected' : ''}>项目</option>
              <option value="person" ${state.contextQuery.kind === 'person' ? 'selected' : ''}>人物</option>
              <option value="open" ${state.contextQuery.kind === 'open' ? 'selected' : ''}>未关闭待办</option>
              <option value="closed" ${state.contextQuery.kind === 'closed' ? 'selected' : ''}>已关闭事项</option>
              <option value="evidence" ${state.contextQuery.kind === 'evidence' ? 'selected' : ''}>证据</option>
            </select>
            <input id="contextQueryInput" class="field-input" type="text" value="${escapeHtml(state.contextQuery.query || '')}" placeholder="查 OpenMy / 张总 / 某条待办 / 某个证据" onkeydown="if(event.key==='Enter') runContextQuery()">
            <button class="action-btn primary" type="button" onclick="runContextQuery()">查询</button>
          </div>
          ${renderContextQueryResult()}
        </div>
      </div>
      <div class="briefing-card briefing-card-full">
        <div class="briefing-card-title">屏幕上下文</div>
        <div class="event-item">当前模式：${escapeHtml(modeLabel)}。关闭后系统退回纯语音；摘要模式默认保守；参与模式会让屏幕证据进入日报、提取和上下文闭环。</div>
        <div class="inline-actions" style="margin-top:12px;flex-wrap:wrap">
          <button class="action-btn ${screenMode === 'off' ? 'primary' : ''}" type="button" onclick="updateScreenContextMode('off')">关闭</button>
          <button class="action-btn ${screenMode === 'summary_only' ? 'primary' : ''}" type="button" onclick="updateScreenContextMode('summary_only')">只保留摘要</button>
          <button class="action-btn ${screenMode === 'full' ? 'primary' : ''}" type="button" onclick="updateScreenContextMode('full')">参与上下文</button>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:16px">
          <div>
            <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">按应用排除</div>
            <input id="screenExcludeApps" class="field-input" type="text" value="${escapeHtml((state.screenSettings.exclude_apps || []).join(', '))}" placeholder="例如：微信, 支付宝">
          </div>
          <div>
            <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">按域名排除</div>
            <input id="screenExcludeDomains" class="field-input" type="text" value="${escapeHtml((state.screenSettings.exclude_domains || []).join(', '))}" placeholder="例如：taobao.com, bank.example.com">
          </div>
          <div>
            <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:6px">按窗口标题排除</div>
            <input id="screenExcludeWindows" class="field-input" type="text" value="${escapeHtml((state.screenSettings.exclude_window_keywords || []).join(', '))}" placeholder="例如：支付, 验证码, 钥匙串">
          </div>
        </div>
        <div class="inline-actions" style="margin-top:12px">
          <button class="action-btn primary" type="button" onclick="saveScreenContextExclusions()">保存屏幕上下文规则</button>
        </div>
        <div class="muted" style="margin-top:12px">会记录：时间、应用、窗口、域名、活动标签和过滤后的屏幕摘要。不会把密码、支付页、验证码、地址手机号等敏感内容直接送进主链。</div>
      </div>
    </div>
  `;

  // 展开/折叠逻辑
  node.querySelectorAll('.briefing-card-title[onclick]').forEach(title => {
    title.addEventListener('click', () => {
      const body = title.nextElementSibling;
      if (body) {
        const isHidden = body.style.display === 'none';
        body.style.display = isHidden ? 'block' : 'none';
        title.querySelector('span').textContent = isHidden ? '▲ 收起' : '▼ 点击展开';
      }
    });
  });
}

function getSegmentDistillation(segment, meta) {
  const highlights = [];
  (meta.events || []).filter((item) => item.time === segment.time).forEach((item) => {
    highlights.push(`<strong>${escapeHtml(item.project || '事件')}</strong> ${escapeHtml(plainText(item.summary || ''))}`);
  });
  (meta.decisions || []).filter((item) => item.time === segment.time).forEach((item) => {
    highlights.push(`<strong>${escapeHtml(item.project || '决策')}</strong> ${escapeHtml(plainText(item.what || item.decision || ''))}`);
  });
  (meta.todos || []).filter((item) => item.time === segment.time).forEach((item) => {
    highlights.push(`<strong>${escapeHtml(item.project || '待办')}</strong> ${escapeHtml(plainText(item.task || ''))}`);
  });
  if (highlights.length > 0) return highlights.join('<br>');
  if (segment.summary) return escapeHtml(plainText(segment.summary));
  return escapeHtml(plainText(segment.preview || ''));
}

function renderBriefingView() {
  const node = document.getElementById('view-briefing');
  if (!node) return;

  const briefing = state.currentBriefing;
  if (!briefing || briefing.error) {
    node.innerHTML = `<div class="briefing-banner" style="background:linear-gradient(135deg,#94a3b8,#64748b)">
      <h2>暂无日报</h2>
      <div class="briefing-summary">${escapeHtml(state.currentDate)} 的日报还没生成。你可以去流程里重做日报，或直接重新运行。</div>
    </div>`;
    return;
  }

  let html = `<div class="briefing-banner">
    <h2>今日日报</h2>
    <div class="briefing-summary">${escapeHtml(plainText(briefing.summary || ''))}</div>
    <div class="briefing-stats-row">
      <div class="briefing-stat"><span class="briefing-stat-num">${briefing.total_scenes || 0}</span><span class="briefing-stat-label">记录</span></div>
      <div class="briefing-stat"><span class="briefing-stat-num">${fmtNum(briefing.total_words || 0)}</span><span class="briefing-stat-label">字数</span></div>
      <div class="briefing-stat"><span class="briefing-stat-num">${briefing.voice_hours || 0}h</span><span class="briefing-stat-label">语音时长</span></div>
      <div class="briefing-stat"><span class="briefing-stat-num">${briefing.screen_recognition_available ? '已开' : '未开'}</span><span class="briefing-stat-label">屏幕上下文</span></div>
    </div>
  </div>`;

  html += '<div class="briefing-grid">';

  if (briefing.screen_highlights?.length) {
    html += `<div class="briefing-card">
      <div class="briefing-card-title">屏幕上下文 <span class="prop-count">${briefing.screen_highlights.length}</span></div>
      ${briefing.screen_highlights.map((item) => `<div class="event-item">${escapeHtml(plainText(item))}</div>`).join('')}
    </div>`;
  }

  if (briefing.completion_candidates?.length) {
    html += `<div class="briefing-card">
      <div class="briefing-card-title">完成候选 <span class="prop-count">${briefing.completion_candidates.length}</span></div>
      ${briefing.completion_candidates.map((item) => `<div class="event-item">${escapeHtml(plainText(item))}</div>`).join('')}
    </div>`;
  }


  if (briefing.work_sessions && Object.keys(briefing.work_sessions).length) {
    const maxValue = Math.max(...Object.values(briefing.work_sessions).map((value) => parseInt(value, 10) || 1));
    html += `<div class="briefing-card">
      <div class="briefing-card-title">应用使用</div>
      ${Object.entries(briefing.work_sessions).map(([app, duration]) => {
        const width = Math.max(6, ((parseInt(duration, 10) || 1) / maxValue) * 100);
        return `<div class="app-bar-row">
          <span class="app-bar-name">${escapeHtml(app)}</span>
          <div class="app-bar-track"><div class="app-bar-fill" style="width:${width}%"></div></div>
          <span class="app-bar-duration">${escapeHtml(duration)}</span>
        </div>`;
      }).join('')}
    </div>`;
  }

  if (briefing.decisions?.length) {
    html += `<div class="briefing-card">
      <div class="briefing-card-title">今日决策 <span class="prop-count">${briefing.decisions.length}</span></div>
      ${briefing.decisions.map((decision) => `<div class="event-item">${escapeHtml(plainText(decision))}</div>`).join('')}
    </div>`;
  }

  if (briefing.todos_open?.length) {
    html += `<div class="briefing-card">
      <div class="briefing-card-title">遗留待办 <span class="prop-count">${briefing.todos_open.length}</span></div>
      ${briefing.todos_open.map((todo) => `<div class="event-item">${escapeHtml(plainText(todo))}</div>`).join('')}
    </div>`;
  }

  if (briefing.key_events?.length) {
    html += `<div class="briefing-card briefing-card-full">
      <div class="briefing-card-title">关键事件 <span class="prop-count">${briefing.key_events.length}</span></div>
      ${briefing.key_events.map((event) => `<div class="event-item">${escapeHtml(plainText(event))}</div>`).join('')}
    </div>`;
  }

  if (briefing.time_blocks?.length) {
    html += `<div class="briefing-card briefing-card-full">
      <div class="briefing-card-title">时段追踪</div>
      ${briefing.time_blocks.map((block) => {
        const fullText = plainText(block.summary || '');
        const truncated = fullText.length > 80 ? fullText.slice(0, 80) + '…' : fullText;
        const needsTruncate = fullText.length > 80;
        return `<div class="time-block">
        <div class="tb-period">${escapeHtml((block.period || '').split(' ')[0])}</div>
        <div class="tb-body">
          <div class="tb-summary">
            <span class="tb-short">${escapeHtml(truncated)}</span>
            ${needsTruncate ? `<span class="tb-full" style="display:none">${escapeHtml(fullText)}</span>
            <button class="raw-btn" style="margin-left:4px;font-size:11px" onclick="const p=this.parentElement;const s=p.querySelector('.tb-short');const f=p.querySelector('.tb-full');const v=f.style.display==='none';f.style.display=v?'inline':'none';s.style.display=v?'none':'inline';this.textContent=v?'收起':'展开'">展开</button>` : ''}
          </div>
          <div class="tb-tags">
            ${(block.apps_used || []).map((app) => `<span class="tb-tag tb-tag-app">${escapeHtml(app)}</span>`).join('')}
          </div>
        </div>
      </div>`;
      }).join('')}
    </div>`;
  }

  html += '</div>';
  node.innerHTML = html;
}

function renderTimelineView() {
  const node = document.getElementById('view-timeline');
  if (!node) return;

  const detail = state.currentData;
  const meta = state.currentMeta || {};
  let html = '<div class="timeline">';
  detail.segments.forEach((segment) => {
    const distilled = getSegmentDistillation(segment, meta);

    html += `<div class="tl-node" data-segment-time="${escapeHtml(segment.time)}">
      <span class="tl-time">${escapeHtml(segment.time)}</span>
      <div class="tl-dot" style="border-color:var(--accent);background:var(--bg)"></div>
      <div class="tl-card">

        <div class="seg-distilled">${distilled}</div>
        <div class="raw-controls"><button class="raw-btn" type="button" onclick="toggleRawText(this)">显示原文</button></div>
        <div class="seg-raw">${fmtText(segment.text || '')}</div>
      </div>
    </div>`;
  });
  html += '</div>';
  node.innerHTML = html;
}

function renderTableView() {
  const node = document.getElementById('view-table');
  if (!node) return;

  const detail = state.currentData;
  let html = '<div class="table-view"><table class="data-table">';
  html += '<thead><tr><th width="80">时间</th><th>内容预览</th><th width="100">操作</th></tr></thead><tbody>';
  detail.segments.forEach((segment) => {
    html += `<tr>
      <td class="td-time">${escapeHtml(segment.time)}</td>
      <td class="td-summary">${escapeHtml(plainText(segment.preview || segment.text || ''))}</td>
      <td><button class="raw-btn" type="button" onclick="switchView('timeline'); scrollToSegment('${escapeHtml(segment.time)}')">👉 跳转</button></td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  node.innerHTML = html;
}

function renderChartsView() {
  const node = document.getElementById('view-charts');
  if (!node) return;
  node.innerHTML = `<div class="charts-grid">
    <div class="chart-card"><h3>时段热度</h3><canvas id="chartTime"></canvas></div>
  </div>`;
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

function renderCorrectionsView() {
  const node = document.getElementById('view-corrections');
  if (!node) return;

  node.innerHTML = `
    <div class="briefing-grid">
      <div class="briefing-card briefing-card-full">
        <div class="briefing-card-title" style="cursor:pointer" onclick="toggleAccordion(this)">高级操作（跟进 · 项目 · 决策） <span style="float:right;color:var(--text-light);font-size:12px">▼ 展开</span></div>
        <div class="accordion-body" style="display:none">
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-top:12px">
            <div>
              <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:8px">跟进处理</div>
              <select id="closeLoopSelect" class="field-select" style="margin-bottom:8px">${optionMarkup(state.loops, (item) => item.title || item.loop_id)}</select>
              <div class="inline-actions">
                <button class="action-btn" type="button" onclick="submitContextAction('/api/context/loops/close', { query: document.getElementById('closeLoopSelect').value, status: 'done' }, '已标记完成')">完成</button>
                <button class="action-btn" type="button" onclick="submitContextAction('/api/context/loops/reject', { query: document.getElementById('closeLoopSelect').value }, '已设为不再跟进')">移除</button>
              </div>
            </div>
            <div>
              <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:8px">项目整理</div>
              <select id="mergeProjectSource" class="field-select" style="margin-bottom:4px">${optionMarkup(state.projects, (item) => item.title || item.project_id)}</select>
              <select id="mergeProjectTarget" class="field-select" style="margin-bottom:8px">${optionMarkup(state.projects, (item) => item.title || item.project_id)}</select>
              <div class="inline-actions">
                <button class="action-btn" type="button" onclick="submitContextAction('/api/context/projects/merge', { source: document.getElementById('mergeProjectSource').value, target: document.getElementById('mergeProjectTarget').value }, '已合并')">合并</button>
                <button class="action-btn" type="button" onclick="submitContextAction('/api/context/projects/reject', { query: document.getElementById('mergeProjectSource').value }, '已移出')">移出</button>
              </div>
            </div>
            <div>
              <div style="font-weight:600;font-size:12px;color:var(--text-secondary);margin-bottom:8px">决策整理</div>
              <select id="rejectDecisionSelect" class="field-select" style="margin-bottom:8px">${optionMarkup(state.decisions, (item) => item.decision || item.topic || item.decision_id)}</select>
              <div class="inline-actions">
                <button class="action-btn" type="button" onclick="submitContextAction('/api/context/decisions/reject', { query: document.getElementById('rejectDecisionSelect').value }, '已移出')">移出决策</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderPipelineView() {
  const node = document.getElementById('view-pipeline');
  if (!node) return;

  const detail = state.selectedJobDetail;
  node.innerHTML = `
    <div class="briefing-grid">
      <div class="briefing-card">
        <div class="briefing-card-title">流程操作</div>
        <div class="form-stack">
          <div>
            <label class="form-label" for="pipelineDateInput">目标日期</label>
            <input id="pipelineDateInput" class="field-input" type="text" value="${escapeHtml(state.currentDate || '')}" placeholder="YYYY-MM-DD（默认当前日期）">
          </div>
          <div class="inline-actions">
            <button class="action-btn primary" type="button" onclick="createPipelineJob('context')">刷新上下文</button>
            <button class="action-btn" type="button" onclick="createPipelineJob('clean')">清理文本</button>
            <button class="action-btn" type="button" onclick="createPipelineJob('roles')">识别对象</button>
            <button class="action-btn" type="button" onclick="createPipelineJob('distill')">整理摘要</button>
            <button class="action-btn" type="button" onclick="createPipelineJob('briefing')">生成日报</button>
            <button class="action-btn" type="button" onclick="createPipelineJob('run')">重新运行</button>
          </div>
        </div>
      </div>

      <div class="briefing-card">
        <div class="briefing-card-title">流程说明</div>
        <div class="event-item"><code>刷新上下文</code> 不需要日期，其它流程默认使用当前选中的日期。</div>
        <div class="event-item">任务完成后会自动轮询，并刷新当前日期的数据。</div>
        <div class="event-item"><button class="action-btn" type="button" onclick="refreshPipelineJobs()">刷新列表</button></div>
      </div>
    </div>

    <div class="pipeline-layout">
      <div class="job-card">
        <div class="briefing-card-title">最近运行</div>
        <div id="pipelineJobsList" class="search-stack">
          ${renderEventList(
            state.jobs,
            (job) => `<button class="job-item ${job.job_id === state.selectedJobId ? 'active' : ''}" type="button" onclick="loadPipelineJobDetail('${escapeHtml(job.job_id)}')">
              <strong>${escapeHtml(formatPipelineKind(job.kind))}</strong>
              <div class="muted">${escapeHtml(job.target_date || '全局')} · ${escapeHtml(formatPipelineStatus(job.status))}</div>
            </button>`,
            '还没有运行记录。'
          )}
        </div>
      </div>

      <div class="job-card">
        <div class="briefing-card-title">运行详情</div>
        <div id="pipelineJobDetail">
          ${detail ? `
            <div class="event-item"><strong>流程</strong><br>${escapeHtml(formatPipelineKind(detail.kind))}</div>
            <div class="event-item"><strong>状态</strong><br>${escapeHtml(formatPipelineStatus(detail.status))}</div>
            <div class="event-item"><strong>当前步骤</strong><br>${escapeHtml(formatPipelineStep(detail.current_step))}</div>
            <div class="event-item"><strong>结果文件</strong><br>${escapeHtml((detail.artifacts || []).join(' / ') || '暂无')}</div>
            <pre class="job-log">${escapeHtml((detail.log_lines || []).join('\n') || '暂无日志')}</pre>
          ` : renderEmptyState('选择一条运行记录查看详情。')}
        </div>
      </div>
    </div>
  `;
}

function switchView(viewName) {
  state.currentView = viewName;
  document.querySelectorAll('.view-tab').forEach((node) => {
    node.classList.toggle('active', node.id === `tab-${viewName}`);
  });
  document.querySelectorAll('.view-content').forEach((node) => {
    node.classList.toggle('active', node.id === `view-${viewName}`);
  });
  const filterBar = document.getElementById('filter-bar');
  if (filterBar) {
    filterBar.style.display = viewName === 'timeline' ? 'flex' : 'none';
  }
  if (viewName === 'charts') {
    setTimeout(initCharts, 50);
  }
}

function toggleRawText(button) {
  const rawNode = button.parentElement.nextElementSibling;
  const visible = !rawNode.classList.contains('visible');
  rawNode.classList.toggle('visible', visible);
  button.innerHTML = visible ? '隐藏原文' : '显示原文';
  button.style.color = visible ? '#fff' : 'var(--text-secondary)';
  button.style.background = visible ? 'var(--text)' : 'var(--bg-sidebar)';
}

function filterRole(role) {
  if (role === 'all') {
    state.activeFilters.clear();
  } else if (state.activeFilters.has(role)) {
    state.activeFilters.delete(role);
  } else {
    state.activeFilters.add(role);
  }

  document.querySelectorAll('.role-tag').forEach((button) => {
    if (button.dataset.role === 'all') {
      button.classList.toggle('active', state.activeFilters.size === 0);
    } else {
      button.classList.toggle('active', state.activeFilters.has(button.dataset.role));
    }
  });

  document.querySelectorAll('#view-timeline .tl-node').forEach((node) => {
    if (state.activeFilters.size === 0) {
      node.classList.remove('hidden');
      return;
    }
    let matched = false;
    if (state.activeFilters.has('needs_review') && node.dataset.needsReview === 'true') matched = true;
    if (state.activeFilters.has(node.dataset.role)) matched = true;
    node.classList.toggle('hidden', !matched);
  });
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
  if (document.getElementById('view-corrections')) {
    renderCorrectionsView();
  }
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
    renderCorrectionsView();
    renderOverviewView();
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
    renderOverviewView();
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
    renderOverviewView();
  } catch (error) {
    showToast(error.message);
  }
}

function openSpotlight() {
  document.getElementById('spotlightOverlay').classList.add('active');
  document.getElementById('spotlightInput').focus();
}

function closeSpotlight(e) {
  if (e && e.target !== document.getElementById('spotlightOverlay')) return;
  document.getElementById('spotlightOverlay').classList.remove('active');
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
  }
});

async function runSearchSpotlight(query) {
  const container = document.getElementById('spotlightResults');
  if (!query) {
    container.innerHTML = '';
    return;
  }
  const results = await fetchJson(`/api/search?q=${encodeURIComponent(query)}`, []);
  if (!results.length) {
    container.innerHTML = '<div class="spotlight-empty">找不到相关的上下文</div>';
    return;
  }
  container.innerHTML = results.map(item => `
    <button class="spotlight-result-item" onclick="jumpToSearchResult('${escapeHtml(item.date)}', '${escapeHtml(item.time)}', '${escapeHtml(query)}')">
      <strong style="display:block;margin-bottom:4px;color:var(--text);font-size:13px">${escapeHtml(item.date)} · ${escapeHtml(item.time)}</strong>
      <div class="muted" style="font-size:12px;line-height:1.5">${item.context || escapeHtml(plainText(item.raw_context || ''))}</div>
    </button>
  `).join('');
}

async function jumpToSearchResult(date, time, query = '') {
  closeSpotlight();
  if (state.currentDate !== date) {
    await loadDate(date, time, query);
  } else {
    switchView('timeline');
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

  if (rerender && document.getElementById('view-pipeline')) {
    renderPipelineView();
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
      <button class="cp-close" onclick="closeSettingsOverlay()" style="background:none;border:none;font-size:18px;color:var(--text-secondary);cursor:pointer;line-height:1">✕</button>
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

    <div class="settings-section">
      <div class="settings-section-title">记忆库修整：纠正 AI 归档错误</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">
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
        <div id="pipelineJobDetail" style="margin-top:12px"></div>
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
  if (!targetEl.closest('.seg-raw, .seg-distilled, .tl-card, .briefing-card, .spotlight-result-item, .event-item, .prop-item, .time-block')) return;
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
