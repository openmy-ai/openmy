// settings.js — 设置和首配
import { state } from './state.js';
import { fetchJson, postJson } from './api.js';
import { escapeHtml, renderEventList, showToast } from './utils.js';
import { optionMarkup } from './daily.js';
import { renderContextQueryResult } from './context.js';
import { createPipelineJob, formatPipelineKind, formatPipelineStatus, loadPipelineJobDetail, refreshPipelineJobs, renderPipelineJobDetail, rerenderHomePipelineSlot } from './pipeline.js';
import { renderHomePage } from './home.js';
import { getEngineDisplayName } from './context.js';

export function rerenderSettingsOverlay() {
  const overlay = document.getElementById('settingsOverlay');
  if (!overlay?.classList.contains('active')) return;
  const content = document.getElementById('settingsContent');
  if (!content) return;
  content.innerHTML = renderSettingsHTML();
  applySettingsUI();
}


export async function loadOnboarding() {
  state.onboarding = await fetchJson('/api/onboarding', {});
  if (state.route === 'home') {
    renderHomePage();
  }
}

export async function loadScreenContextSettings() {
  state.screenSettings = await fetchJson('/api/settings/screen-context', {
    enabled: true,
    participation_mode: 'summary_only',
    exclude_apps: [],
    exclude_domains: [],
    exclude_window_keywords: [],
  });
  rerenderSettingsOverlay();
}


export function renderOnboardingCard() {
  return renderHomeOnboardingCard();
}

export function getTranscriptionIcon(provider) {
  return `/static/icons/${provider}.svg`;
}

export function renderHomeOnboardingCard() {
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

export function renderTranscriptionSettings() {
  const onboarding = state.onboarding || {};
  const localChoices = onboarding.choices?.local || [];
  const cloudChoices = onboarding.choices?.cloud || [];
  const selected = state.selectedTranscriptionProvider || onboarding.current_provider || onboarding.recommended_provider || '';
  const currentLabel = currentProviderLabel();

  // Determine which lane is active based on current selection
  const isCloudSelected = cloudChoices.some((c) => c.name === selected);
  const activeLane = state.transcriptionLane || (isCloudSelected ? 'cloud' : 'local');

  const activeChoices = activeLane === 'cloud' ? cloudChoices : localChoices;

  const renderChoice = (item) => {
    const isActive = selected === item.name;
    const isRecommended = item.is_recommended;
    return `
    <button class="transcription-option ${isActive ? 'active' : ''}" type="button" onclick="selectTranscriptionOption('${escapeHtml(item.name || '')}')">
      <div>
        <div class="transcription-option-title">${escapeHtml(getEngineDisplayName(item.name))}${isRecommended ? ' <span class="transcription-badge-rec">推荐</span>' : ''}</div>
        <div class="transcription-option-desc">${escapeHtml(item.description || '')}</div>
      </div>
      <div class="transcription-option-check">${isActive ? '✓' : ''}</div>
    </button>
  `;
  };

  return `
    <div class="settings-section" id="transcriptionSettingsSection">
      <div class="settings-section-title">转写模型</div>

      <div class="transcription-lane-picker">
        <button class="transcription-lane ${activeLane === 'local' ? 'active' : ''}" type="button" onclick="setTranscriptionLane('local')">
          <div class="transcription-lane-icon">🖥</div>
          <div class="transcription-lane-title">本地引擎</div>
          <div class="transcription-lane-desc">免费，不需要密钥</div>
        </button>
        <button class="transcription-lane ${activeLane === 'cloud' ? 'active' : ''}" type="button" onclick="setTranscriptionLane('cloud')">
          <div class="transcription-lane-icon">☁️</div>
          <div class="transcription-lane-title">云端引擎</div>
          <div class="transcription-lane-desc">更快更准，需要 API Key</div>
        </button>
      </div>

      <div class="transcription-choices">
        ${activeChoices.map(renderChoice).join('')}
      </div>

      <div class="transcription-actions">
        <div class="transcription-current">当前：${escapeHtml(currentLabel || '还没选')}</div>
        <button class="action-btn primary" type="button" onclick="confirmTranscriptionProvider()">确认</button>
      </div>
    </div>
  `;
}

export function currentProviderLabel() {
  const onboarding = state.onboarding || {};
  const items = (onboarding.choices?.local || []).concat(onboarding.choices?.cloud || []);
  const provider = onboarding.current_provider || '';
  return items.find((item) => item.name === provider)?.label || provider;
}

export function selectTranscriptionOption(provider) {
  state.selectedTranscriptionProvider = provider;
  rerenderSettingsOverlay();
}

export function setTranscriptionLane(lane) {
  state.transcriptionLane = lane;
  rerenderSettingsOverlay();
}

export async function confirmTranscriptionProvider() {
  const provider = state.selectedTranscriptionProvider || state.onboarding?.recommended_provider || '';
  if (!provider) return;
  await selectOnboardingProvider(provider, { closeSettings: true });
}

export async function selectOnboardingProvider(provider, options = {}) {
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

export function splitSettingList(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export async function updateScreenContextMode(mode) {
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

export async function saveScreenContextExclusions() {
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


export function openSettings() {
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

export function closeSettingsOverlay(e) {
  if (e) e.stopPropagation();
  const overlay = document.getElementById('settingsOverlay');
  overlay.classList.remove('active');
  document.getElementById('settingsBtn')?.classList.remove('active');
  document.getElementById('transcriptionBtn')?.classList.remove('active');
}

export function renderSettingsHTML() {
  return `
  <div class="settings-page" style="padding:0">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2 style="margin:0;font-size:20px;">设置</h2>
      <button class="action-btn" type="button" onclick="closeSettingsOverlay()" style="padding:6px 12px">✕ 关闭</button>
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

export function applySettings() {
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

export function saveSetting(key, value) {
  localStorage.setItem('openmy-' + key, value);
  applySettings();
  applySettingsUI();
}

export function applySettingsUI() {
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
