// playback.js — 原声回放
import { state, sharedSceneAudio, setSharedSceneAudio } from './state.js';
import { escapeHtml, showToast } from './utils.js';
import { formatPlaybackClock } from './dates.js';

function emitPlaybackChange() {
  window.dispatchEvent(new CustomEvent('openmy:playback-change', {
    detail: {
      activeKey: state.playback.activeKey,
      activeChunkId: state.playback.activeChunkId,
      status: state.playback.status,
      progress: state.playback.progress,
      duration: state.playback.duration,
      rate: state.playback.rate,
      sceneStart: state.playback.sceneStart,
      sceneEnd: state.playback.sceneEnd,
    },
  }));
}

export function getSceneByTime(time) {
  const scenes = state.currentData?.scenes?.scenes || [];
  return scenes.find((item) => item.time_start === time) || null;
}

export function getSegmentSceneTarget(segmentTime) {
  const scene = getSceneByTime(segmentTime);
  if (!scene) return null;
  const audioRef = scene.audio_ref || null;
  if (!audioRef?.chunk_id) {
    return {
      key: segmentTime,
      scene,
      audioRef: null,
      start: 0,
      end: 0,
      duration: 0,
      url: '',
    };
  }

  const start = Math.max(0, Number(audioRef.offset_start || 0));
  const rawEnd = Math.max(start, Number(audioRef.offset_end || start));
  const realDuration = Math.max(0, Number(audioRef.duration_seconds || 0));
  const end = rawEnd > start ? rawEnd : (realDuration > 0 ? start + realDuration : start + 5);
  return {
    key: segmentTime,
    scene,
    audioRef,
    start,
    end,
    duration: Math.max(0.5, end - start),
    url: `/api/audio/${encodeURIComponent(state.currentDate)}/${encodeURIComponent(audioRef.chunk_id)}`,
  };
}

export function ensureSceneAudio() {
  if (sharedSceneAudio) return sharedSceneAudio;
  const audio = new Audio();
  audio.preload = 'metadata';
  audio.addEventListener('timeupdate', () => {
    if (!state.playback.activeKey) return;
    const current = Number(audio.currentTime || 0);
    if (current >= state.playback.sceneEnd - 0.05) {
      state.playback.progress = state.playback.duration;
      if (!audio.paused) {
        audio.pause();
      }
      audio.currentTime = state.playback.sceneEnd;
    } else {
      state.playback.progress = Math.max(0, current - state.playback.sceneStart);
    }
    syncScenePlaybackUi();
  });
  audio.addEventListener('play', () => {
    state.playback.status = 'playing';
    syncScenePlaybackUi();
  });
  audio.addEventListener('pause', () => {
    if (!state.playback.activeKey) return;
    state.playback.status = 'paused';
    syncScenePlaybackUi();
  });
  audio.addEventListener('ended', () => {
    state.playback.status = 'paused';
    state.playback.progress = state.playback.duration;
    syncScenePlaybackUi();
  });
  setSharedSceneAudio(audio);
  return audio;
}

export function stopScenePlayback() {
  if (sharedSceneAudio) {
    sharedSceneAudio.pause();
  }
  state.playback.activeKey = '';
  state.playback.activeChunkId = '';
  state.playback.status = 'idle';
  state.playback.progress = 0;
  state.playback.duration = 0;
  state.playback.sceneStart = 0;
  state.playback.sceneEnd = 0;
  emitPlaybackChange();
}

export async function loadSceneAudioSource(audio, url) {
  await new Promise((resolve, reject) => {
    function cleanup() {
      audio.removeEventListener('loadedmetadata', handleReady);
      audio.removeEventListener('error', handleError);
    }

    const handleReady = () => {
      cleanup();
      resolve();
    };
    const handleError = () => {
      cleanup();
      reject(new Error('audio_load_failed'));
    };
    audio.addEventListener('loadedmetadata', handleReady, { once: true });
    audio.addEventListener('error', handleError, { once: true });
    audio.src = url;
    audio.load();
  });
}

export async function prepareScenePlayback(target) {
  const audio = ensureSceneAudio();
  const sourceChanged = state.playback.activeChunkId !== target.audioRef.chunk_id || !audio.src.endsWith(target.url);
  if (sourceChanged) {
    await loadSceneAudioSource(audio, target.url);
  }
  state.playback.activeKey = target.key;
  state.playback.activeChunkId = target.audioRef.chunk_id;
  state.playback.sceneStart = target.start;
  state.playback.sceneEnd = target.end;
  state.playback.duration = target.duration;
  state.playback.progress = Math.max(0, Number(audio.currentTime || 0) - target.start);
  audio.playbackRate = state.playback.rate;
  if (sourceChanged || Math.abs(Number(audio.currentTime || 0) - target.start) > 0.2) {
    audio.currentTime = target.start;
    state.playback.progress = 0;
  }
  syncScenePlaybackUi();
  return audio;
}

export function syncScenePlaybackUi() {
  document.querySelectorAll('.scene-playback').forEach((node) => {
    const key = node.dataset.playbackKey || '';
    const duration = Number(node.dataset.playbackDuration || 0);
    const active = key === state.playback.activeKey;
    const progress = active ? Math.min(duration, Math.max(0, state.playback.progress || 0)) : 0;
    const button = node.querySelector('.scene-playback-btn');
    const range = node.querySelector('.scene-playback-range');
    const time = node.querySelector('.scene-playback-time');
    const speed = node.querySelector('.scene-playback-rate');
    node.classList.toggle('is-active', active);
    node.closest('.record-item')?.classList.toggle('is-playing', active);
    if (button) {
      button.textContent = active && state.playback.status === 'playing' ? '暂停原声' : '播放原声';
      button.setAttribute('aria-pressed', active && state.playback.status === 'playing' ? 'true' : 'false');
    }
    if (range) {
      range.disabled = !active;
      range.max = String(duration);
      range.value = String(progress);
    }
    if (time) {
      time.textContent = `${formatPlaybackClock(progress)} / ${formatPlaybackClock(duration)}`;
    }
    if (speed) {
      speed.value = String(state.playback.rate || 1);
    }
  });
  emitPlaybackChange();
}

export function renderScenePlaybackControl(segment) {
  const target = getSegmentSceneTarget(segment.time);
  if (!target || !target.audioRef) {
    return `
      <div class="scene-playback is-unavailable">
        <button class="scene-playback-btn" type="button" disabled>录音不可用</button>
        <span class="scene-playback-note">旧数据或缺少定位时，这里会安全禁用。</span>
      </div>
    `;
  }

  const active = state.playback.activeKey === target.key;
  const progress = active ? Math.min(target.duration, Math.max(0, state.playback.progress || 0)) : 0;
  const rate = String(state.playback.rate || 1);
  return `
    <div class="scene-playback ${active ? 'is-active' : ''}" data-playback-key="${escapeHtml(target.key)}" data-playback-duration="${target.duration}">
      <button class="scene-playback-btn" type="button" onclick="toggleScenePlayback('${escapeHtml(target.key)}')" aria-pressed="${active && state.playback.status === 'playing' ? 'true' : 'false'}">
        ${active && state.playback.status === 'playing' ? '暂停原声' : '播放原声'}
      </button>
      <input class="scene-playback-range" type="range" min="0" max="${target.duration}" step="0.1" value="${progress}" ${active ? '' : 'disabled'} oninput="seekScenePlayback('${escapeHtml(target.key)}', this.value)">
      <span class="scene-playback-time">${formatPlaybackClock(progress)} / ${formatPlaybackClock(target.duration)}</span>
      <select class="scene-playback-rate" onchange="setScenePlaybackRate('${escapeHtml(target.key)}', this.value)">
        <option value="0.5" ${rate === '0.5' ? 'selected' : ''}>0.5x</option>
        <option value="1" ${rate === '1' ? 'selected' : ''}>1x</option>
        <option value="1.5" ${rate === '1.5' ? 'selected' : ''}>1.5x</option>
        <option value="2" ${rate === '2' ? 'selected' : ''}>2x</option>
      </select>
    </div>
  `;
}

export async function toggleScenePlayback(segmentTime) {
  const target = getSegmentSceneTarget(segmentTime);
  if (!target?.audioRef) {
    showToast('这段录音现在不可用。');
    return;
  }

  const audio = ensureSceneAudio();
  if (state.playback.activeKey === target.key && !audio.paused) {
    audio.pause();
    return;
  }

  try {
    await prepareScenePlayback(target);
    await audio.play();
  } catch (error) {
    stopScenePlayback();
    syncScenePlaybackUi();
    showToast('这段录音暂时打不开。');
  }
}

export async function seekScenePlayback(segmentTime, rawValue) {
  const target = getSegmentSceneTarget(segmentTime);
  if (!target?.audioRef) return;

  try {
    const audio = ensureSceneAudio();
    if (state.playback.activeKey !== target.key) {
      await prepareScenePlayback(target);
      audio.pause();
    }
    const nextOffset = Math.max(0, Math.min(target.duration, Number(rawValue || 0)));
    audio.currentTime = target.start + nextOffset;
    state.playback.progress = nextOffset;
    state.playback.status = audio.paused ? 'paused' : 'playing';
    syncScenePlaybackUi();
  } catch (error) {
    stopScenePlayback();
    syncScenePlaybackUi();
    showToast('这段录音暂时打不开。');
  }
}

export function setScenePlaybackRate(_segmentTime, rawValue) {
  const nextRate = Number(rawValue || 1) || 1;
  state.playback.rate = nextRate;
  localStorage.setItem('openmy-playback-rate', String(nextRate));
  if (sharedSceneAudio) {
    sharedSceneAudio.playbackRate = nextRate;
  }
  syncScenePlaybackUi();
}
