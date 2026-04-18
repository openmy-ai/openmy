#!/usr/bin/env node

const { chromium } = require('playwright');

async function main() {
  const baseUrl = process.argv[2];
  if (!baseUrl) {
    throw new Error('missing baseUrl');
  }

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'],
  });

  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  try {
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => typeof window.loadDate === 'function');

    const result = await page.evaluate(async () => {
      await window.loadDate('2026-04-18');

      class FakeAudio {
        constructor() {
          this.preload = 'metadata';
          this.currentTime = 0;
          this.playbackRate = 1;
          this.paused = true;
          this.src = '';
          this.listeners = new Map();
        }

        addEventListener(type, handler) {
          const bucket = this.listeners.get(type) || [];
          bucket.push(handler);
          this.listeners.set(type, bucket);
        }

        removeEventListener(type, handler) {
          const bucket = this.listeners.get(type) || [];
          this.listeners.set(type, bucket.filter((item) => item !== handler));
        }

        emit(type) {
          const bucket = this.listeners.get(type) || [];
          for (const handler of bucket) {
            handler.call(this, { type, target: this });
          }
        }

        load() {
          queueMicrotask(() => this.emit('loadedmetadata'));
        }

        async play() {
          this.paused = false;
          this.emit('play');
        }

        pause() {
          this.paused = true;
          this.emit('pause');
        }
      }

      window.Audio = FakeAudio;

      const matchedSentence = '我的意思是按照我刚才说的这个工作流。';
      const anchor = {
        selectedText: '工作流',
        contextText: '兜底文案',
        segmentTime: '14:27',
        matchedSentence,
      };

      const displayButton = document.querySelector('.raw-btn')?.textContent?.trim() || '';

      window.openSelectionPopover(anchor, 120, 120);
      const selectionPopover = document.getElementById('selectionPopover');
      const sourceBtn = document.getElementById('selectionPopoverSourceBtn');
      const canSeeSourceAction = selectionPopover?.classList.contains('is-open') && !sourceBtn?.disabled;

      window.openSubtitleReviewFromSelection();
      await new Promise((resolve) => {
        let attempts = 0;
        const timer = setInterval(() => {
          const loadingEl = document.getElementById('subtitle-waveform-loading');
          attempts += 1;
          if (!loadingEl || loadingEl.style.display === 'none' || attempts > 30) {
            clearInterval(timer);
            resolve();
          }
        }, 100);
      });

      const overlay = document.getElementById('subtitleReviewOverlay');
      const overlayOpened = overlay?.classList.contains('active') || false;
      const exactText = document.querySelector('.subtitle-context')?.textContent?.trim() || '';
      const playButton = document.getElementById('subtitleReviewPlayButton')?.textContent?.trim() || '';
      const hasWaveform = Boolean(document.querySelector('.waveform-container'));
      const loadingHidden = document.getElementById('subtitle-waveform-loading')?.style.display === 'none';
      const noRangeInput = !document.querySelector('.subtitle-progress-range');
      const rateOptions = Array.from(document.querySelectorAll('.subtitle-rate-select option')).map((node) => node.textContent.trim());

      await window.toggleSubtitleReviewPlayback();
      await new Promise((resolve) => setTimeout(resolve, 0));
      const playedOnce = window.state.playback.status === 'playing';

      window.setSubtitleReviewRate('1.5');
      const switchedRate = window.state.playback.rate === 1.5;

      await window.seekSubtitleReview(1.1);
      await new Promise((resolve) => setTimeout(resolve, 0));
      const progressed = Number(window.state.playback.progress || 0) >= 1;
      const waveformClock = document.getElementById('subtitle-waveform-time')?.textContent || '';

      const sentenceButtons = Array.from(document.querySelectorAll('.subtitle-sentence'));
      const lastButton = sentenceButtons[sentenceButtons.length - 1];
      const lastLabel = lastButton?.querySelector('.subtitle-sentence-label')?.textContent?.trim() || '';
      lastButton?.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
      const clickedLabel = document.querySelector('.subtitle-sentence.is-active .subtitle-sentence-label')?.textContent?.trim() || '';
      const clickedKey = window.state.playback.activeKey || '';

      window.jumpToCorrectionFromReview();
      await new Promise((resolve) => setTimeout(resolve, 0));
      const correctionDrawerOpen = document.getElementById('correctionPopover')?.classList.contains('is-open') || false;
      const correctionContext = document.getElementById('cpContextText')?.textContent?.trim() || '';

      return {
        checks: {
          selectionHasSourceAction: canSeeSourceAction,
          overlayOpened,
          waveformLoaded: hasWaveform && loadingHidden,
          exactSentenceShown: exactText === matchedSentence,
          overlayButtonRenamed: playButton === '回听整段录音',
          noRangeInput,
          displayButtonRenamed: displayButton === '显示原文和播放原声',
          playbackWorks: playedOnce && switchedRate && progressed,
          sentenceClickJump: Boolean(lastLabel) && clickedLabel === lastLabel && clickedKey.endsWith('::subtitle-review'),
          jumpToCorrectionKeepsSentence: correctionDrawerOpen && correctionContext === matchedSentence,
        },
        details: {
          rateOptions,
          waveformClock,
        },
      };
    });

    const failures = [];
    const expectedRates = ['0.5x', '1x', '1.5x', '2x'];

    for (const [name, passed] of Object.entries(result.checks || {})) {
      if (!passed) failures.push(name);
    }
    if (JSON.stringify(result.details.rateOptions) !== JSON.stringify(expectedRates)) {
      failures.push('rate-options');
    }
    if (!/0:0[1-9]|0:[1-5][0-9]/.test(result.details.waveformClock)) {
      failures.push('waveform-clock');
    }

    if (failures.length) {
      console.error(JSON.stringify({ ok: false, failures, result }, null, 2));
      process.exit(1);
    }

    console.log(JSON.stringify({ ok: true, result }, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
