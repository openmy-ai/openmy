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
  paused: '已暂停',
  succeeded: '已完成',
  partial: '已部分完成',
  cancelled: '已取消',
  interrupted: '已中断',
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
  handledTerminalNotices: new Set(),
  homeJobFocusId: '',
  uploadingHomeFiles: false,
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

function getHomePipelineJob() {
  const activeJob = state.jobs.find((job) => ['queued', 'running', 'paused'].includes(job.status));
  if (activeJob) return activeJob;
  if (!state.homeJobFocusId) return null;
  return state.jobs.find((job) => job.job_id === state.homeJobFocusId) || null;
}

function formatDurationSeconds(value) {
  const seconds = Number(value || 0);
  if (!Number.isFinite(seconds) || seconds <= 0) return '—';
  const minutes = Math.floor(seconds / 60);
  const remain = seconds % 60;
  if (minutes <= 0) return `${remain}秒`;
  return `${minutes}:${String(remain).padStart(2, '0')}`;
}

function formatEtaSeconds(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return '预估中…';
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remain = seconds % 60;
  return `${minutes}:${String(remain).padStart(2, '0')}`;
}

function formatStepVisual(step) {
  const status = step?.status || 'pending';
  if (status === 'done') return { icon: '✓', className: 'step-done' };
  if (status === 'running') return { icon: '<span class="spinner"></span>', className: 'step-running' };
  if (status === 'skipped') return { icon: '↷', className: 'step-skipped' };
  if (status === 'failed') return { icon: '!', className: 'step-failed' };
  return { icon: '○', className: 'step-pending' };
}

function hasReadyTranscriptionProvider() {
  return Boolean(state.onboarding?.current_provider);
}

function renderHomeDropZone() {
  const providerReady = hasReadyTranscriptionProvider();
  const disabled = state.uploadingHomeFiles || !providerReady ? 'disabled' : '';
  const hint = state.uploadingHomeFiles
    ? '正在上传音频…'
    : providerReady
      ? '拖入音频，或者点一下选文件'
      : '先选转写引擎，再拖入音频';
  const subtitle = providerReady
    ? '文件收进来后，才会开始转写、清洗、场景切分和蒸馏。'
    : '现在先把转写引擎定下来，不然文件收进来也跑不动。';
  return `
    <div class="home-ingest-card">
      <div class="home-ingest-title">开始处理新录音</div>
      <div class="home-ingest-meta">支持 .wav .mp3 .m4a .aac .mp4 .mov .flac .ogg .webm</div>
      <div class="dropzone-card ${providerReady ? '' : 'is-blocked'}" id="homeDropzone" ondragover="onHomeDropzoneDragOver(event)" ondragleave="onHomeDropzoneDragLeave(event)" ondrop="onHomeDropzoneDrop(event)" onclick="${providerReady ? "document.getElementById('homeFileInput').click()" : "openSettings('transcription')"}">
        <div class="dropzone-icon">＋</div>
        <div class="dropzone-title">${hint}</div>
        <div class="dropzone-subtitle">${subtitle}</div>
        ${providerReady
          ? `<button class="action-btn primary" type="button" ${disabled} onclick="event.stopPropagation();document.getElementById('homeFileInput').click()">选择音频</button>`
          : `<button class="action-btn primary" type="button" onclick="event.stopPropagation();openSettings('transcription')">先选转写引擎</button>`}
        <input id="homeFileInput" type="file" ${disabled} accept=".wav,.mp3,.m4a,.aac,.mp4,.mov,.flac,.ogg,.webm" style="display:none" onchange="onHomeFileInputChange(event)">
      </div>
    </div>
  `;
}

function renderHomePipelineSlotCard(job) {
  if (!job) return renderHomeDropZone();
  const steps = job.steps || [];
  const recentLogs = [...(job.log_lines || [])].slice(-3).reverse();
  const isFinished = ['succeeded', 'partial'].includes(job.status);
  const isFailed = ['failed', 'cancelled', 'interrupted'].includes(job.status);
  const canPause = job.can_pause;
  const canResume = job.status === 'paused';
  const canSkip = job.can_skip;
  const sourceName = job.source_file || (job.target_date ? `${job.target_date} 的处理任务` : '处理中');
  const summaryText = isFailed
    ? (job.error || steps.find((step) => step.status === 'failed')?.result_summary || '这次处理没跑通。')
    : '';
  return `
    <div class="progress-home-card ${isFailed ? 'is-failed' : ''}">
      <div class="progress-home-header">
        <div>
          <div class="progress-home-title">OpenMy — 正在处理 ${escapeHtml(sourceName)}</div>
          <div class="progress-home-subtitle">${escapeHtml(formatPipelineStatus(job.status))}${job.target_date ? ` · ${escapeHtml(job.target_date)}` : ''}</div>
        </div>
        <div class="progress-home-percent">${Number(job.progress_pct || 0)}%</div>
      </div>
      <div class="progress-home-bar"><div class="progress-home-bar-fill" style="width:${Number(job.progress_pct || 0)}%"></div></div>
      <div class="progress-home-meta">
        <span>${escapeHtml(formatEtaSeconds(job.eta_seconds))}</span>
        <span>${escapeHtml(job.source_file || '等待任务推进')}</span>
      </div>
      ${isFailed ? `<div class="progress-home-failure">${escapeHtml(summaryText)}</div>` : ''}
      <div class="progress-home-steps">
        ${steps.map((step, index) => {
          const visual = formatStepVisual(step);
          return `
            <div class="progress-home-step ${visual.className}">
              <div class="progress-home-step-icon">${visual.icon}</div>
              <div class="progress-home-step-body">
                <div class="progress-home-step-head">
                  <span class="progress-home-step-label">${index + 1}/4 ${escapeHtml(step.label || step.name || '')}</span>
                  <span class="progress-home-step-duration">${escapeHtml(formatDurationSeconds(step.duration_seconds))}</span>
                </div>
                <div class="progress-home-step-summary">${escapeHtml(step.result_summary || '等待开始')}</div>
              </div>
            </div>
          `;
        }).join('')}
      </div>
      <div class="progress-home-log">
        <div class="progress-home-log-title">实时日志</div>
        ${recentLogs.length ? recentLogs.map((line) => {
          const isError = /失败|错误|error|failed/i.test(line);
          return `<div class="progress-home-log-line ${isError ? 'error' : ''}">${escapeHtml(line)}</div>`;
        }).join('') : '<div class="progress-home-log-line muted">还没有日志</div>'}
      </div>
      <div class="progress-home-actions">
        ${canPause ? `<button class="action-btn" type="button" onclick="runPipelineAction('${escapeHtml(job.job_id)}','pause')">暂停</button>` : ''}
        ${canResume ? `<button class="action-btn" type="button" onclick="runPipelineAction('${escapeHtml(job.job_id)}','resume')">继续</button>` : ''}
        ${canSkip ? `<button class="action-btn" type="button" onclick="runPipelineAction('${escapeHtml(job.job_id)}','skip')">跳过当前步骤</button>` : ''}
        ${!isFinished ? `<button class="action-btn danger" type="button" onclick="runPipelineAction('${escapeHtml(job.job_id)}','cancel')">取消</button>` : ''}
        ${isFailed ? `<button class="action-btn" type="button" onclick="openSettings('transcription')">去选转写引擎</button>` : ''}
        ${isFinished && job.target_date ? `<button class="action-btn primary" type="button" onclick="loadDate('${escapeHtml(job.target_date)}')">查看日报</button>` : ''}
        ${(isFinished || isFailed) ? `<button class="action-btn" type="button" onclick="clearHomeJobFocus()">收起结果</button>` : ''}
      </div>
    </div>
  `;
}

function rerenderHomePipelineSlot() {
  if (state.route !== 'home') return;
  const slot = document.getElementById('homePipelineSlot');
  if (!slot) return;
  slot.innerHTML = renderHomePipelineSlotCard(getHomePipelineJob());
}

function clearHomeJobFocus() {
  state.homeJobFocusId = '';
  rerenderHomePipelineSlot();
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
  const s = formatFriendlyDate(start);
  const e = formatFriendlyDate(end);
  return s === e ? s : `${s} – ${e}`;
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

function deriveProjectItemsFromDates(dates, limit = 4) {
  const counts = new Map();
  dates.forEach((item) => {
    const projectNames = [
      ...(item.decisions || []).map((entry) => entry.project),
      ...(item.todos || []).map((entry) => entry.project),
      ...(item.events || []).map((entry) => entry.project),
    ].filter(Boolean);
    [...new Set(projectNames)].forEach((name) => {
      counts.set(name, (counts.get(name) || 0) + 1);
    });
  });
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ label: name, meta: `${count} 天出现` }));
}

function deriveLoopItemsFromDates(dates, limit = 4) {
  return uniqueTextItems(
    dates.flatMap((item) => (item.todos || []).map((entry) => entry.task || entry.what || '')),
    limit,
  ).map((text) => ({ label: text, meta: '来自最近录音' }));
}

function looksWeakSummary(text) {
  const summary = plainText(text || '');
  if (!summary) return true;
  if (summary.length < 18) return true;
  const weakPatterns = ['主要用了', '主要在', '今天主要', '这段时间主要', '我主要', '暂无摘要'];
  return weakPatterns.some((pattern) => summary.includes(pattern));
}

function buildDailySummary(detail, meta) {
  const primary = plainText(meta.daily_summary || state.currentBriefing?.summary || state.context.status_line || '');
  if (!looksWeakSummary(primary)) return primary;

  const insight = plainText((meta.insights || [])[0]?.content || '');
  const decision = plainText((meta.decisions || [])[0]?.decision || (meta.decisions || [])[0]?.what || '');
  const todo = plainText((meta.todos || [])[0]?.task || (meta.intents || [])[0]?.summary || '');
  const preview = plainText(detail.segments?.[0]?.summary || detail.segments?.[0]?.preview || detail.segments?.[0]?.text || '').slice(0, 120);

  const lines = [
    insight && `今天最值得记住的是：${insight}`,
    decision && `今天定下来的是：${decision}`,
    todo && `接下来要盯的是：${todo}`,
  ].filter(Boolean);

  if (lines.length) return lines.join(' ');
  return preview || primary || '今天还没有可以展示的摘要。';
}

function buildWeeklySlots(dates) {
  if (!dates.length) return [];
  const latest = parseIsoDate(dates[0].date);
  const day = latest.getDay() || 7;
  const monday = new Date(latest);
  monday.setDate(latest.getDate() - day + 1);
  const map = new Map(dates.map((item) => [item.date, item]));
  return Array.from({ length: 7 }, (_, index) => {
    const current = new Date(monday);
    current.setDate(monday.getDate() + index);
    const date = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`;
    return map.get(date) || {
      date,
      segments: 0,
      word_count: 0,
      summary: '',
      timeline: [],
      decisions: [],
      todos: [],
      isPlaceholder: true,
    };
  });
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

  setInterval(refreshPipelineJobs, 1000);
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
    rerenderHomePipelineSlot();
    if (state.route === 'home') renderHomePage();
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
      <div id="homePipelineSlot">${renderHomePipelineSlotCard(getHomePipelineJob())}</div>

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
  const today = new Date();
  const monthDay = `${today.getMonth() + 1}月${today.getDate()}日`;

  const todayItem = recentDates.find((item) => item.date === today.toISOString().slice(0, 10)) || recentDates[0];
  const todaySummary = todayItem ? truncateSummary(buildDailySummary({ segments: todayItem.timeline || [] }, todayItem), 90) : '';

  const totalSegments = recentDates.reduce((sum, item) => sum + (item.segments || 0), 0);
  const totalWords = recentDates.reduce((sum, item) => sum + (item.word_count || 0), 0);
  const activeDays = recentDates.filter((item) => item.segments > 0).length;

  const projectItems = (state.context.active_projects || []).slice(0, 4).map((item) => ({
    label: item.title || item.project_id || '',
    meta: item.status || item.summary || '活跃中',
  }));
  const fallbackProjectItems = deriveProjectItemsFromDates(recentDates, 4);
  const loopItems = deriveLoopItemsFromDates(recentDates, 4);
  const correctionCount = (state.corrections || []).length;

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

      <div class="home-card-grid home-card-grid--dense">
        <div class="home-card home-card-grid--full" onclick="${todayItem ? `loadDate('${escapeHtml(todayItem.date)}')` : ''}">
          <div class="home-card-header">
            <span class="home-card-title">今日摘要</span>
            ${todayItem ? `<span class="home-card-badge">${todayItem.segments || 0}条记录</span>` : ''}
          </div>
          <div class="home-card-body">
            ${todaySummary ? escapeHtml(todaySummary) : '<span class="text-muted">今天还没有录音</span>'}
          </div>
        </div>

        <div class="home-card">
          <div class="home-card-header">
            <span class="home-card-title">最近录音</span>
            <span class="home-card-badge">${recentDates.length}</span>
          </div>
          <div class="home-card-list">
            ${recentDates.slice(0, 3).map((item) => `
              <button type="button" onclick="loadDate('${escapeHtml(item.date)}')">
                <div class="home-card-list-title">${escapeHtml(formatFriendlyDate(item.date))}</div>
                <div class="home-card-list-meta">${escapeHtml(truncateSummary(item.summary || item.timeline?.[0]?.preview || '还没有摘要', 40))}</div>
              </button>
            `).join('')}
          </div>
        </div>

        <div class="home-card">
          <div class="home-card-header">
            <span class="home-card-title">待纠错</span>
            <span class="home-card-badge">${correctionCount}</span>
          </div>
          <div class="home-card-body">
            ${correctionCount ? `词典里已经收了 ${correctionCount} 条纠正，点开可以继续加。` : '现在还没有纠错记录。你可以在日报里选中文字，右侧会滑出纠错抽屉。'}
          </div>
          <div class="home-card-footer">
            <button class="action-btn" type="button" onclick="openCorrectionPopover('', 0, 0, '先从日报里选中一句话，抽屉就会带着原句打开。')">打开纠错抽屉</button>
          </div>
        </div>

        <div class="home-card">
          <div class="home-card-header">
            <span class="home-card-title">活跃项目</span>
            <span class="home-card-badge">${(projectItems.length || fallbackProjectItems.length || loopItems.length) ? (projectItems.length || fallbackProjectItems.length || loopItems.length) : 0}</span>
          </div>
          ${(projectItems.length || fallbackProjectItems.length) ? `
            <div class="home-card-list">
              ${(projectItems.length ? projectItems : fallbackProjectItems).map((item) => `
                <div class="home-card-list-item">
                  <div class="home-card-list-title">${escapeHtml(item.label || '')}</div>
                  <div class="home-card-list-meta">${escapeHtml(item.meta || '')}</div>
                </div>
              `).join('')}
            </div>
          ` : loopItems.length ? `
            <div class="home-card-body">最近更像项目的事情还没被归类出来，我先把待做的事摆在这里。</div>
            <div class="home-card-list">
              ${loopItems.slice(0, 2).map((item) => `
                <div class="home-card-list-item">
                  <div class="home-card-list-title">${escapeHtml(item.label || '')}</div>
                  <div class="home-card-list-meta">${escapeHtml(item.meta || '')}</div>
                </div>
              `).join('')}
            </div>
          ` : `
            <div class="home-card-body text-muted">等你再跑几天录音，这里会自己长出项目卡片。</div>
          `}
        </div>
      </div>

      <div id="homePipelineSlot">${renderHomePipelineSlotCard(getHomePipelineJob())}</div>

      <div style="text-align:center;padding:24px 0">
        <button class="report-btn" type="button" onclick="state.showWikiHome=true;renderHomePage()">使用说明</button>
      </div>
    </div>
  `;
}


function renderReportPage(title, dates, extraMeta = '', isWeekly = false) {
  const main = document.getElementById('main');
  if (!dates.length) {
    main.innerHTML = `<div class="report-page"><h1>${escapeHtml(title)}</h1><div class="report-meta">当前没有可汇总的数据。</div></div>`;
    return;
  }

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
                <div class="heatmap-bar" style="height:${Math.max(percent, 6)}%"></div>
              </div>
              <div class="heatmap-count">${segments}</div>
            </div>`;
        }).join('')}
      </div>` : ''}

      ${highlightText ? `
      <div class="week-highlight">
        <div class="week-highlight-label">本周高亮</div>
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
    state.homeJobFocusId = job.job_id;
    showToast(`已开始：${formatPipelineKind(kind)}`);
    await refreshPipelineJobs();
  } catch (error) {
    showToast(error.message);
  }
}

async function uploadHomeAudioFiles(fileList) {
  if (!hasReadyTranscriptionProvider()) {
    showToast('先选转写引擎，再上传音频。');
    openSettings('transcription');
    return;
  }
  const files = Array.from(fileList || []);
  if (!files.length) return;
  const file = files[0];
  state.uploadingHomeFiles = true;
  rerenderHomePipelineSlot();
  try {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch('/api/upload', { method: 'POST', body: formData });
    const upload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(upload.error || `${response.status} ${response.statusText}`);
    }
    const job = await postJson('/api/pipeline/jobs', {
      kind: 'run',
      audio_files: [upload.file_path],
      source_file: upload.filename,
      source_size_bytes: upload.size_bytes,
    });
    state.selectedJobId = job.job_id;
    state.homeJobFocusId = job.job_id;
    showToast(`已开始处理：${upload.filename}`);
    await refreshPipelineJobs();
  } catch (error) {
    showToast(error.message);
  } finally {
    state.uploadingHomeFiles = false;
    rerenderHomePipelineSlot();
    const input = document.getElementById('homeFileInput');
    if (input) input.value = '';
  }
}

function onHomeFileInputChange(event) {
  uploadHomeAudioFiles(event.target.files);
}

function onHomeDropzoneDragOver(event) {
  event.preventDefault();
  event.currentTarget?.classList.add('dragover');
}

function onHomeDropzoneDragLeave(event) {
  event.preventDefault();
  event.currentTarget?.classList.remove('dragover');
}

function onHomeDropzoneDrop(event) {
  event.preventDefault();
  event.currentTarget?.classList.remove('dragover');
  uploadHomeAudioFiles(event.dataTransfer?.files || []);
}

async function runPipelineAction(jobId, action) {
  try {
    const payload = await postJson(`/api/pipeline/jobs/${jobId}/${action}`, {});
    state.selectedJobId = jobId;
    state.homeJobFocusId = jobId;
    state.selectedJobDetail = payload;
    showToast(`已执行：${action === 'pause' ? '暂停' : action === 'resume' ? '继续' : action === 'cancel' ? '取消' : '跳过'}`);
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
  if (state.homeJobFocusId && !state.jobs.find((job) => job.job_id === state.homeJobFocusId)) {
    state.homeJobFocusId = '';
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
  rerenderHomePipelineSlot();

  // Global Indicator Logic
  const activeJobs = state.jobs.filter(j => ['queued', 'running', 'paused'].includes(j.status));
  const indicator = document.getElementById('globalJobIndicator');
  if (indicator) {
    if (activeJobs.length > 0) {
      const current = activeJobs[0];
      document.getElementById('globalJobText').textContent = current?.source_file
        ? `正在处理 ${current.source_file}`
        : `正在后台执行 ${activeJobs.length} 个分析任务...`;
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
  if (state.homeJobFocusId === jobId || ['queued', 'running', 'paused'].includes(detail.status)) {
    state.homeJobFocusId = jobId;
  }

  if (detail.status === 'succeeded' && !state.handledCompletedJobs.has(detail.job_id)) {
    state.handledCompletedJobs.add(detail.job_id);
    await handleJobCompletion(detail);
  }
  if (['failed', 'partial', 'cancelled', 'interrupted'].includes(detail.status) && !state.handledTerminalNotices.has(detail.job_id)) {
    state.handledTerminalNotices.add(detail.job_id);
    showToast(detail.error || detail.steps?.find((step) => step.status === 'failed')?.result_summary || `处理状态：${formatPipelineStatus(detail.status)}`);
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

// === Correction Drawer ===
document.addEventListener('mouseup', (e) => {
  const selection = window.getSelection();
  const selectedText = selection?.toString().trim();
  if (!selectedText || selectedText.length < 2 || selectedText.length > 50) return;
  const targetEl = e.target;
  if (targetEl.closest('input, textarea, button, select, .correction-drawer, .spotlight-modal')) return;
  if (!targetEl.closest('.seg-raw, .seg-distilled, .record-card, .briefing-card, .spotlight-result-item, .event-item, .prop-item, .time-block')) return;
  const contextText = plainText(targetEl.closest('.record-card, .briefing-card, .event-item, .prop-item, .time-block')?.textContent || selectedText);
  openCorrectionPopover(selectedText, e.clientX, e.clientY, contextText);
});

function openCorrectionPopover(wrongText = '', mouseX = 0, mouseY = 0, contextText = '') {
  const drawer = document.getElementById('correctionPopover');
  const wrongEl = document.getElementById('cpWrongText');
  const contextEl = document.getElementById('cpContextText');
  const rightInput = document.getElementById('cpRightInput');
  wrongEl.textContent = wrongText || '先在日报里选中一段文字';
  contextEl.textContent = contextText || '先从日报里选中一句话，抽屉就会带着原句打开。';
  rightInput.value = wrongText || '';
  drawer.classList.add('is-open');
  document.body.style.overflow = 'hidden';
  setTimeout(() => rightInput.focus(), 80);
}

function closeCorrectionPopover() {
  document.getElementById('correctionPopover').classList.remove('is-open');
  document.body.style.overflow = '';
}

async function submitInlineCorrection() {
  const wrong = document.getElementById('cpWrongText').textContent.trim();
  const right = document.getElementById('cpRightInput').value.trim();
  const context = document.getElementById('cpContextText').textContent.trim();
  if (!wrong || wrong.includes('先在日报里选中')) { showToast('先选中一段日报文字，再来纠错。'); return; }
  if (!right) { showToast('请输入正确的文本'); return; }
  if (wrong === right) { showToast('纠正前后相同'); return; }
  try {
    await postJson('/api/correct/typo', {
      wrong, right, context, date: state.currentDate, sync_vocab: true,
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
  const drawer = document.getElementById('correctionPopover');
  if (drawer.classList.contains('is-open') && !drawer.contains(e.target)) {
    closeCorrectionPopover();
  }
});

init();
