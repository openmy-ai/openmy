import { state } from './state.js';
import { escapeHtml, plainText, showToast } from './utils.js';
import {
  ensureSceneAudio,
  getSceneByTime,
  getSegmentSceneTarget,
  prepareScenePlayback,
  setScenePlaybackRate,
  stopScenePlayback,
  syncScenePlaybackUi,
} from './playback.js';
import { bindWaveformSeek, fetchWaveformData, formatWaveformTime, renderWaveform } from './waveform.js';
import { closeSelectionPopover, openCorrectionPopover } from './corrections.js';

let waveformCleanup = null;
let waveformRequestId = 0;
let subtitleAudioListenerBound = false;
let playbackEventListenerBound = false;
const waveformState = {
  canvas: null,
  timeDisplay: null,
  loadingEl: null,
  waveform: null,
  duration: 0,
  speechSegments: [],
  audioUrl: '',
};

function resetWaveformState() {
  if (typeof waveformCleanup === 'function') {
    waveformCleanup();
  }
  waveformCleanup = null;
  waveformState.canvas = null;
  waveformState.timeDisplay = null;
  waveformState.loadingEl = null;
  waveformState.waveform = null;
  waveformState.duration = 0;
  waveformState.speechSegments = [];
  waveformState.audioUrl = '';
}

function getAnchor(anchor = state.correctionAnchor) {
  return anchor && typeof anchor === 'object' ? anchor : null;
}

function splitSentences(rawText = '') {
  const text = plainText(rawText);
  if (!text) return [];
  const normalized = text.replace(/\r/g, '').replace(/\n+/g, '\n').trim();
  const matches = normalized.match(/[^。！？；\n]+[。！？；]?/g) || [];
  const sentences = matches.map((item) => item.trim()).filter(Boolean);
  return sentences.length ? sentences : [normalized];
}

function findMatchedSentenceIndex(sentences, selectedText = '') {
  const needle = plainText(selectedText);
  if (!needle) return 0;
  const exact = sentences.findIndex((item) => item.includes(needle));
  if (exact >= 0) return exact;
  const compactNeedle = needle.replace(/\s+/g, '');
  return Math.max(
    0,
    sentences.findIndex((item) => item.replace(/\s+/g, '').includes(compactNeedle)),
  );
}

function buildSentenceBuckets(sentences, target, selectedText, speechSegments = [], realDuration = 0) {
  if (!sentences.length) return [];
  const matchedIndex = Math.max(0, findMatchedSentenceIndex(sentences, selectedText));
  const hasTiming = speechSegments.length > 0 && realDuration > 0;
  return sentences.map((text, index) => {
    let startTime = 0;
    let endTime = 0;
    if (hasTiming) {
      const segIndex = Math.min(index, speechSegments.length - 1);
      const seg = speechSegments[segIndex];
      if (seg) {
        startTime = Number(seg.start || 0);
        endTime = Number(seg.end || seg.start || 0);
      }
    } else if (realDuration > 0) {
      const slice = realDuration / sentences.length;
      startTime = index * slice;
      endTime = startTime + slice;
    } else if (target?.duration > 0) {
      const slice = target.duration / sentences.length;
      startTime = index * slice;
      endTime = startTime + slice;
    }

    return {
      index,
      label: `句 ${String(index + 1).padStart(2, '0')}`,
      text,
      matched: index === matchedIndex,
      startTime: Math.round(startTime * 10) / 10,
      endTime: Math.round(endTime * 10) / 10,
      hasTiming,
    };
  });
}

function buildReviewModel(anchor = getAnchor()) {
  if (!anchor) return null;
  const scene = anchor.segmentTime ? getSceneByTime(anchor.segmentTime) : null;
  const sceneTarget = anchor.segmentTime ? getSegmentSceneTarget(anchor.segmentTime) : null;
  const sourceText = plainText(
    scene?.transcription_evidence?.map((item) => item?.text || '').filter(Boolean).join(' ')
      || scene?.text
      || anchor.contextText
      || anchor.selectedText
      || '',
  );
  const matchedSentence = plainText(anchor.matchedSentence || '');
  const speechSegments = Array.isArray(scene?.audio_ref?.speech_segments)
    ? scene.audio_ref.speech_segments
    : (Array.isArray(sceneTarget?.audioRef?.speech_segments) ? sceneTarget.audioRef.speech_segments : []);
  const realDuration = Math.max(0, Number(sceneTarget?.audioRef?.duration_seconds || 0));
  const target = sceneTarget?.audioRef
    ? {
      ...sceneTarget,
      key: `${sceneTarget.key}::subtitle-review`,
      start: 0,
      end: realDuration > 0 ? realDuration : sceneTarget.end,
      duration: realDuration > 0 ? realDuration : sceneTarget.duration,
    }
    : sceneTarget;
  const buckets = buildSentenceBuckets(
    splitSentences(sourceText),
    target,
    matchedSentence || anchor.selectedText || '',
    speechSegments,
    realDuration,
  );
  const fallbackIndex = Math.max(0, buckets.findIndex((item) => item.matched));
  const nextIndex = Number.isFinite(state.subtitleReview.selectedSentenceIndex)
    ? Math.max(0, Math.min(Math.max(buckets.length - 1, 0), state.subtitleReview.selectedSentenceIndex))
    : fallbackIndex;

  return {
    anchor,
    scene,
    target,
    sourceText,
    matchedSentence,
    hasExactMatch: Boolean(matchedSentence),
    speechSegments,
    realDuration,
    sentences: buckets,
    currentIndex: buckets.length ? nextIndex : 0,
    hasAudio: Boolean(target?.audioRef?.chunk_id && target?.url),
  };
}

function getCurrentSentenceLabel(model) {
  if (!model?.sentences?.length) return '暂无句子';
  return `第 ${model.currentIndex + 1} 句 / 共 ${model.sentences.length} 句`;
}

function getCurrentSentence(model) {
  return model?.sentences?.[model.currentIndex] || null;
}

function renderSentenceList(model) {
  if (!model.sentences.length) {
    return '<div class="subtitle-empty">这段现在还没有可回看的句子。</div>';
  }
  return model.sentences.map((item) => `
    <button
      class="subtitle-sentence ${item.index === model.currentIndex ? 'is-active' : ''} ${item.matched ? 'is-matched' : ''}"
      type="button"
      data-subtitle-index="${item.index}"
      onclick="focusSubtitleSentence(${item.index})"
    >
      <span class="subtitle-sentence-label">${escapeHtml(item.label)}</span>
      <span class="subtitle-sentence-text">${escapeHtml(item.text)}</span>
    </button>
  `).join('');
}

function syncReviewStatus(model = buildReviewModel()) {
  if (!state.subtitleReview.open || !model) return;
  const sentenceLabel = document.getElementById('subtitleReviewSentenceLabel');
  const playButton = document.getElementById('subtitleReviewPlayButton');
  const hint = document.getElementById('subtitleReviewHint');
  const active = state.playback.activeKey === model.target?.key;
  const playing = active && state.playback.status === 'playing';

  if (sentenceLabel) {
    sentenceLabel.textContent = getCurrentSentenceLabel(model);
  }
  if (playButton) {
    playButton.textContent = playing ? '暂停回听' : '回听整段录音';
  }
  if (hint) {
    hint.textContent = model.hasAudio
      ? '点击下方句子可以浏览全文'
      : '这段录音现在不可用，但文字来源还能看。';
  }
}

export function updateSentenceHighlight(index) {
  const items = Array.from(document.querySelectorAll('.subtitle-sentence'));
  if (!items.length) return;
  items.forEach((item, itemIndex) => {
    item.classList.toggle('is-active', itemIndex === index);
  });
  const activeEl = items[index];
  if (activeEl) {
    activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

export function updateWaveformProgress(time) {
  if (!waveformState.canvas || !waveformState.waveform || !waveformState.duration) return;
  renderWaveform(
    waveformState.canvas,
    waveformState.waveform,
    waveformState.duration,
    waveformState.speechSegments,
    time,
  );
  if (waveformState.timeDisplay) {
    waveformState.timeDisplay.textContent = `${formatWaveformTime(time)} / ${formatWaveformTime(waveformState.duration)}`;
  }
}

function getRelativePlaybackTime(model) {
  if (!model?.target) return 0;
  if (state.playback.activeKey === model.target.key) {
    return Math.max(0, Number(state.playback.progress || 0));
  }
  const currentSentence = getCurrentSentence(model);
  return Math.max(0, Number(currentSentence?.startTime || 0));
}

function hydrateWaveform(model) {
  resetWaveformState();
  const canvas = document.getElementById('subtitle-waveform-canvas');
  const timeDisplay = document.getElementById('subtitle-waveform-time');
  const loadingEl = document.getElementById('subtitle-waveform-loading');
  if (!canvas || !model?.hasAudio || !model.target?.url) {
    if (loadingEl) {
      loadingEl.textContent = '当前没有可回听的录音。';
      loadingEl.style.display = 'grid';
    }
    return;
  }

  waveformState.canvas = canvas;
  waveformState.timeDisplay = timeDisplay;
  waveformState.loadingEl = loadingEl;
  waveformState.audioUrl = model.target.url;
  const requestId = waveformRequestId + 1;
  waveformRequestId = requestId;

  fetchWaveformData(model.target.url)
    .then(({ waveform, duration }) => {
      if (requestId !== waveformRequestId || waveformState.audioUrl !== model.target.url) return;
      waveformState.waveform = waveform;
      waveformState.duration = duration;
      waveformState.speechSegments = model.speechSegments;
      if (waveformState.loadingEl) {
        waveformState.loadingEl.style.display = 'none';
      }
      updateWaveformProgress(getRelativePlaybackTime(model));
      waveformCleanup = bindWaveformSeek(canvas, duration, async (time) => {
        await seekSubtitleReview(time);
      });
    })
    .catch(() => {
      if (requestId !== waveformRequestId) return;
      if (waveformState.loadingEl) {
        waveformState.loadingEl.textContent = '波形加载失败';
        waveformState.loadingEl.style.display = 'grid';
      }
    });
}

function bindSubtitleReviewListeners() {
  if (!subtitleAudioListenerBound) {
    ensureSceneAudio().addEventListener('timeupdate', () => {
      if (!state.subtitleReview.open) return;
      const model = buildReviewModel();
      if (!model?.sentences?.length) return;
      const audio = ensureSceneAudio();
      const relativeTime = Math.max(0, Number(audio.currentTime || 0) - Number(model.target?.start || 0));
      const matchedBucket = model.sentences.find(
        (item) => item.hasTiming && relativeTime >= item.startTime && relativeTime < item.endTime,
      );
      if (matchedBucket && matchedBucket.index !== state.subtitleReview.selectedSentenceIndex) {
        state.subtitleReview.selectedSentenceIndex = matchedBucket.index;
        updateSentenceHighlight(matchedBucket.index);
        syncReviewStatus(buildReviewModel());
      }
      updateWaveformProgress(relativeTime);
    });
    subtitleAudioListenerBound = true;
  }

  if (!playbackEventListenerBound) {
    window.addEventListener('openmy:playback-change', () => {
      if (!state.subtitleReview.open) return;
      const model = buildReviewModel();
      if (!model) return;
      syncReviewStatus(model);
      updateWaveformProgress(getRelativePlaybackTime(model));
    });
    playbackEventListenerBound = true;
  }
}

export function renderSubtitleReview() {
  const overlay = document.getElementById('subtitleReviewOverlay');
  const content = document.getElementById('subtitleReviewContent');
  if (!overlay || !content || !state.subtitleReview.open) return;

  const model = buildReviewModel();
  if (!model) {
    content.innerHTML = '<div class="subtitle-empty">先在日报里选一段字，再来看来源。</div>';
    return;
  }

  const currentSentence = getCurrentSentence(model);
  const matchedSentence = model.hasExactMatch
    ? model.matchedSentence
    : (currentSentence?.text || model.anchor.selectedText || model.sourceText || '这段没有匹配到更精确的原句。');
  const currentRate = String(state.playback.rate || 1);
  const disabledAttr = model.hasAudio ? '' : 'disabled';

  content.innerHTML = `
    <div class="subtitle-review-shell">
      <div class="subtitle-review-card">
        <div class="subtitle-section-label">你刚选中的字</div>
        <div class="subtitle-selection">${escapeHtml(model.anchor.selectedText || '还没有选中文字')}</div>
      </div>

      <div class="subtitle-review-card">
        <div class="subtitle-section-label">命中原句</div>
        <div class="subtitle-context ${model.hasExactMatch ? 'is-exact' : ''}">${escapeHtml(matchedSentence)}</div>
      </div>

      <div class="subtitle-review-card">
        <div class="subtitle-review-topline">
          <div>
            <div class="subtitle-section-label">字幕回看</div>
            <div class="subtitle-progress-copy" id="subtitleReviewSentenceLabel">${escapeHtml(getCurrentSentenceLabel(model))}</div>
          </div>
          <div class="subtitle-review-controls">
            <select class="subtitle-rate-select" onchange="setSubtitleReviewRate(this.value)" ${disabledAttr}>
              <option value="0.5" ${currentRate === '0.5' ? 'selected' : ''}>0.5x</option>
              <option value="1" ${currentRate === '1' ? 'selected' : ''}>1x</option>
              <option value="1.5" ${currentRate === '1.5' ? 'selected' : ''}>1.5x</option>
              <option value="2" ${currentRate === '2' ? 'selected' : ''}>2x</option>
            </select>
            <button class="subtitle-play-btn" id="subtitleReviewPlayButton" type="button" onclick="toggleSubtitleReviewPlayback()" ${disabledAttr}>
              回听整段录音
            </button>
          </div>
        </div>

        <div class="waveform-container" id="subtitle-waveform-container">
          <canvas class="waveform-canvas" id="subtitle-waveform-canvas"></canvas>
          <span class="waveform-time" id="subtitle-waveform-time">0:00 / 0:00</span>
          <span class="waveform-loading" id="subtitle-waveform-loading">加载波形中...</span>
        </div>

        <div class="subtitle-progress-hint" id="subtitleReviewHint">点击下方句子可以浏览全文</div>

        <div class="subtitle-sentence-list">
          ${renderSentenceList(model)}
        </div>
      </div>
    </div>
  `;

  syncReviewStatus(model);
  updateSentenceHighlight(model.currentIndex);
  hydrateWaveform(model);
}

export function openSubtitleReview(anchor = getAnchor()) {
  if (!anchor) {
    showToast('先在日报里选一段字。');
    return;
  }
  closeSelectionPopover();
  bindSubtitleReviewListeners();
  state.correctionAnchor = anchor;
  state.subtitleReview.open = true;
  const previewModel = buildReviewModel(anchor);
  state.subtitleReview.selectedSentenceIndex = Math.max(
    0,
    previewModel?.sentences?.findIndex((item) => item.matched) ?? 0,
  );
  document.getElementById('subtitleReviewOverlay')?.classList.add('active');
  document.body.style.overflow = 'hidden';
  renderSubtitleReview();
}

export function closeSubtitleReview() {
  stopScenePlayback();
  state.subtitleReview.open = false;
  state.subtitleReview.selectedSentenceIndex = 0;
  document.getElementById('subtitleReviewOverlay')?.classList.remove('active');
  document.body.style.overflow = '';
  resetWaveformState();
}

export async function focusSubtitleSentence(index) {
  const model = buildReviewModel();
  if (!model) return;

  const nextIndex = Math.max(0, Math.min(model.sentences.length - 1, Number(index || 0)));
  state.subtitleReview.selectedSentenceIndex = nextIndex;
  const bucket = model.sentences[nextIndex];

  if (bucket?.hasTiming && model.hasAudio) {
    try {
      const audio = ensureSceneAudio();
      await prepareScenePlayback(model.target);
      audio.currentTime = model.target.start + bucket.startTime;
      state.playback.progress = bucket.startTime;
      await audio.play();
    } catch (error) {
      // 播放失败时保留当前高亮，不阻断查看文本
    }
  }

  renderSubtitleReview();
  updateSentenceHighlight(nextIndex);
}

export async function toggleSubtitleReviewPlayback() {
  const model = buildReviewModel();
  if (!model?.hasAudio) {
    showToast('这段录音现在不可用。');
    return;
  }

  const audio = ensureSceneAudio();
  const active = state.playback.activeKey === model.target.key;
  const playing = active && !audio.paused;
  if (playing) {
    audio.pause();
    syncReviewStatus(model);
    return;
  }

  try {
    await prepareScenePlayback(model.target);
    const currentSentence = getCurrentSentence(model);
    const nextTime = currentSentence?.hasTiming ? currentSentence.startTime : 0;
    audio.currentTime = model.target.start + nextTime;
    state.playback.progress = nextTime;
    await audio.play();
    syncScenePlaybackUi();
    syncReviewStatus(buildReviewModel());
  } catch (error) {
    stopScenePlayback();
    syncScenePlaybackUi();
    showToast('这段录音暂时打不开。');
  }
}

export async function seekSubtitleReview(rawValue) {
  const model = buildReviewModel();
  if (!model?.hasAudio) return;

  try {
    const audio = ensureSceneAudio();
    if (state.playback.activeKey !== model.target.key) {
      await prepareScenePlayback(model.target);
      audio.pause();
    }
    const nextOffset = Math.max(0, Math.min(waveformState.duration || model.realDuration || model.target.duration, Number(rawValue || 0)));
    audio.currentTime = model.target.start + nextOffset;
    state.playback.progress = nextOffset;
    state.playback.status = audio.paused ? 'paused' : 'playing';
    syncScenePlaybackUi();

    const nextBucket = model.sentences.find(
      (item) => item.hasTiming && nextOffset >= item.startTime && nextOffset < item.endTime,
    );
    if (nextBucket) {
      state.subtitleReview.selectedSentenceIndex = nextBucket.index;
      updateSentenceHighlight(nextBucket.index);
      syncReviewStatus(buildReviewModel());
    } else {
      updateWaveformProgress(nextOffset);
    }
  } catch (error) {
    stopScenePlayback();
    syncScenePlaybackUi();
    showToast('这段录音暂时打不开。');
  }
}

export function setSubtitleReviewRate(rawValue) {
  setScenePlaybackRate('', rawValue);
  syncReviewStatus(buildReviewModel());
}

export function jumpToCorrectionFromReview() {
  const model = buildReviewModel();
  if (!model) return;
  const contextText = model.matchedSentence || model.sourceText || model.anchor.contextText || model.anchor.selectedText;
  closeSubtitleReview();
  openCorrectionPopover(model.anchor.selectedText, 0, 0, contextText);
}
