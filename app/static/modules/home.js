// home.js — 首页
import { state } from './state.js';
import { escapeHtml, fmtNum, truncateSummary } from './utils.js';
import { buildDailySummary, deriveLoopItemsFromDates, deriveProjectItemsFromDates, formatFriendlyDate, getGreetingByHour, getVisibleDates } from './dates.js';
import { renderIngestCard } from './pipeline.js';
import { renderWikiHome } from './context.js';
import { closeSidebar } from './sidebar.js';
import { getProfileEmoji, getProfileInitial, getProfileName } from './profile.js';
import { setRoute } from './router.js';

export function renderChipList(items, emptyText) {
  if (!items.length) {
    return `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
  }
  return `<div class="summary-chip-list">${items.map((item) => `<span class="summary-chip">${escapeHtml(item)}</span>`).join('')}</div>`;
}

function getProjectAvatarHue(label = '') {
  return Array.from(label).reduce((sum, char) => sum + char.charCodeAt(0), 0) % 360;
}

function getProjectAvatarInitial(label = '') {
  return escapeHtml((label || '项').trim().slice(0, 1) || '项');
}


export function renderHomePage() {
  closeSidebar();
  setRoute('home');
  state.currentDate = '';

  // New user: no engine configured → auto-enter wizard
  const onboarding = state.onboarding || {};
  const hasProvider = Boolean(onboarding.current_provider);
  if (!hasProvider || state.showWikiHome) {
    renderWikiHome();
    return;
  }

  const visibleDates = getVisibleDates();
  if (visibleDates.length) {
    renderRecentSummaryHome(visibleDates);
  } else {
    renderWikiHome();
  }
}

export function getOnboardingSteps() {
  const onboarding = state.onboarding || {};
  const hasProvider = Boolean(onboarding.current_provider);
  const hasRecordings = (state.allDates || []).length > 0;
  const hasCorrections = (state.corrections || []).length > 0;
  return [
    { id: 'engine', title: '选转写引擎', desc: '6种引擎可选，本地或云端', done: hasProvider, action: "openSettings('transcription')" },
    { id: 'record', title: '第一段录音', desc: '拖入音频或 CLI 运行 quick-start', done: hasRecordings, action: hasProvider ? "document.getElementById('homeFileInput')?.click()" : "openSettings('transcription')" },
    { id: 'correct', title: '体验纠错', desc: '在日报里选中文字，试试纠错', done: hasCorrections, action: "openCorrectionPopover('', 0, 0, '先从日报里选中一句话，抽屉就会带着原句打开。')" },
  ];
}

export function renderOnboardingTracker() {
  const steps = getOnboardingSteps();
  const allDone = steps.every((s) => s.done);
  const firstUndone = steps.findIndex((s) => !s.done);
  return `
    <div class="onboarding-tracker ${allDone ? 'all-done' : ''}">
      ${steps.map((step, i) => {
        const cls = step.done ? 'is-done' : (i === firstUndone ? 'is-current' : '');
        return `
          <button class="onboarding-step ${cls}" type="button" onclick="${step.action}">
            <span class="onboarding-step-num">${step.done ? '✓' : i + 1}</span>
            <div class="onboarding-step-title">${escapeHtml(step.title)}</div>
            <div class="onboarding-step-desc">${escapeHtml(step.desc)}</div>
          </button>
        `;
      }).join('')}
    </div>
  `;
}

export function renderRecentSummaryHome(visibleDates) {
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
    meta: item.current_goal || item.status || '活跃中',
    nextActions: (item.next_actions || []).slice(0, 2),
  }));
  const fallbackProjectItems = deriveProjectItemsFromDates(recentDates, 4);
  const loopItems = deriveLoopItemsFromDates(recentDates, 4);
  const correctionCount = (state.corrections || []).length;

  const greeting = getGreetingByHour();
  const profileName = getProfileName();
  const profileEmoji = getProfileEmoji();
  const welcomeText = profileName ? `${greeting}，${escapeHtml(profileName)}` : `${greeting}！今天是 ${escapeHtml(monthDay)}`;

  const onboardingSteps = getOnboardingSteps();
  const allOnboardingDone = onboardingSteps.every((s) => s.done);

  main.innerHTML = `
    <div class="home-page">
      <div class="welcome-hero">
        <div class="profile-greeting">
          <button class="profile-edit-trigger" type="button" onclick="openProfileModal()" title="编辑个人信息">
            <div class="profile-avatar">${profileName ? escapeHtml(getProfileInitial()) : profileEmoji}</div>
          </button>
          <div>
            <div class="profile-name-row">
              <div class="welcome-title">${welcomeText}</div>
              <span class="profile-edit-hint">点头像改名字</span>
            </div>
            <div class="welcome-subtitle">这是你最近 7 天的上下文概览</div>
          </div>
        </div>
      </div>

      ${!allOnboardingDone ? renderOnboardingTracker() : ''}

      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-card-value ${activeDays === 0 ? 'is-zero' : ''}">${activeDays}</div>
          <div class="stat-card-label">活跃天数</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-value ${totalSegments === 0 ? 'is-zero' : ''}">${totalSegments}</div>
          <div class="stat-card-label">录音段数</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-value ${totalWords === 0 ? 'is-zero' : ''}">${fmtNum(totalWords)}</div>
          <div class="stat-card-label">总字数</div>
        </div>
      </div>

      <div class="home-card home-card-grid--full" onclick="${todayItem ? `loadDate('${escapeHtml(todayItem.date)}')` : ''}" style="margin-bottom:16px;cursor:pointer">
        <div class="home-card-header">
          <span class="home-card-title"><span class="card-icon">📋</span>今日摘要</span>
          ${todayItem ? `<span class="home-card-badge">${todayItem.segments || 0}条记录</span>` : ''}
        </div>
        <div class="home-card-body">
          ${todaySummary ? escapeHtml(todaySummary) : '<span class="text-muted">今天还没有录音</span>'}
        </div>
      </div>

      <div class="home-card-grid home-card-grid--dense">
        <div class="home-card">
          <div class="home-card-header">
            <span class="home-card-title"><span class="card-icon">🎙️</span>最近录音</span>
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
            <span class="home-card-title"><span class="card-icon">✏️</span>待纠错</span>
            <span class="home-card-badge">${correctionCount}</span>
          </div>
          <div class="home-card-body">
            ${correctionCount ? `词典里已经收了 ${correctionCount} 条纠错，点开可以继续加。` : '现在还没有纠错记录。你可以在日报里选中文字，右侧会滑出纠错抽屉。'}
          </div>
          <div class="home-card-footer">
            <button class="action-btn" type="button" onclick="openCorrectionPopover('', 0, 0, '先从日报里选中一句话，抽屉就会带着原句打开。')">打开纠错抽屉</button>
          </div>
        </div>
      </div>

      ${(projectItems.length || fallbackProjectItems.length) ? `
      <div class="home-card" style="margin-top:16px">
        <div class="home-card-header">
          <span class="home-card-title"><span class="card-icon">🚀</span>活跃项目</span>
          <span class="home-card-badge">${projectItems.length || fallbackProjectItems.length}</span>
        </div>
        <div class="home-card-list">
          ${(projectItems.length ? projectItems : fallbackProjectItems).map((item) => {
            const label = item.label || '';
            return `
            <div class="home-card-list-item home-card-list-item--project">
              <span class="project-avatar" style="background:hsl(${getProjectAvatarHue(label)}, 60%, 50%)">${getProjectAvatarInitial(label)}</span>
              <div class="project-copy">
                <div class="home-card-list-title">${escapeHtml(label)}</div>
                <div class="home-card-list-meta">${escapeHtml(item.meta || '')}</div>
                ${item.nextActions?.length ? `<div class="home-card-list-actions">${item.nextActions.map((action) => `<span class="action-chip">${escapeHtml(action)}</span>`).join('')}</div>` : ''}
              </div>
            </div>
          `;
          }).join('')}
        </div>
      </div>
      ` : ''}

      ${allOnboardingDone ? `<div id="homePipelineSlot">${renderIngestCard()}</div>` : ''}
    </div>
  `;
}
