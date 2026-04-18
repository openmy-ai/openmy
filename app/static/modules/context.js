// context.js — 上下文查询和 Wiki 首页
import { state } from './state.js';
import { fetchJson } from './api.js';
import { escapeHtml, plainText } from './utils.js';
import { getHomePipelineJob, renderHomePipelineSlotCard } from './pipeline.js';
import { loadDate } from './daily.js';
import { setRoute } from './router.js';

let contextHooks = {
  rerenderSettingsOverlay: () => {},
  renderHomePage: () => {},
  renderWeeklyReport: () => {},
  renderMonthlyReport: () => {},
};

export function setContextHooks(hooks = {}) {
  contextHooks = { ...contextHooks, ...hooks };
}

export function renderContextQueryResult() {
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

// --- Engine readable name map ---
const ENGINE_NAMES = {
  funasr: 'FunASR',
  'faster-whisper': 'Faster Whisper',
  whisper: 'Whisper',
  gemini: 'Gemini',
  dashscope: 'DashScope',
  groq: 'Groq',
  deepgram: 'Deepgram',
};

export function getEngineDisplayName(name) {
  return ENGINE_NAMES[name] || name;
}

// --- Wizard navigation ---
export function wizardNext() {
  state.wizardStep = Math.min((state.wizardStep || 0) + 1, 3);
  renderWikiHome();
}

export function wizardBack() {
  state.wizardStep = Math.max((state.wizardStep || 0) - 1, 0);
  renderWikiHome();
}

export function wizardSelectEngine(provider) {
  state.selectedTranscriptionProvider = provider;
  renderWikiHome();
}

export async function wizardConfirmEngine() {
  const provider = state.selectedTranscriptionProvider;
  if (!provider) return;
  try {
    const { postJson } = await import('./api.js');
    const { showToast } = await import('./utils.js');
    const result = await postJson('/api/onboarding/select', { provider });
    if (result?.onboarding) state.onboarding = result.onboarding;
    state.selectedTranscriptionProvider = provider;
    showToast(result?.human_summary || `已选 ${getEngineDisplayName(provider)}`);
  } catch (e) { /* ignore */ }
  wizardNext();
}

export function wizardGoHome() {
  state.showWikiHome = false;
  state.wizardStep = 0;
  const { renderHomePage } = contextHooks;
  renderHomePage?.();
}

export function renderWikiHome() {
  setRoute('start');
  const main = document.getElementById('main');
  const step = state.wizardStep || 0;
  const onboarding = state.onboarding || {};
  const localChoices = onboarding.choices?.local || [];
  const cloudChoices = onboarding.choices?.cloud || [];
  const selected = state.selectedTranscriptionProvider || onboarding.current_provider || onboarding.recommended_provider || '';
  const hasProvider = !!onboarding.current_provider;

  const STEPS = [
    { label: '欢迎' },
    { label: '选引擎' },
    { label: '录音' },
    { label: '完成' },
  ];

  // --- Progress bar ---
  const progressHTML = STEPS.map((s, i) => {
    const cls = i < step ? 'done' : i === step ? 'active' : '';
    const dotContent = i < step ? '✓' : (i + 1);
    const lineAfter = i < STEPS.length - 1
      ? `<div class="wizard-progress-line ${i < step ? 'done' : ''}"></div>`
      : '';
    return `<div class="wizard-progress-step ${cls}"><span class="wizard-progress-dot">${dotContent}</span><span>${escapeHtml(s.label)}</span></div>${lineAfter}`;
  }).join('');

  // --- Step content ---
  let bodyHTML = '';

  if (step === 0) {
    // Welcome
    bodyHTML = `
      <div class="wizard-hero-icon">🎙️</div>
      <div class="wizard-hero-title">欢迎使用 OpenMy</div>
      <div class="wizard-hero-desc">
        把你每天说的话变成可搜索、可回顾的个人上下文。<br>
        录音 → 转写 → 整理 → 浏览，全部在本地完成。
      </div>
    `;
  } else if (step === 1) {
    // Engine selection — show real names, minimal noise
    const renderItem = (item) => {
      const isActive = selected === item.name;
      const displayName = getEngineDisplayName(item.name);
      const isRec = item.is_recommended;
      return `
        <button class="wizard-engine-item ${isActive ? 'active' : ''}" type="button" onclick="wizardSelectEngine('${escapeHtml(item.name)}')">
          <div>
            <span class="wizard-engine-name">${escapeHtml(displayName)}</span>
            ${isRec ? '<span class="wizard-engine-badge">推荐</span>' : ''}
          </div>
          <div class="wizard-engine-check">${isActive ? '✓' : ''}</div>
        </button>
      `;
    };

    bodyHTML = `
      <div class="wizard-step-title">选一个转写引擎</div>
      <div class="wizard-step-desc">本地免费，云端更快。选一个就行。</div>

      <div class="wizard-engine-group">
        <div class="wizard-engine-group-title"><span class="wizard-engine-group-tag tag-local">本地</span> 免费，不需要密钥</div>
        ${localChoices.map(renderItem).join('')}
      </div>

      <div class="wizard-engine-group">
        <div class="wizard-engine-group-title"><span class="wizard-engine-group-tag tag-cloud">云端</span> 需要 API Key</div>
        ${cloudChoices.map(renderItem).join('')}
      </div>
    `;
  } else if (step === 2) {
    // Upload — directly embed dropzone, no terminal
    const engineLabel = hasProvider ? getEngineDisplayName(onboarding.current_provider) : (selected ? getEngineDisplayName(selected) : '');
    bodyHTML = `
      <div class="wizard-step-title">上传第一段录音</div>
      <div class="wizard-step-desc">
        ${engineLabel ? `引擎：<strong>${escapeHtml(engineLabel)}</strong>。` : ''}
        把音频文件拖进来，系统自动处理。
      </div>

      <div class="dropzone-card wizard-dropzone" id="homeDropzone"
           ondragover="onHomeDropzoneDragOver(event)"
           ondragleave="onHomeDropzoneDragLeave(event)"
           ondrop="onHomeDropzoneDrop(event)"
           onclick="document.getElementById('homeFileInput')?.click()">
        <div class="dropzone-icon">＋</div>
        <div class="dropzone-title">拖入音频，或点击选文件</div>
        <div class="dropzone-subtitle">支持 .wav .mp3 .m4a .aac .flac 等格式</div>
        <input id="homeFileInput" type="file" accept=".wav,.mp3,.m4a,.aac,.mp4,.mov,.flac,.ogg,.webm" style="display:none" onchange="onHomeFileInputChange(event)">
      </div>

      <div class="wizard-skip-hint">
        没有音频？跳过这步，以后随时可以上传。
      </div>
    `;
  } else if (step === 3) {
    // Done
    bodyHTML = `
      <div class="wizard-done-icon">✅</div>
      <div class="wizard-step-title">配置完成！</div>
      <div class="wizard-step-desc">你可以回到首页查看数据，或继续探索这些功能：</div>

      <ul class="wizard-features-list">
        <li><span class="feature-icon">🔍</span><span class="feature-text">全文搜索</span><span class="feature-hint">按 ⌘K</span></li>
        <li><span class="feature-icon">✏️</span><span class="feature-text">纠错词典</span><span class="feature-hint">在日报里选中文字</span></li>
        <li><span class="feature-icon">📊</span><span class="feature-text">周报 / 月报</span><span class="feature-hint">侧边栏切换</span></li>
        <li><span class="feature-icon">🖥️</span><span class="feature-text">屏幕活动记录</span><span class="feature-hint">设置里开启</span></li>
        <li><span class="feature-icon">🎵</span><span class="feature-text">录音回放</span><span class="feature-hint">日报里点播放</span></li>
      </ul>

      <div class="wizard-step-desc" style="margin-bottom:16px">常用命令：</div>
      <table class="wizard-cmd-table">
        <tr><td>openmy quick-start</td><td>交互式引导，从选引擎到出结果</td></tr>
        <tr><td>openmy run --date 2026-04-08</td><td>处理指定日期的录音</td></tr>
        <tr><td>openmy report</td><td>打开网页界面</td></tr>
        <tr><td>openmy screen on</td><td>开启屏幕截图记录</td></tr>
        <tr><td>openmy correct typo</td><td>纠正转写错误</td></tr>
      </table>
    `;
  }

  // --- Navigation ---
  let navHTML = '';
  if (step === 0) {
    navHTML = `<div class="wizard-nav-spacer"></div><button class="wizard-nav-btn primary" type="button" onclick="wizardNext()">开始配置 →</button>`;
  } else if (step === 1) {
    const nextAction = selected ? `wizardConfirmEngine()` : `wizardNext()`;
    const nextLabel = selected ? '确认并继续 →' : '跳过 →';
    navHTML = `
      <button class="wizard-nav-btn" type="button" onclick="wizardBack()">← 上一步</button>
      <button class="wizard-nav-btn primary" type="button" onclick="${nextAction}">${nextLabel}</button>
    `;
  } else if (step === 2) {
    navHTML = `
      <button class="wizard-nav-btn" type="button" onclick="wizardBack()">← 上一步</button>
      <button class="wizard-nav-btn primary" type="button" onclick="wizardNext()">完成 ✓</button>
    `;
  } else if (step === 3) {
    navHTML = `
      <div class="wizard-nav-spacer"></div>
      <button class="wizard-nav-btn primary" type="button" onclick="wizardGoHome()">回到首页</button>
    `;
  }

  main.innerHTML = `
    <div class="wizard">
      <div class="wizard-progress">${progressHTML}</div>
      <div class="wizard-body">${bodyHTML}</div>
      <div class="wizard-nav">${navHTML}</div>
    </div>
  `;
}

export async function loadContext() {
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

  contextHooks.rerenderSettingsOverlay();
  if (state.route === 'home') {
    contextHooks.renderHomePage();
  } else if (state.route === 'weekly') {
    contextHooks.renderWeeklyReport();
  } else if (state.route === 'monthly') {
    contextHooks.renderMonthlyReport();
  }
}

export async function runContextQuery(kind = '', query = '') {
  const kindEl = document.getElementById('contextQueryKind');
  const inputEl = document.getElementById('contextQueryInput');
  const finalKind = kind || kindEl?.value || state.contextQuery.kind || 'project';
  const finalQuery = query !== '' ? query : (inputEl?.value || '').trim();

  state.contextQuery.kind = finalKind;
  state.contextQuery.query = finalQuery;
  state.contextQuery.loading = true;
  contextHooks.rerenderSettingsOverlay();

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
    contextHooks.rerenderSettingsOverlay();
  }
}

export async function jumpToEvidence(date, timeRange = '', query = '') {
  const time = String(timeRange || '').split('-', 1)[0] || '';
  if (!date) {
    return;
  }
  await loadDate(date, time, query);
}
