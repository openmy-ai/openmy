// state.js — 全局应用状态
export const state = {
  allDates: [],
  stats: null,
  route: 'home',
  currentDate: '',
  currentData: null,
  currentMeta: null,
  currentBriefing: null,
  context: {},
  onboarding: {},
  selectedTranscriptionProvider: '',
  transcriptionLane: '',
  wizardStep: 0,
  showWikiHome: false,
  settingsSection: '',
  loops: [],
  projects: [],
  decisions: [],
  corrections: [],
  searchResults: [],
  spotlightIndex: -1,
  jobs: [],
  selectedJobId: '',
  selectedJobDetail: null,
  handledCompletedJobs: new Set(),
  handledTerminalNotices: new Set(),
  homeJobFocusId: '',
  uploadingHomeFiles: false,
  chartInstances: [],
  contextQuery: {
    kind: 'project',
    query: '',
    result: null,
    loading: false,
  },
  screenSettings: {
    enabled: true,
    participation_mode: 'summary_only',
    exclude_apps: [],
    exclude_domains: [],
    exclude_window_keywords: [],
  },
  playback: {
    activeKey: '',
    activeChunkId: '',
    status: 'idle',
    progress: 0,
    duration: 0,
    rate: Number(localStorage.getItem('openmy-playback-rate') || '1') || 1,
    sceneStart: 0,
    sceneEnd: 0,
  },
  correctionAnchor: null,
  subtitleReview: {
    open: false,
    selectedSentenceIndex: 0,
  },
  profile: {
    name: localStorage.getItem('openmy-profile-name') || '',
    emoji: localStorage.getItem('openmy-profile-emoji') || '',
  },
};

export let searchTimer = null;
export let sharedSceneAudio = null;

export function setSearchTimer(value) {
  searchTimer = value;
}

export function setSharedSceneAudio(value) {
  sharedSceneAudio = value;
}
