// router.js — hash 路由
import { state } from './state.js';
import { renderSidebar } from './sidebar.js';

const ROUTES = ['home', 'start', 'weekly', 'monthly'];

export function setRoute(route) {
  state.route = route;
  // Sync hash without triggering hashchange
  const hash = route === 'home' ? '' : `#/${route}`;
  if (location.hash !== hash && `#${location.hash}` !== hash) {
    history.replaceState(null, '', hash || location.pathname);
  }
  document.getElementById('settingsBtn')?.classList.remove('active');
  renderSidebar();
}

export function getCurrentHashRoute() {
  const hash = location.hash.replace(/^#\/?/, '');
  if (ROUTES.includes(hash)) return hash;
  return '';
}
