// app.js — 入口文件
import { state, searchTimer, setSearchTimer } from './modules/state.js';
import { loadSidebar, renderSidebar, toggleSidebar, closeSidebar } from './modules/sidebar.js';
import { renderHomePage } from './modules/home.js';
import { loadDate, toggleSection, toggleRawText, scrollToSegment, optionMarkup } from './modules/daily.js';
import { renderWeeklyReport, renderMonthlyReport } from './modules/reports.js';
import { openSpotlight, closeSpotlight, handleSpotlightKeydown, runSearchSpotlight, jumpToSearchResult } from './modules/search.js';
import { openSettings, closeSettingsOverlay, loadOnboarding, loadScreenContextSettings, applySettings, applySettingsUI, saveSetting, selectTranscriptionOption, setTranscriptionLane, confirmTranscriptionProvider, selectOnboardingProvider, renderOnboardingCard, renderHomeOnboardingCard, updateScreenContextMode, saveScreenContextExclusions, rerenderSettingsOverlay } from './modules/settings.js';
import { openCorrectionPopover, closeCorrectionPopover, submitInlineCorrection, renderSidebarDict, toggleSidebarDict, submitContextAction, toggleAccordion, submitTypoCorrection, refreshCorrectionsFeed, openSelectionPopover, closeSelectionPopover, openSubtitleReviewFromSelection, openCorrectionFromSelection } from './modules/corrections.js';
import { refreshPipelineJobs, loadPipelineJobDetail, runPipelineAction, clearHomeJobFocus, createPipelineJob, onHomeFileInputChange, onHomeDropzoneDragOver, onHomeDropzoneDragLeave, onHomeDropzoneDrop, setPipelineHooks, renderHomeDropZone } from './modules/pipeline.js';
import { runContextQuery, jumpToEvidence, loadContext, setContextHooks, renderWikiHome, wizardNext, wizardBack, wizardSelectEngine, wizardConfirmEngine, wizardGoHome } from './modules/context.js';
import { getCurrentHashRoute } from './modules/router.js';
import { toggleScenePlayback, seekScenePlayback, setScenePlaybackRate } from './modules/playback.js';
import { openProfileModal, closeProfileModal, confirmProfileModal, setProfileHooks } from './modules/profile.js';
import { fetchWaveformData, renderWaveform, bindWaveformSeek } from './modules/waveform.js';
import { openSubtitleReview, closeSubtitleReview, renderSubtitleReview, toggleSubtitleReviewPlayback, seekSubtitleReview, focusSubtitleSentence, setSubtitleReviewRate, jumpToCorrectionFromReview, updateSentenceHighlight, updateWaveformProgress } from './modules/subtitle-overlay.js';
import { showToast } from './modules/utils.js';

setContextHooks({ rerenderSettingsOverlay, renderHomePage, renderWeeklyReport, renderMonthlyReport });
setPipelineHooks({ rerenderSettingsOverlay, refreshContext: loadContext });

setProfileHooks({ renderHomePage });

Object.assign(window, {
  state, showToast, renderSidebar, renderHomePage, renderWeeklyReport, renderMonthlyReport, loadDate,
  openSpotlight, closeSpotlight, openSettings, closeSettingsOverlay, toggleSidebar, closeSidebar,
  openCorrectionPopover, closeCorrectionPopover, submitInlineCorrection, renderSidebarDict, toggleSidebarDict,
  openSelectionPopover, closeSelectionPopover, openSubtitleReviewFromSelection, openCorrectionFromSelection,
  refreshPipelineJobs, loadPipelineJobDetail, runPipelineAction, clearHomeJobFocus, createPipelineJob,
  runContextQuery, jumpToEvidence, toggleSection, toggleRawText, toggleScenePlayback, seekScenePlayback,
  setScenePlaybackRate, openProfileModal, closeProfileModal, confirmProfileModal, selectTranscriptionOption, setTranscriptionLane,
  confirmTranscriptionProvider, selectOnboardingProvider, saveSetting, submitContextAction, toggleAccordion,
  submitTypoCorrection, onHomeFileInputChange, onHomeDropzoneDragOver, onHomeDropzoneDragLeave,
  onHomeDropzoneDrop, jumpToSearchResult, renderOnboardingCard, renderHomeOnboardingCard,
  updateScreenContextMode, saveScreenContextExclusions, optionMarkup, scrollToSegment, renderWikiHome,
  renderHomeDropZone, wizardNext, wizardBack, wizardSelectEngine, wizardConfirmEngine, wizardGoHome,
  fetchWaveformData, renderWaveform, bindWaveformSeek,
  openSubtitleReview, closeSubtitleReview, renderSubtitleReview, toggleSubtitleReviewPlayback, seekSubtitleReview,
  focusSubtitleSentence, setSubtitleReviewRate, jumpToCorrectionFromReview, updateSentenceHighlight, updateWaveformProgress,
});

async function init() {
  const spotlightInput = document.getElementById('spotlightInput');
  spotlightInput.addEventListener('input', (event) => {
    clearTimeout(searchTimer);
    setSearchTimer(setTimeout(() => runSearchSpotlight(event.target.value.trim()), 200));
  });
  spotlightInput.addEventListener('keydown', handleSpotlightKeydown);

  applySettings();
  await loadSidebar();
  await Promise.all([
    loadContext(),
    loadOnboarding(),
    loadScreenContextSettings(),
    refreshCorrectionsFeed(),
    refreshPipelineJobs(),
  ]);

  // Route based on hash
  const hashRoute = getCurrentHashRoute();
  if (hashRoute === 'start') {
    renderWikiHome();
  } else {
    renderHomePage();
  }

  // Handle browser back/forward
  window.addEventListener('hashchange', () => {
    const route = getCurrentHashRoute();
    if (route === 'start') {
      renderWikiHome();
    } else {
      renderHomePage();
    }
  });

  setInterval(refreshPipelineJobs, 1000);
}

init();
