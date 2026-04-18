const waveformCache = new Map();

function resolveWaveformColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function formatWaveformTime(seconds = 0) {
  const totalSeconds = Math.max(0, Math.floor(Number(seconds || 0)));
  const minutes = Math.floor(totalSeconds / 60);
  const remainder = totalSeconds % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

function getPointerClientX(event) {
  if (typeof event.clientX === 'number') return event.clientX;
  if (event.touches?.[0] && typeof event.touches[0].clientX === 'number') {
    return event.touches[0].clientX;
  }
  return 0;
}

export async function fetchWaveformData(audioUrl) {
  if (waveformCache.has(audioUrl)) {
    return waveformCache.get(audioUrl);
  }

  const response = await fetch(audioUrl);
  if (!response.ok) {
    throw new Error(`waveform_fetch_failed:${response.status}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  const audioContext = new (window.AudioContext || window.webkitAudioContext)();
  try {
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    const channelData = audioBuffer.getChannelData(0);
    const samplesPerPoint = Math.max(1, Math.floor(audioBuffer.sampleRate / 10));
    const points = Math.max(1, Math.ceil(channelData.length / samplesPerPoint));
    const waveform = new Float32Array(points);

    for (let index = 0; index < points; index += 1) {
      let sum = 0;
      const start = index * samplesPerPoint;
      const end = Math.min(start + samplesPerPoint, channelData.length);
      for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
        sum += Math.abs(channelData[sampleIndex]);
      }
      waveform[index] = end > start ? sum / (end - start) : 0;
    }

    const payload = { waveform, duration: audioBuffer.duration };
    waveformCache.set(audioUrl, payload);
    return payload;
  } finally {
    await audioContext.close();
  }
}

export function renderWaveform(canvas, waveform, duration, speechSegments = [], currentTime = 0) {
  if (!canvas || !waveform?.length || !duration) return;

  const ctx = canvas.getContext('2d');
  const width = canvas.clientWidth || canvas.width || 600;
  const height = canvas.clientHeight || canvas.height || 64;
  const dpr = window.devicePixelRatio || 1;

  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const barWidth = Math.max(width / waveform.length, 1);
  const mid = height / 2;
  let maxAmp = 0;
  for (const value of waveform) {
    if (value > maxAmp) maxAmp = value;
  }
  maxAmp = maxAmp || 1;

  const playedSpeech = resolveWaveformColor('--waveform-played-speech', '#4f9cf7');
  const playedSilence = resolveWaveformColor('--waveform-played-silence', '#3a6ea5');
  const idleSpeech = resolveWaveformColor('--waveform-speech', 'rgba(79, 156, 247, 0.5)');
  const idleSilence = resolveWaveformColor('--waveform-silence', 'rgba(255, 255, 255, 0.15)');
  const cursorColor = resolveWaveformColor('--waveform-cursor', '#ffffff');

  const pointsPerSecond = waveform.length / duration;
  const vadRanges = Array.isArray(speechSegments)
    ? speechSegments
      .filter((item) => item && typeof item === 'object')
      .map((item) => ({
        startIdx: Math.floor(Math.max(0, Number(item.start || 0)) * pointsPerSecond),
        endIdx: Math.ceil(Math.max(0, Number(item.end || 0)) * pointsPerSecond),
      }))
    : [];
  const progressIdx = Math.floor((Math.max(0, Math.min(duration, currentTime)) / duration) * waveform.length);

  for (let index = 0; index < waveform.length; index += 1) {
    const amplitude = (waveform[index] / maxAmp) * mid * 0.9;
    const inSpeech = !vadRanges.length || vadRanges.some((range) => index >= range.startIdx && index <= range.endIdx);
    const isPlayed = index <= progressIdx;
    ctx.fillStyle = isPlayed
      ? (inSpeech ? playedSpeech : playedSilence)
      : (inSpeech ? idleSpeech : idleSilence);
    ctx.fillRect(index * barWidth, mid - amplitude, Math.max(barWidth - 0.5, 1), amplitude * 2);
  }

  const progressX = (Math.max(0, Math.min(duration, currentTime)) / duration) * width;
  ctx.strokeStyle = cursorColor;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(progressX, 0);
  ctx.lineTo(progressX, height);
  ctx.stroke();
}

export function bindWaveformSeek(canvas, duration, onSeek) {
  let dragging = false;

  const getTime = (event) => {
    const rect = canvas.getBoundingClientRect();
    const clientX = getPointerClientX(event);
    const x = clientX - rect.left;
    return Math.max(0, Math.min(duration, (x / rect.width) * duration));
  };

  const handleMouseDown = (event) => {
    dragging = true;
    onSeek(getTime(event));
  };
  const handleMouseMove = (event) => {
    if (dragging) onSeek(getTime(event));
  };
  const handleStop = () => {
    dragging = false;
  };
  const handleTouchStart = (event) => {
    dragging = true;
    onSeek(getTime(event));
  };
  const handleTouchMove = (event) => {
    if (dragging) onSeek(getTime(event));
  };

  canvas.addEventListener('mousedown', handleMouseDown);
  canvas.addEventListener('mousemove', handleMouseMove);
  canvas.addEventListener('mouseup', handleStop);
  canvas.addEventListener('mouseleave', handleStop);
  canvas.addEventListener('touchstart', handleTouchStart, { passive: true });
  canvas.addEventListener('touchmove', handleTouchMove, { passive: true });
  canvas.addEventListener('touchend', handleStop);

  return () => {
    canvas.removeEventListener('mousedown', handleMouseDown);
    canvas.removeEventListener('mousemove', handleMouseMove);
    canvas.removeEventListener('mouseup', handleStop);
    canvas.removeEventListener('mouseleave', handleStop);
    canvas.removeEventListener('touchstart', handleTouchStart);
    canvas.removeEventListener('touchmove', handleTouchMove);
    canvas.removeEventListener('touchend', handleStop);
  };
}

export { formatWaveformTime };
