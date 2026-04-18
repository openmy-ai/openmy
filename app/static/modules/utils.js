// utils.js — 通用工具
export function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('visible'), 2600);
}

export function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function plainText(value) {
  return String(value || '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/<[^>]+>/g, '')
    .replace(/^---+$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export function fmtText(value) {
  const safe = escapeHtml(value || '');
  return safe.split(/\n+/).map((paragraph) => paragraph.trim() ? `<p>${paragraph}</p>` : '').join('');
}

export function fmtNum(value) {
  const number = Number(value || 0);
  if (number >= 10000) return `${(number / 10000).toFixed(1)}万`;
  if (number >= 1000) return `${(number / 1000).toFixed(1)}k`;
  return String(number);
}

export function renderEmptyState(text) {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

export function renderEventList(items, renderItem, emptyText) {
  if (!items || !items.length) {
    return renderEmptyState(emptyText);
  }
  return items.map(renderItem).join('');
}

export function truncateSummary(text, maxLength = 50) {
  const summary = plainText(text || '');
  if (!summary) return '暂无摘要';
  return summary.length > maxLength ? `${summary.slice(0, maxLength)}…` : summary;
}

export function highlightQuerySnippet(text, query) {
  const safe = escapeHtml(plainText(text || ''));
  if (!query) return safe;
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return safe.replace(new RegExp(`(${escapedQuery})`, 'gi'), '<mark class="search-highlight">$1</mark>');
}
