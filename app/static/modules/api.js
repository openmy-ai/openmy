// api.js — 网络请求封装
import { showToast } from './utils.js';

export async function fetchJson(url, fallback = undefined) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      if (fallback !== undefined) return fallback;
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    if (fallback !== undefined) return fallback;
    showToast(`请求失败：${error.message}`);
    throw error;
  }
}

export async function postJson(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `${response.status} ${response.statusText}`);
  }
  return data;
}
