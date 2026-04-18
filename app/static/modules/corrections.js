// corrections.js — 纠错系统
import { state } from './state.js';
import { fetchJson, postJson } from './api.js';
import { escapeHtml, plainText, showToast } from './utils.js';
import { loadDate } from './daily.js';
import { loadContext } from './context.js';
import { rerenderSettingsOverlay } from './settings.js';

const SELECTION_TARGET_SELECTOR = '.seg-raw, .seg-distilled, .record-card, .briefing-card, .spotlight-result-item, .event-item, .prop-item, .time-block';
const SELECTION_CONTEXT_SELECTOR = '.record-card, .briefing-card, .spotlight-result-item, .event-item, .prop-item, .time-block';

export async function refreshCorrectionsFeed() {
  const payload = await fetchJson('/api/corrections', { corrections: [] });
  state.corrections = payload.corrections || [];
  renderSidebarDict();
  rerenderSettingsOverlay();
}

export async function submitTypoCorrection() {
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

export function toggleAccordion(titleEl) {
  const body = titleEl.nextElementSibling;
  if (!body) return;
  const isHidden = body.style.display === 'none';
  body.style.display = isHidden ? 'block' : 'none';
  const arrow = titleEl.querySelector('span');
  if (arrow) arrow.textContent = isHidden ? '▲ 收起' : '▼ 展开';
}

export async function submitContextAction(url, payload, successMessage) {
  try {
    await postJson(url, payload);
    showToast(successMessage);
    await loadContext();
    rerenderSettingsOverlay();
  } catch (error) {
    showToast(error.message);
  }
}

export function splitSettingList(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}


export function renderSidebarDict() {
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

export function toggleSidebarDict() {
  const btn = document.querySelector('.sidebar-dict-toggle');
  const list = document.getElementById('sidebarDictList');
  btn.classList.toggle('open');
  list.classList.toggle('open');
}

function getSelectionElement(node) {
  if (!node) return null;
  if (node.nodeType === Node.ELEMENT_NODE) {
    return node;
  }
  return node.parentElement || null;
}

function extractMatchedSentence(targetEl, selectedText = '') {
  if (!targetEl || !selectedText) return '';
  const block = targetEl.closest(SELECTION_TARGET_SELECTOR);
  if (!block) return '';
  const fullText = plainText(block.textContent || '');
  if (!fullText) return '';
  const sentences = fullText.match(/[^。！？；\n]+[。！？；]?/g) || [fullText];
  const needle = plainText(selectedText);
  const hit = sentences.find((item) => item.includes(needle));
  if (hit) return hit.trim();
  const compact = needle.replace(/\s+/g, '');
  const fuzzy = sentences.find((item) => item.replace(/\s+/g, '').includes(compact));
  return fuzzy ? fuzzy.trim() : '';
}

function buildCorrectionAnchor(selectedText, targetEl) {
  const contextBlock = targetEl?.closest(SELECTION_CONTEXT_SELECTOR) || targetEl;
  const segmentTime = targetEl?.closest('[data-segment-time]')?.dataset.segmentTime || '';
  const contextText = plainText(contextBlock?.textContent || selectedText);
  return {
    selectedText,
    contextText,
    segmentTime,
    matchedSentence: extractMatchedSentence(targetEl, selectedText),
  };
}

function positionSelectionPopover(popover, mouseX, mouseY) {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const width = Math.min(320, viewportWidth - 24);
  const left = Math.max(12, Math.min(mouseX - width / 2, viewportWidth - width - 12));
  const top = Math.max(12, Math.min(mouseY + 12, viewportHeight - 160));
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
}

function shouldIgnoreSelectionTarget(targetEl) {
  return Boolean(targetEl?.closest('input, textarea, button, select, .correction-drawer, .subtitle-review-panel, .selection-popover, .spotlight-modal'));
}

function getSelectionTarget(selection, eventTarget) {
  const anchorEl = getSelectionElement(selection?.anchorNode);
  const focusEl = getSelectionElement(selection?.focusNode);
  const eventEl = getSelectionElement(eventTarget);
  const anchorBlock = anchorEl?.closest(SELECTION_TARGET_SELECTOR) || null;
  const focusBlock = focusEl?.closest(SELECTION_TARGET_SELECTOR) || null;
  const eventBlock = eventEl?.closest(SELECTION_TARGET_SELECTOR) || null;
  if (!anchorBlock || !focusBlock || !eventBlock) return null;
  if (anchorBlock !== focusBlock || anchorBlock !== eventBlock) return null;
  return anchorBlock;
}

export function openSelectionPopover(anchor = state.correctionAnchor, mouseX = 0, mouseY = 0) {
  const popover = document.getElementById('selectionPopover');
  const textEl = document.getElementById('selectionPopoverText');
  const sourceBtn = document.getElementById('selectionPopoverSourceBtn');
  if (!popover || !textEl) return;
  state.correctionAnchor = anchor;
  textEl.textContent = anchor?.selectedText || '先在日报里选一段字。';
  if (sourceBtn) {
    sourceBtn.disabled = !anchor?.segmentTime;
  }
  positionSelectionPopover(popover, mouseX, mouseY);
  popover.classList.add('is-open');
}

export function closeSelectionPopover() {
  document.getElementById('selectionPopover')?.classList.remove('is-open');
}

export function openSubtitleReviewFromSelection() {
  if (!state.correctionAnchor) {
    showToast('先在日报里选一段字。');
    return;
  }
  closeSelectionPopover();
  window.openSubtitleReview?.(state.correctionAnchor);
}

export function openCorrectionFromSelection() {
  if (!state.correctionAnchor) {
    showToast('先在日报里选一段字。');
    return;
  }
  const anchor = state.correctionAnchor;
  closeSelectionPopover();
  openCorrectionPopover(anchor.selectedText, 0, 0, anchor.matchedSentence || anchor.contextText);
}

// === Selection + Correction ===
document.addEventListener('mouseup', (event) => {
  const selection = window.getSelection();
  const selectedText = selection?.toString().trim();
  if (!selectedText || selectedText.length < 2 || selectedText.length > 50) return;
  const targetEl = getSelectionTarget(selection, event.target);
  if (!targetEl || shouldIgnoreSelectionTarget(targetEl)) return;
  const anchor = buildCorrectionAnchor(selectedText, targetEl);
  openSelectionPopover(anchor, event.clientX, event.clientY);
});

export function openCorrectionPopover(wrongText = '', mouseX = 0, mouseY = 0, contextText = '') {
  closeSelectionPopover();
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

export function closeCorrectionPopover() {
  document.getElementById('correctionPopover').classList.remove('is-open');
  document.body.style.overflow = '';
}

export async function submitInlineCorrection() {
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
  const popover = document.getElementById('selectionPopover');
  if (popover?.classList.contains('is-open') && !popover.contains(e.target)) {
    closeSelectionPopover();
  }
  if (drawer.classList.contains('is-open') && !drawer.contains(e.target)) {
    closeCorrectionPopover();
  }
});
