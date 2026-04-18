// pipeline.js — 录音处理与任务流
import { state } from './state.js';
import { PIPELINE_KIND_LABELS, PIPELINE_STATUS_LABELS } from './tokens.js';
import { escapeHtml, renderEmptyState, renderEventList, showToast } from './utils.js';
import { fetchJson, postJson } from './api.js';
import { loadDate } from './daily.js';

let pipelineHooks = {
  rerenderSettingsOverlay: () => {},
  refreshContext: async () => {},
};

export function setPipelineHooks(hooks = {}) {
  pipelineHooks = { ...pipelineHooks, ...hooks };
}

export function formatPipelineKind(value) {
  return PIPELINE_KIND_LABELS[value] || value || '未知任务';
}

export function formatPipelineStatus(value) {
  return PIPELINE_STATUS_LABELS[value] || value || '未知状态';
}

export function formatPipelineStep(value) {
  if (!value) return '—';
  return PIPELINE_KIND_LABELS[value] || value;
}

export function renderPipelineJobDetail() {
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

export function getHomePipelineJob() {
  const activeJob = state.jobs.find((job) => ['queued', 'running', 'paused'].includes(job.status));
  if (activeJob) return activeJob;
  if (!state.homeJobFocusId) return null;
  return state.jobs.find((job) => job.job_id === state.homeJobFocusId) || null;
}

export function formatDurationSeconds(value) {
  const seconds = Number(value || 0);
  if (!Number.isFinite(seconds) || seconds <= 0) return '—';
  const minutes = Math.floor(seconds / 60);
  const remain = seconds % 60;
  if (minutes <= 0) return `${remain}秒`;
  return `${minutes}:${String(remain).padStart(2, '0')}`;
}

export function formatEtaSeconds(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return '预估中…';
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remain = seconds % 60;
  return `${minutes}:${String(remain).padStart(2, '0')}`;
}

export function formatStepVisual(step) {
  const status = step?.status || 'pending';
  if (status === 'done') return { icon: '✓', className: 'step-done' };
  if (status === 'running') return { icon: '<span class="spinner"></span>', className: 'step-running' };
  if (status === 'skipped') return { icon: '↷', className: 'step-skipped' };
  if (status === 'failed') return { icon: '!', className: 'step-failed' };
  return { icon: '○', className: 'step-pending' };
}

export function hasReadyTranscriptionProvider() {
  return Boolean(state.onboarding?.current_provider);
}

function getCurrentHomeProviderLabel() {
  const onboarding = state.onboarding || {};
  const items = (onboarding.choices?.local || []).concat(onboarding.choices?.cloud || []);
  const provider = onboarding.current_provider || '';
  return items.find((item) => item.name === provider)?.label || provider || '未设置';
}

function getPipelineSourceName(job) {
  return job?.source_file || (job?.target_date ? `${job.target_date} 的处理任务` : '这条录音');
}

function getPipelineFailureSummary(job) {
  if (!job) return '这次处理没跑通。';
  return job.error || job.steps?.find((step) => step.status === 'failed')?.result_summary || '这次处理没跑通。';
}

function getPipelineCompletionSummary(job) {
  if (!job) return '这条录音已经处理完成。';
  const terminalStep = [...(job.steps || [])].reverse().find((step) => step.result_summary);
  if (terminalStep?.result_summary) return terminalStep.result_summary;
  if (job.target_date) return `${job.target_date} 的日报已经可以查看。`;
  return `${getPipelineSourceName(job)}已经处理完成。`;
}

function renderHomeFileInput(disabled = false) {
  return `<input id="homeFileInput" type="file" ${disabled ? 'disabled' : ''} accept=".wav,.mp3,.m4a,.aac,.mp4,.mov,.flac,.ogg,.webm" style="display:none" onchange="onHomeFileInputChange(event)">`;
}

export function getIngestCardState(job = getHomePipelineJob()) {
  if (!hasReadyTranscriptionProvider()) return 'unconfigured';
  if (state.uploadingHomeFiles) return 'uploading';
  if (!job) return 'idle';
  if (['queued', 'running', 'paused'].includes(job.status)) return 'processing';
  if (['succeeded', 'partial'].includes(job.status)) return 'completed';
  if (['failed', 'cancelled', 'interrupted'].includes(job.status)) return 'failed';
  return 'idle';
}

function renderUnconfiguredIngestCard() {
  return `
    <div class="home-ingest-card ingest-card ingest-card--unconfigured">
      <div class="ingest-card-header">
        <div>
          <div class="home-ingest-title">开始之前，先选转写引擎</div>
          <div class="home-ingest-meta">OpenMy 需要一个转写引擎来把录音变成文字。本地免费或云端更快，6种可选。</div>
        </div>
        <div class="ingest-card-badge">未配置</div>
      </div>
      <div class="ingest-card-actions">
        <button class="action-btn primary" type="button" onclick="openSettings('transcription')">选择转写引擎</button>
      </div>
    </div>
  `;
}

function renderIdleIngestCard() {
  return `
    <div class="home-ingest-card ingest-card ingest-card--idle">
      <div class="ingest-card-header">
        <div>
          <div class="home-ingest-title">拖入录音，开始处理</div>
          <div class="home-ingest-meta">支持 .wav .mp3 .m4a 等格式，文件收进来后自动转写、清洗和整理。</div>
        </div>
        <div class="ingest-card-badge">已就绪</div>
      </div>
      <div class="dropzone-card" id="homeDropzone" ondragover="onHomeDropzoneDragOver(event)" ondragleave="onHomeDropzoneDragLeave(event)" ondrop="onHomeDropzoneDrop(event)" onclick="document.getElementById('homeFileInput').click()">
        <div class="dropzone-icon">＋</div>
        <div class="dropzone-title">拖入音频，或者点一下选文件</div>
        <div class="dropzone-subtitle">文件收进来后，才会开始转写、清洗、场景切分和蒸馏。</div>
        <button class="action-btn primary" type="button" onclick="event.stopPropagation();document.getElementById('homeFileInput').click()">选择音频文件</button>
        ${renderHomeFileInput()}
      </div>
      <div class="ingest-card-footer">当前引擎：${escapeHtml(getCurrentHomeProviderLabel())}</div>
    </div>
  `;
}

function renderUploadingIngestCard() {
  return `
    <div class="home-ingest-card ingest-card ingest-card--uploading">
      <div class="ingest-card-header">
        <div>
          <div class="home-ingest-title">正在上传音频...</div>
          <div class="home-ingest-meta">上传完成后会自动开始转写、清洗和整理。</div>
        </div>
        <div class="ingest-card-badge">上传中</div>
      </div>
      <div class="ingest-card-status">
        <span class="spinner" aria-hidden="true"></span>
        <div class="ingest-card-status-copy">音频正在进入 OpenMy，马上就会切到处理进度。</div>
      </div>
      <div class="ingest-card-actions">
        <button class="action-btn primary" type="button" disabled>正在上传音频...</button>
      </div>
      ${renderHomeFileInput(true)}
    </div>
  `;
}

function renderProcessingIngestCard(job) {
  const steps = job.steps || [];
  const recentLogs = [...(job.log_lines || [])].slice(-3).reverse();
  const isFinished = ['succeeded', 'partial'].includes(job.status);
  const isFailed = ['failed', 'cancelled', 'interrupted'].includes(job.status);
  const canPause = job.can_pause;
  const canResume = job.status === 'paused';
  const canSkip = job.can_skip;
  const sourceName = getPipelineSourceName(job);
  const summaryText = isFailed ? getPipelineFailureSummary(job) : '';
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

function renderCompletedIngestCard(job) {
  return `
    <div class="home-ingest-card ingest-card ingest-card--completed">
      <div class="ingest-card-header">
        <div>
          <div class="home-ingest-title">处理完成 ✓</div>
          <div class="home-ingest-meta">${escapeHtml(getPipelineSourceName(job))}${job.target_date ? ` · ${escapeHtml(job.target_date)}` : ''}</div>
        </div>
        <div class="ingest-card-badge">${escapeHtml(formatPipelineStatus(job.status))}</div>
      </div>
      <div class="ingest-card-summary">${escapeHtml(getPipelineCompletionSummary(job))}</div>
      <div class="ingest-card-footer">当前引擎：${escapeHtml(getCurrentHomeProviderLabel())}</div>
      <div class="progress-home-actions">
        ${job.target_date ? `<button class="action-btn primary" type="button" onclick="loadDate('${escapeHtml(job.target_date)}')">查看日报</button>` : ''}
        <button class="action-btn" type="button" onclick="clearHomeJobFocus()">收起结果</button>
      </div>
    </div>
  `;
}

function renderFailedIngestCard(job) {
  return `
    <div class="home-ingest-card ingest-card ingest-card--failed">
      <div class="ingest-card-header">
        <div>
          <div class="home-ingest-title">这次处理没有完成</div>
          <div class="home-ingest-meta">${escapeHtml(getPipelineSourceName(job))}${job?.target_date ? ` · ${escapeHtml(job.target_date)}` : ''}</div>
        </div>
        <div class="ingest-card-badge">${escapeHtml(formatPipelineStatus(job?.status || 'failed'))}</div>
      </div>
      <div class="progress-home-failure">${escapeHtml(getPipelineFailureSummary(job))}</div>
      <div class="ingest-card-footer">重试会重新选择音频文件，再新开一条处理任务。</div>
      <div class="progress-home-actions">
        <button class="action-btn primary" type="button" onclick="document.getElementById('homeFileInput').click()">重试</button>
        <button class="action-btn" type="button" onclick="openSettings('transcription')">去选转写引擎</button>
        <button class="action-btn" type="button" onclick="clearHomeJobFocus()">收起结果</button>
      </div>
      ${renderHomeFileInput()}
    </div>
  `;
}

export function renderIngestCard(job = getHomePipelineJob()) {
  const cardState = getIngestCardState(job);
  switch (cardState) {
    case 'unconfigured':
      return renderUnconfiguredIngestCard();
    case 'idle':
      return renderIdleIngestCard();
    case 'uploading':
      return renderUploadingIngestCard();
    case 'processing':
      return renderProcessingIngestCard(job);
    case 'completed':
      return renderCompletedIngestCard(job);
    case 'failed':
      return renderFailedIngestCard(job);
    default:
      return renderIdleIngestCard();
  }
}

export function renderHomeDropZone() {
  const cardState = getIngestCardState(null);
  if (cardState === 'unconfigured') return renderUnconfiguredIngestCard();
  if (cardState === 'uploading') return renderUploadingIngestCard();
  return renderIdleIngestCard();
}

export function renderHomePipelineSlotCard(job) {
  return renderIngestCard(job);
}

export function rerenderHomePipelineSlot() {
  if (state.route !== 'home') return;
  const slot = document.getElementById('homePipelineSlot');
  if (!slot) return;
  slot.innerHTML = renderIngestCard(getHomePipelineJob());
}

export function clearHomeJobFocus() {
  state.homeJobFocusId = '';
  rerenderHomePipelineSlot();
}

export async function createPipelineJob(kind) {
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

export async function uploadHomeAudioFiles(fileList) {
  if (!hasReadyTranscriptionProvider()) {
    showToast('先选转写引擎，再上传音频。');
    globalThis.openSettings?.('transcription');
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

export function onHomeFileInputChange(event) {
  uploadHomeAudioFiles(event.target.files);
}

export function onHomeDropzoneDragOver(event) {
  event.preventDefault();
  event.currentTarget?.classList.add('dragover');
}

export function onHomeDropzoneDragLeave(event) {
  event.preventDefault();
  event.currentTarget?.classList.remove('dragover');
}

export function onHomeDropzoneDrop(event) {
  event.preventDefault();
  event.currentTarget?.classList.remove('dragover');
  uploadHomeAudioFiles(event.dataTransfer?.files || []);
}

export async function runPipelineAction(jobId, action) {
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

export async function refreshPipelineJobs() {
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

export async function loadPipelineJobDetail(jobId, rerender = true) {
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

  if (rerender) pipelineHooks.rerenderSettingsOverlay();
  const detailNode = document.getElementById('pipelineJobDetail');
  if (detailNode) {
    detailNode.innerHTML = renderPipelineJobDetail();
  }
}

export async function handleJobCompletion(job) {
  if (job.kind === 'context') {
    await pipelineHooks.refreshContext();
    showToast('上下文已刷新');
    return;
  }
  if (job.target_date && job.target_date === state.currentDate) {
    await loadDate(state.currentDate);
    showToast(`${formatPipelineKind(job.kind)}已完成，并已刷新当前日期`);
  }
}

// === Settings Page ===
