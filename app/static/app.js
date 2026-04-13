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
  onboarding: {},
  selectedTranscriptionProvider: '',
  showWikiHome: false,
  settingsSection: '',
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
    .replace(/^---+$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
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

function formatFriendlyDate(dateStr) {
  const date = parseIsoDate(dateStr);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function formatPageDate(dateStr) {
  const date = parseIsoDate(dateStr);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function formatRangeLabel(start, end) {
  return `${formatShortDate(start)}–${formatShortDate(end)}`;
}

function truncateSummary(text, maxLength = 50) {
  const summary = plainText(text || '');
  if (!summary) return '暂无摘要';
  return summary.length > maxLength ? `${summary.slice(0, maxLength)}…` : summary;
}

function getVisibleDates() {
  const currentYear = new Date().getFullYear();
  return [...(state.allDates || [])]
    .filter((item) => {
      const year = Number.parseInt(String(item?.date || '').split('-')[0], 10);
      return Number.isFinite(year) && year <= currentYear + 1;
    });
}

function latestDateInfo() {
  return getVisibleDates().sort((a, b) => b.date.localeCompare(a.date))[0] || null;
}

function filterDateRange(startDate, endDate) {
  return getVisibleDates()
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
    loadOnboarding(),
    loadScreenContextSettings(),
    refreshCorrectionsFeed(),
    refreshPipelineJobs(),
  ]);
  renderHomePage();

  setInterval(refreshPipelineJobs, 5000);
}


async function loadOnboarding() {
  state.onboarding = await fetchJson('/api/onboarding', {});
  if (state.route === 'home') {
    renderHomePage();
  }
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


function renderOnboardingCard() {
  return renderHomeOnboardingCard();
}

function getTranscriptionIcon(provider) {
  return `/static/icons/${provider}.svg`;
}

function renderHomeOnboardingCard() {
  const onboarding = state.onboarding || {};
  const currentProvider = onboarding.current_provider || '';
  const currentLabel = currentProvider ? (onboarding.choices?.local || []).concat(onboarding.choices?.cloud || []).find((item) => item.name === currentProvider)?.label || currentProvider : '';
  const title = currentProvider ? `已选转写模型：${currentLabel}` : '还没选转写模型';
  const desc = currentProvider ? '现在可以直接开始第一次 quick-start（快速开始），要改的话也可以去左侧菜单里换。' : '先把转写模型定下来，别再去角落里找设置。';
  const cta = currentProvider ? '去设置里改' : '去设置里选';
  return `
    <section class="callout onboarding-card onboarding-card-compact">
      <div class="callout-body">
        <div class="section-kicker">网页首配入口</div>
        <h2 class="onboarding-title">${escapeHtml(title)}</h2>
        <p class="onboarding-copy">${escapeHtml(desc)}</p>
        <div class="inline-actions"><button class="action-btn primary" type="button" onclick="openSettings('transcription')">${cta}</button></div>
      </div>
    </section>
  `;
}

function renderTranscriptionSettings() {
  const onboarding = state.onboarding || {};
  const localChoices = onboarding.choices?.local || [];
  const cloudChoices = onboarding.choices?.cloud || [];
  const selected = state.selectedTranscriptionProvider || onboarding.current_provider || onboarding.recommended_provider || '';
  const currentLabel = currentProviderLabel();
  const renderChoice = (item) => `
    <button class="transcription-option ${selected === item.name ? 'active' : ''}" type="button" onclick="selectTranscriptionOption('${escapeHtml(item.name || '')}')">
      <img class="transcription-option-icon" src="${getTranscriptionIcon(item.name || '')}" alt="">
      <div>
        <div class="transcription-option-title">${escapeHtml(item.label || item.name)}</div>
        <div class="transcription-option-desc">${escapeHtml(item.description || '')}</div>
        <div class="transcription-option-state">${item.is_recommended ? '推荐' : selected === item.name ? '已选中' : '点一下选中'}</div>
      </div>
    </button>
  `;

  return `
    <div class="settings-section" id="transcriptionSettingsSection">
      <div class="settings-section-title">转写模型</div>
      <div class="transcription-grid">
        ${localChoices.map(renderChoice).join('')}
        ${cloudChoices.map(renderChoice).join('')}
      </div>
      <div class="transcription-actions">
        <div class="transcription-current">当前：${escapeHtml(currentLabel || '还没定')}</div>
        <button class="action-btn primary" type="button" onclick="confirmTranscriptionProvider()">确认</button>
      </div>
    </div>
  `;
}

function currentProviderLabel() {
  const onboarding = state.onboarding || {};
  const items = (onboarding.choices?.local || []).concat(onboarding.choices?.cloud || []);
  const provider = onboarding.current_provider || '';
  return items.find((item) => item.name === provider)?.label || provider;
}

function selectTranscriptionOption(provider) {
  state.selectedTranscriptionProvider = provider;
  rerenderSettingsOverlay();
}

async function confirmTranscriptionProvider() {
  const provider = state.selectedTranscriptionProvider || state.onboarding?.recommended_provider || '';
  if (!provider) return;
  await selectOnboardingProvider(provider, { closeSettings: true });
}

async function selectOnboardingProvider(provider, options = {}) {
  if (!provider) return;
  try {
    const result = await postJson('/api/onboarding/select', { provider });
    if (result?.onboarding) {
      state.onboarding = result.onboarding;
    }
    showToast(result?.human_summary || `已经切到 ${provider}`);
    if (result?.onboarding) {
      state.onboarding = result.onboarding;
    }
    state.selectedTranscriptionProvider = provider;
    rerenderHomeOnboardingSlot();
    if (options.closeSettings) closeSettingsOverlay();
  } catch (error) {
    showToast(`设置失败：${error.message}`);
  }
}

function renderHomePage() {
  closeSidebar();
  setRoute('home');
  state.currentDate = '';
  const visibleDates = getVisibleDates();
  if (visibleDates.length && !state.showWikiHome) {
    renderRecentSummaryHome(visibleDates);
  } else {
    renderWikiHome();
  }
}

function renderWikiHome() {
  const main = document.getElementById('main');
  const onboarding = state.onboarding || {};
  const needsSetup = !onboarding.current_provider;
  const setupNotice = needsSetup
    ? `<div class="wiki-notice"><span>还没配置转写引擎</span> <button class="action-btn" type="button" onclick="openSettings('transcription')">去设置</button></div>`
    : '';

  main.innerHTML = `
    <div class="home-page wiki-home">
      ${setupNotice}
      <h1>OpenMy</h1>
      <div class="home-meta">把你每天说的话变成可搜索、可回顾的个人上下文。<br>录音 → 转写 → 整理 → 浏览，全部在本地完成。</div>

      <div class="wiki-section">
        <div class="section-kicker">快速开始</div>
        <div class="wiki-steps">
          <button class="wiki-step" type="button" onclick="openSettings('transcription')">
            <span class="wiki-step-num">1</span>
            <span class="wiki-step-body">
              <span class="wiki-step-title">选择转写引擎</span>
              <span class="wiki-step-desc">本地免费或云端更快，6种引擎可选</span>
            </span>
          </button>
          <button class="wiki-step" type="button" onclick="showToast('在终端运行 openmy quick-start 开始转写')">
            <span class="wiki-step-num">2</span>
            <span class="wiki-step-body">
              <span class="wiki-step-title">运行转写</span>
              <span class="wiki-step-desc">终端输入 openmy quick-start，跟着提示走</span>
            </span>
          </button>
          <button class="wiki-step" type="button" onclick="document.querySelector('.date-list')?.scrollIntoView({behavior:'smooth'})">
            <span class="wiki-step-num">3</span>
            <span class="wiki-step-body">
              <span class="wiki-step-title">回来看结果</span>
              <span class="wiki-step-desc">刷新页面，左边出现日期，点进去看内容</span>
            </span>
          </button>
        </div>
      </div>

      <div class="wiki-section">
        <div class="section-kicker">功能</div>
        <div class="wiki-features">
          <button class="wiki-feature" type="button" onclick="openSettings('transcription')">
            <span class="wiki-feature-title">音频转文字</span>
            <span class="wiki-feature-desc">6种转写引擎，中英文，本地或云端</span>
          </button>
          <button class="wiki-feature" type="button" onclick="showToast('转写完成后自动生成摘要、决策和待办')">
            <span class="wiki-feature-title">自动整理</span>
            <span class="wiki-feature-desc">转写完自动提取摘要、决策、待办和洞察</span>
          </button>
          <button class="wiki-feature" type="button" onclick="openSpotlight()">
            <span class="wiki-feature-title">全文搜索</span>
            <span class="wiki-feature-desc">按关键词搜索所有日期的对话内容</span>
          </button>
          <button class="wiki-feature" type="button" onclick="openSettings()">
            <span class="wiki-feature-title">屏幕记录</span>
            <span class="wiki-feature-desc">自动截屏加文字识别，和语音对照</span>
          </button>
          <button class="wiki-feature" type="button" onclick="toggleSidebarDict()">
            <span class="wiki-feature-title">纠错词典</span>
            <span class="wiki-feature-desc">转写有误点一下纠正，下次自动生效</span>
          </button>
          <button class="wiki-feature" type="button" onclick="renderWeeklyReport()">
            <span class="wiki-feature-title">周报月报</span>
            <span class="wiki-feature-desc">自动汇总一周或一个月的记录和趋势</span>
          </button>
        </div>
      </div>

      <div class="wiki-section">
        <div class="section-kicker">转写引擎</div>
        <div class="wiki-engines">
          <button class="wiki-engine" type="button" onclick="openSettings('transcription')"><span class="wiki-engine-tag tag-local">本地</span><span class="wiki-engine-name">FunASR</span><span class="wiki-engine-note">中文优先，不要密钥</span></button>
          <button class="wiki-engine" type="button" onclick="openSettings('transcription')"><span class="wiki-engine-tag tag-local">本地</span><span class="wiki-engine-name">Faster Whisper</span><span class="wiki-engine-note">通用，不要密钥</span></button>
          <button class="wiki-engine" type="button" onclick="openSettings('transcription')"><span class="wiki-engine-tag tag-cloud">云端</span><span class="wiki-engine-name">Gemini</span><span class="wiki-engine-note">速度快，推荐</span></button>
          <button class="wiki-engine" type="button" onclick="openSettings('transcription')"><span class="wiki-engine-tag tag-cloud">云端</span><span class="wiki-engine-name">DashScope</span><span class="wiki-engine-note">中文精度高</span></button>
          <button class="wiki-engine" type="button" onclick="openSettings('transcription')"><span class="wiki-engine-tag tag-cloud">云端</span><span class="wiki-engine-name">Groq</span><span class="wiki-engine-note">极快</span></button>
          <button class="wiki-engine" type="button" onclick="openSettings('transcription')"><span class="wiki-engine-tag tag-cloud">云端</span><span class="wiki-engine-name">Deepgram</span><span class="wiki-engine-note">英文场景</span></button>
        </div>
      </div>

      <div class="wiki-section">
        <div class="section-kicker">常用命令</div>
        <table class="wiki-cmd-table">
          <tbody>
            <tr><td>openmy quick-start</td><td>交互式引导，从选引擎到出结果</td></tr>
            <tr><td>openmy run --date 2026-04-08</td><td>处理指定日期的录音</td></tr>
            <tr><td>openmy report</td><td>打开这个网页界面</td></tr>
            <tr><td>openmy screen on</td><td>开启屏幕截图记录</td></tr>
            <tr><td>openmy correct typo</td><td>纠正转写错误</td></tr>
          </tbody>
        </table>
      </div>

      <div class="wiki-section wiki-links">
        <a href="https://github.com/openmy-ai/openmy" target="_blank" rel="noopener">GitHub</a>
        <a href="https://github.com/openmy-ai/openmy#readme" target="_blank" rel="noopener">完整文档</a>
        <a href="https://github.com/openmy-ai/openmy/issues" target="_blank" rel="noopener">反馈问题</a>
      </div>
    </div>
  `;
}

function renderRecentSummaryHome(visibleDates) {
  const main = document.getElementById('main');
  const recentDates = visibleDates.slice(0, 7);

  main.innerHTML = `
    <div class="home-page">
      <div class="home-header-row">
        <h1>OpenMy</h1>
        <button class="report-btn" type="button" onclick="state.showWikiHome=true;renderHomePage()">使用说明</button>
      </div>
      <div class="home-meta">最近记录</div>
      <div class="daily-link-list">
        ${recentDates.map((item) => `
          <button class="daily-link-item" type="button" onclick="loadDate('${escapeHtml(item.date)}')">
            <span class="daily-link-date">${escapeHtml(formatFriendlyDate(item.date))}</span>
            <span class="daily-link-summary">${item.segments ? escapeHtml(truncateSummary(item.summary || item.timeline?.[0]?.preview || '')) : '<span class="text-muted">仅屏幕截图</span>'}</span>
            <span class="daily-link-count">${item.segments ? item.segments + '条' : '截屏'}</span>
          </button>
        `).join('')}
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

  const summaryText = plainText(meta.daily_summary || state.currentBriefing?.summary || state.context.status_line || '');
  const headerMeta = [
    detail.date,
    `${detail.segments.length}条记录`,
    `${fmtNum(detail.word_count || 0)}字`,
  ];

  document.getElementById('main').innerHTML = `
    <article class="daily-article">
      <header class="page-header">
        <div class="page-title">${escapeHtml(formatPageDate(detail.date))}</div>
        <div class="page-meta">${headerMeta.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}</div>
      </header>
      ${summaryText ? `<section class="summary-callout"><p>${escapeHtml(summaryText)}</p></section>` : ''}
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

function renderScreenActivity(events) {
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
              <span class="screen-activity-count">${item.count}次</span>
            </div>
          `;
        }).join('')}
      </div>
    </section>
  `;
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
    if (!items.length) return '';
    return `<section class="meta-section" style="--section-color:${group.dot}">
      <div class="prop-card">
      <div class="prop-card-title"><span class="dot" style="background:${group.dot}"></span>${group.title} <span class="prop-count">${items.length}</span></div>
      ${items.map((item) => {
        const time = escapeHtml(item.time || '');
        const project = escapeHtml(item.project || item.topic || '');
        const summary = escapeHtml(plainText(item.summary || item.what || item.task || item.content || item.decision || item.fact || item.intent || ''));
        return `<div class="prop-item">
          ${time ? `<span class="time-tag">${time}</span>` : ''}
          ${summary}${project ? ` <span class="inline-project">(${project})</span>` : ''}
        </div>`;
      }).join('')}
      </div>
    </section>`;
  }).filter(Boolean);

  return cards.length ? `<div class="props-grid">${cards.join('')}</div>` : '';
}

function getSegmentDistillation(segment, meta) {
  if (segment.summary) return escapeHtml(plainText(segment.summary));
  return escapeHtml(plainText(segment.preview || segment.text || '').slice(0, 200));
}

function toggleSection(header) {
  const content = header?.nextElementSibling;
  const arrow = header?.querySelector('.collapse-arrow');
  if (!content || !arrow) return;
  const isCollapsed = content.classList.toggle('collapsed');
  arrow.textContent = isCollapsed ? '▶' : '▼';
}

function initCharts() {
  if (!state.currentData) return;
  if (typeof Chart === 'undefined') return;
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
  const section = arguments[0] || '';
  const overlay = document.getElementById('settingsOverlay');
  const content = document.getElementById('settingsContent');
  state.settingsSection = section;
  if (!state.selectedTranscriptionProvider) {
    state.selectedTranscriptionProvider = state.onboarding?.current_provider || state.onboarding?.recommended_provider || '';
  }
  document.getElementById('settingsBtn')?.classList.add('active');
  document.getElementById('transcriptionBtn')?.classList.add('active');
  content.innerHTML = renderSettingsHTML();
  overlay.classList.add('active');
  applySettingsUI();
  if (section === 'transcription') {
    document.getElementById('transcriptionSettingsSection')?.scrollIntoView({ block: 'start' });
  }
}

function closeSettingsOverlay(e) {
  if (e) e.stopPropagation();
  const overlay = document.getElementById('settingsOverlay');
  overlay.classList.remove('active');
  document.getElementById('settingsBtn')?.classList.remove('active');
  document.getElementById('transcriptionBtn')?.classList.remove('active');
}

function renderSettingsHTML() {
  return `
  <div class="settings-page" style="padding:0">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
      <h2 style="margin:0;font-size:20px;">设置</h2>
      <button class="cp-close" onclick="closeSettingsOverlay()" style="background:none;border:none;font-size:14px;color:var(--text-secondary);cursor:pointer;line-height:1">关闭</button>
    </div>

    ${renderTranscriptionSettings()}

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
