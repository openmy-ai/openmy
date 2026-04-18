// profile.js — 个人资料
import { state } from './state.js';
import { showToast } from './utils.js';

const profileHooks = {
  renderHomePage: null,
};

export function setProfileHooks(hooks = {}) {
  Object.assign(profileHooks, hooks);
}

export function getProfileName() {
  return state.profile.name || '';
}

export function getProfileEmoji() {
  return state.profile.emoji || '👋';
}

export function getProfileInitial() {
  const name = getProfileName();
  if (!name) return '?';
  return name.charAt(0).toUpperCase();
}

export function saveProfile(name, emoji) {
  state.profile.name = name || '';
  state.profile.emoji = emoji || '';
  localStorage.setItem('openmy-profile-name', state.profile.name);
  localStorage.setItem('openmy-profile-emoji', state.profile.emoji);
  if (state.route === 'home') {
    profileHooks.renderHomePage?.();
  }
}

export function openProfileModal() {
  let modal = document.getElementById('profileModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'profileModal';
    modal.className = 'profile-modal';
    modal.onclick = (e) => { if (e.target === modal) closeProfileModal(); };
    modal.innerHTML = `
      <div class="profile-modal-card" onclick="event.stopPropagation()">
        <div class="profile-modal-title">设置你的名字</div>
        <div style="margin-bottom:12px">
          <label class="form-label">昵称</label>
          <input id="profileNameInput" class="field-input" type="text" placeholder="你叫什么？" maxlength="20" autocomplete="off">
        </div>
        <div style="margin-bottom:12px">
          <label class="form-label">头像 Emoji</label>
          <div style="display:flex;gap:8px;flex-wrap:wrap" id="profileEmojiPicker">
            ${['👋','😊','🚀','💡','🎧','🎯','🔥','✨','🐱','🌟','💻','🎵'].map((e) => `<button type="button" class="setting-opt" data-emoji="${e}" onclick="document.querySelectorAll('#profileEmojiPicker .setting-opt').forEach(b=>b.classList.remove('active'));this.classList.add('active')" style="font-size:18px;padding:6px 10px">${e}</button>`).join('')}
          </div>
        </div>
        <div class="profile-modal-footer">
          <button class="action-btn" type="button" onclick="closeProfileModal()">取消</button>
          <button class="action-btn primary" type="button" onclick="confirmProfileModal()">保存</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  const nameInput = document.getElementById('profileNameInput');
  if (nameInput) nameInput.value = getProfileName();
  const currentEmoji = getProfileEmoji();
  document.querySelectorAll('#profileEmojiPicker .setting-opt').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.emoji === currentEmoji);
  });
  modal.classList.add('is-open');
  setTimeout(() => nameInput?.focus(), 100);
}

export function closeProfileModal() {
  document.getElementById('profileModal')?.classList.remove('is-open');
}

export function confirmProfileModal() {
  const name = document.getElementById('profileNameInput')?.value.trim() || '';
  const emojiBtn = document.querySelector('#profileEmojiPicker .setting-opt.active');
  const emoji = emojiBtn?.dataset.emoji || getProfileEmoji();
  saveProfile(name, emoji);
  closeProfileModal();
  showToast(name ? `欢迎，${name}！` : '名字已清除');
}
