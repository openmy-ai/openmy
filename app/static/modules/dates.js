// dates.js — 日期工具和数据聚合
import { state } from './state.js';
import { plainText } from './utils.js';

export function parseIsoDate(dateStr) {
  const [year, month, day] = String(dateStr || '').split('-').map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

export function formatShortDate(dateStr) {
  const date = parseIsoDate(dateStr);
  return `${date.getMonth() + 1}.${date.getDate()}`;
}

export function formatFriendlyDate(dateStr) {
  const date = parseIsoDate(dateStr);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

export function formatPageDate(dateStr) {
  const date = parseIsoDate(dateStr);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

export function formatRangeLabel(start, end) {
  const s = formatFriendlyDate(start);
  const e = formatFriendlyDate(end);
  return s === e ? s : `${s} – ${e}`;
}

export function formatPlaybackClock(value) {
  const seconds = Math.max(0, Number(value || 0));
  const minutes = Math.floor(seconds / 60);
  const remain = Math.floor(seconds % 60);
  return `${minutes}:${String(remain).padStart(2, '0')}`;
}

export function getVisibleDates() {
  const currentYear = new Date().getFullYear();
  return [...(state.allDates || [])]
    .filter((item) => {
      const year = Number.parseInt(String(item?.date || '').split('-')[0], 10);
      return Number.isFinite(year) && year <= currentYear + 1;
    });
}

export function latestDateInfo() {
  return getVisibleDates().sort((a, b) => b.date.localeCompare(a.date))[0] || null;
}

export function filterDateRange(startDate, endDate) {
  return getVisibleDates()
    .filter((item) => item.date >= startDate && item.date <= endDate)
    .sort((a, b) => b.date.localeCompare(a.date));
}

export function latestWeekDates() {
  const latest = latestDateInfo();
  if (!latest) return [];
  const anchor = parseIsoDate(latest.date);
  const day = anchor.getDay() || 7;
  const start = new Date(anchor);
  start.setDate(anchor.getDate() - day + 1);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const startLabel = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
  const endLabel = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`;
  return filterDateRange(startLabel, endLabel);
}

export function latestMonthDates() {
  const latest = latestDateInfo();
  if (!latest) return [];
  const anchor = parseIsoDate(latest.date);
  const startLabel = `${anchor.getFullYear()}-${String(anchor.getMonth() + 1).padStart(2, '0')}-01`;
  return filterDateRange(startLabel, latest.date);
}

export function countKeywordDays(keyword, dates) {
  if (!keyword) return 0;
  const pattern = keyword.toLowerCase();
  return dates.filter((item) => {
    const haystacks = [
      item.summary,
      ...(item.events || []).map((event) => event.what || event.summary || ''),
      ...(item.decisions || []).map((decision) => decision.decision || decision.what || ''),
      ...(item.todos || []).map((todo) => todo.task || todo.what || ''),
    ];
    return haystacks.some((entry) => String(entry || '').toLowerCase().includes(pattern));
  }).length;
}

export function uniqueTextItems(items, limit = 4) {
  const values = [];
  const seen = new Set();
  items.forEach((item) => {
    const normalized = plainText(item || '');
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    values.push(normalized);
  });
  return values.slice(0, limit);
}

export function deriveProjectItemsFromDates(dates, limit = 4) {
  const counts = new Map();
  dates.forEach((item) => {
    const projectNames = [
      ...(item.decisions || []).map((entry) => entry.project),
      ...(item.todos || []).map((entry) => entry.project),
      ...(item.events || []).map((entry) => entry.project),
    ].filter(Boolean);
    [...new Set(projectNames)].forEach((name) => {
      counts.set(name, (counts.get(name) || 0) + 1);
    });
  });
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ label: name, meta: `${count} 天出现` }));
}

export function deriveLoopItemsFromDates(dates, limit = 4) {
  return uniqueTextItems(
    dates.flatMap((item) => (item.todos || []).map((entry) => entry.task || entry.what || '')),
    limit,
  ).map((text) => ({ label: text, meta: '来自最近录音' }));
}

export function looksWeakSummary(text) {
  const summary = plainText(text || '');
  if (!summary) return true;
  if (summary.length < 18) return true;
  const weakPatterns = ['主要用了', '主要在', '今天主要', '这段时间主要', '我主要', '暂无摘要'];
  return weakPatterns.some((pattern) => summary.includes(pattern));
}

export function buildDailySummary(detail, meta) {
  const primary = plainText(meta.daily_summary || state.currentBriefing?.summary || state.context.status_line || '');
  if (!looksWeakSummary(primary)) return primary;

  const insight = plainText((meta.insights || [])[0]?.content || '');
  const decision = plainText((meta.decisions || [])[0]?.decision || (meta.decisions || [])[0]?.what || '');
  const todo = plainText((meta.todos || [])[0]?.task || (meta.intents || [])[0]?.summary || '');
  const preview = plainText(detail.segments?.[0]?.summary || detail.segments?.[0]?.preview || detail.segments?.[0]?.text || '').slice(0, 120);

  const lines = [
    insight && `今天最值得记住的是：${insight}`,
    decision && `今天定下来的是：${decision}`,
    todo && `接下来要盯的是：${todo}`,
  ].filter(Boolean);

  if (lines.length) return lines.join(' ');
  return preview || primary || '今天还没有可以展示的摘要。';
}

export function buildWeeklySlots(dates) {
  if (!dates.length) return [];
  const latest = parseIsoDate(dates[0].date);
  const day = latest.getDay() || 7;
  const monday = new Date(latest);
  monday.setDate(latest.getDate() - day + 1);
  const map = new Map(dates.map((item) => [item.date, item]));
  return Array.from({ length: 7 }, (_, index) => {
    const current = new Date(monday);
    current.setDate(monday.getDate() + index);
    const date = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`;
    return map.get(date) || {
      date,
      segments: 0,
      word_count: 0,
      summary: '',
      timeline: [],
      decisions: [],
      todos: [],
      isPlaceholder: true,
    };
  });
}


export function getGreetingByHour() {
  const hour = new Date().getHours();
  if (hour < 6) return '夜深了';
  if (hour < 11) return '早上好';
  if (hour < 14) return '中午好';
  if (hour < 18) return '下午好';
  return '晚上好';
}
