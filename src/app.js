import { loadManifest, loadCategoryPage, loadSearchIndex } from './data-loader.js';
import { setSearchIndex, searchTitles } from './search.js';
import { initTheatre, switchEpisode, changeServerMode, closePlayer } from './player.js';
import { getQueryParams, updateUrlState } from './router.js';
import { renderGrid, renderPaginationControls, showToastAlert, addToWatchlist, removeFromWatchlist, addToHistory, renderSavedTabs, getStoredList } from './ui.js';

let manifest = null;
let currentTab = 'home'; // home, play, dub, saved
let activeCategory = 'play';
let currentPageNum = 1;
let currentLoadedChunk = [];
let searchQuery = '';
let activeMovieState = null;

const WATCHLIST_KEY = 'jash_watchlist_v2';

async function bootstrap() {
  const thm = localStorage.getItem('jash-theme_v2') || 'dark';
  document.documentElement.setAttribute('data-theme', thm);
  const themeBtnIcon = document.querySelector('#themeBtn i');
  if (themeBtnIcon) themeBtnIcon.className = thm === 'light' ? 'fas fa-sun' : (thm === 'oled' ? 'fas fa-circle' : 'fas fa-moon');

  try {
    manifest = await loadManifest();
    const searchIdx = await loadSearchIndex();
    setSearchIndex(searchIdx);

    // Populate dynamic years & genres
    populateFilterSelects();

    // Check query params
    const initialParams = getQueryParams();
    if (initialParams.lib && (initialParams.lib === 'play' || initialParams.lib === 'dub')) {
      activeCategory = initialParams.lib;
      currentTab = activeCategory;
    }
    if (initialParams.page) currentPageNum = initialParams.page;

    setupEventListeners();
    await switchTab(currentTab, false);

    // If direct ID in URL
    if (initialParams.id) {
      const match = searchIdx.find(m => m.id === initialParams.id || m.pts?.includes(initialParams.id));
      if (match) {
        // Fetch full chunk or mock movie object from index
        openTheatreModal({
          id: match.id,
          title: match.t,
          poster: match.p,
          rating: match.r,
          year: match.y,
          category: match.c,
          lib: match.l,
          genres: match.g,
          prints: match.pts.map(pid => ({ id: pid, title: `Part #${pid}` }))
        }, initialParams.id);
      }
    }

  } catch (err) {
    console.error("Initialization Error:", err);
    const grid = document.getElementById('moviesGrid');
    if (grid) grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1;"><div class="empty-title">Failed to Load Catalogue</div><div class="empty-desc">Check your network connection and refresh.</div></div>';
  }
}

function populateFilterSelects() {
  if (!manifest) return;
  const yrSel = document.getElementById('yearSelect');
  if (yrSel) {
    manifest.years.forEach(yr => {
      const opt = document.createElement('option');
      opt.value = yr; opt.innerText = yr;
      yrSel.appendChild(opt);
    });
  }

  const gnMenu = document.getElementById('genreMenuList');
  if (gnMenu) {
    gnMenu.innerHTML = manifest.genres.map(g => `
      <div class="genre-item">
        <input type="checkbox" id="gn-${g}" value="${g}">
        <label for="gn-${g}">${g}</label>
      </div>`).join('');
    gnMenu.querySelectorAll('input').forEach(chk => chk.addEventListener('change', triggerFilterUpdate));
  }
}

async function switchTab(tabName, resetPg = true) {
  currentTab = tabName;
  if (resetPg) currentPageNum = 1;

  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${tabName}`)?.classList.add('active');

  const feedStage = document.getElementById('feedStage');
  const savedStage = document.getElementById('savedStage');

  if (tabName === 'saved') {
    if (feedStage) feedStage.style.display = 'none';
    if (savedStage) {
      savedStage.style.display = 'block';
      savedStage.classList.add('active');
    }
    renderSavedTabs();
  } else {
    if (feedStage) feedStage.style.display = 'block';
    if (savedStage) {
      savedStage.style.display = 'none';
      savedStage.classList.remove('active');
    }
    if (tabName === 'play' || tabName === 'dub') { activeCategory = tabName; }
    
    const hero = document.getElementById('heroBanner');
    if (hero) hero.style.display = tabName === 'home' ? 'flex' : 'none';

    await fetchAndRenderFeed();
  }
}

async function fetchAndRenderFeed() {
  const countBadge = document.getElementById('statsCountBadge');
  if (countBadge) countBadge.innerText = 'Loading catalogue...';

  if (searchQuery || isFilterActive()) {
    // Client side fuzzy filter
    const filters = getActiveFilters();
    const results = searchTitles(searchQuery, {
      ...filters,
      lib: currentTab === 'home' ? null : activeCategory
    });
    
    renderGrid('moviesGrid', results.map(item => ({
      id: item.id, title: item.t, poster: item.p, rating: item.r, year: item.y, lib: item.l, genres: item.g
    })));
    if (countBadge) countBadge.innerText = `🎬 ${results.length} Titles Found`;
    document.getElementById('paginationControls').innerHTML = '';
  } else {
    // Load static paginated chunk from Vercel CDN
    const targetCat = currentTab === 'home' ? 'play' : activeCategory;
    try {
      currentLoadedChunk = await loadCategoryPage(targetCat, currentPageNum);
      renderGrid('moviesGrid', currentLoadedChunk);
      
      const totalPgs = targetCat === 'play' ? manifest.stats.play_pages : manifest.stats.dub_pages;
      renderPaginationControls('paginationControls', currentPageNum, totalPgs, (nextPg) => {
        currentPageNum = nextPg;
        updateUrlState({ lib: targetCat, page: currentPageNum });
        fetchAndRenderFeed();
        window.scrollTo({ top: 320, behavior: 'smooth' });
      });

      if (countBadge) countBadge.innerText = `🎬 Page ${currentPageNum} of ${totalPgs}`;
    } catch (e) {
      console.error("Chunk Error:", e);
    }
  }

  attachCardClickHandlers();
}

function attachCardClickHandlers() {
  document.querySelectorAll('#moviesGrid .movie-card, #watchlistGrid .movie-card, #historyGrid .movie-card').forEach(card => {
    card.addEventListener('click', () => {
      const cid = card.getAttribute('data-id');
      const clib = card.getAttribute('data-lib');
      const found = currentLoadedChunk.find(m => m.id === cid) || { id: cid, title: card.querySelector('.card-title')?.innerText || 'Movie', lib: clib };
      openTheatreModal(found, cid);
    });
  });
}

function openTheatreModal(movie, targetPrintId = null) {
  activeMovieState = movie;
  const modal = document.getElementById('theatreModal');
  if (modal) modal.classList.add('active');
  document.body.style.overflow = 'hidden';

  const selectedPid = initTheatre(movie, targetPrintId);
  addToHistory(movie);

  const titleEl = document.getElementById('modalPlayingTitle');
  const idEl = document.getElementById('modalPlayingId');
  if (titleEl) titleEl.innerText = movie.title;
  if (idEl) idEl.innerText = `STREAM #${selectedPid}`;

  // Metadata
  const pImg = document.getElementById('metaPosterImg');
  if (pImg) pImg.src = movie.poster || '';
  document.getElementById('metaTitle').innerText = movie.title;
  document.getElementById('metaPlot').innerText = movie.plot || 'No synopsis available.';
  
  document.getElementById('metaTags').innerHTML = `
    <span class="badge badge-accent">${movie.lib === 'play' ? 'Tamil' : 'Dubbed'}</span>
    <span class="badge badge-surface">${movie.category || 'Movie'}</span>
    ${movie.rating ? `<span class="badge badge-gold">⭐ ${movie.rating}</span>` : ''}`;

  document.getElementById('metaGrid').innerHTML = `
    <div><span>Director</span><strong>${movie.director || 'N/A'}</strong></div>
    <div><span>Cast & Actors</span><strong>${movie.actors || 'N/A'}</strong></div>
    <div><span>Genres</span><strong>${movie.genres || 'General'}</strong></div>
    <div><span>Runtime</span><strong>${movie.runtime || 'N/A'}</strong></div>
    <div><span>Release Date</span><strong>${movie.released || movie.year || 'N/A'}</strong></div>`;

  // Episodes strip
  const epStrip = document.getElementById('episodesStrip');
  const epList = document.getElementById('episodesList');
  const pts = movie.prints || [];

  if (pts.length > 1 && epStrip && epList) {
    epStrip.classList.add('active');
    epList.innerHTML = pts.map(p => `
      <div class="ep-card${p.id === selectedPid ? ' active' : ''}" data-epid="${p.id}">
        <div class="ep-title">${p.title}</div>
        <div class="ep-id">#${p.id}</div>
      </div>`).join('');
    epList.querySelectorAll('.ep-card').forEach(c => {
      c.addEventListener('click', () => {
        const epid = c.getAttribute('data-epid');
        switchEpisode(epid);
        epList.querySelectorAll('.ep-card').forEach(x => x.classList.remove('active'));
        c.classList.add('active');
        if (idEl) idEl.innerText = `STREAM #${epid}`;
        updateUrlState({ lib: movie.lib, id: epid });
      });
    });
  } else if (epStrip) {
    epStrip.classList.remove('active');
  }

  updateUrlState({ lib: movie.lib, id: selectedPid });
  updateWatchlistBtnUI();
}

function updateWatchlistBtnUI() {
  if (!activeMovieState) return;
  const list = getStoredList(WATCHLIST_KEY);
  const isSaved = list.some(item => item.id === activeMovieState.id);
  const btn = document.getElementById('modalWatchlistBtn');
  if (btn) {
    btn.classList.toggle('active', isSaved);
    btn.innerHTML = isSaved ? '<i class="fas fa-check"></i> In Watchlist' : '<i class="fas fa-bookmark"></i> Watchlist';
  }
}

function isFilterActive() {
  const yr = document.getElementById('yearSelect')?.value || 'all';
  const checked = document.querySelectorAll('#genreMenuList input:checked');
  return yr !== 'all' || checked.length > 0;
}

function getActiveFilters() {
  return {
    year: document.getElementById('yearSelect')?.value || 'all',
    genres: Array.from(document.querySelectorAll('#genreMenuList input:checked')).map(c => c.value)
  };
}

function triggerFilterUpdate() {
  currentPageNum = 1;
  fetchAndRenderFeed();
}

function setupEventListeners() {
  document.getElementById('tab-home')?.addEventListener('click', () => switchTab('home'));
  document.getElementById('tab-play')?.addEventListener('click', () => switchTab('play'));
  document.getElementById('tab-dub')?.addEventListener('click', () => switchTab('dub'));
  document.getElementById('tab-saved')?.addEventListener('click', () => switchTab('saved'));

  document.getElementById('searchInput')?.addEventListener('input', (e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    const clr = document.getElementById('clearSearchBtn');
    if (clr) clr.style.display = searchQuery ? 'block' : 'none';
    triggerFilterUpdate();
  });

  document.getElementById('clearSearchBtn')?.addEventListener('click', () => {
    const inp = document.getElementById('searchInput');
    if (inp) inp.value = '';
    searchQuery = '';
    document.getElementById('clearSearchBtn').style.display = 'none';
    triggerFilterUpdate();
  });

  document.getElementById('yearSelect')?.addEventListener('change', triggerFilterUpdate);
  document.getElementById('sortSelect')?.addEventListener('change', triggerFilterUpdate);

  // Theme cycle
  document.getElementById('themeBtn')?.addEventListener('click', () => {
    const thms = ['dark', 'oled', 'light'];
    const curr = document.documentElement.getAttribute('data-theme') || 'dark';
    const nxt = thms[(thms.indexOf(curr) + 1) % thms.length];
    document.documentElement.setAttribute('data-theme', nxt);
    localStorage.setItem('jash-theme_v2', nxt);
    const icn = document.querySelector('#themeBtn i');
    if (icn) icn.className = nxt === 'light' ? 'fas fa-sun' : (nxt === 'oled' ? 'fas fa-circle' : 'fas fa-moon');
    showToastAlert(nxt === 'light' ? '☀️ Daylight Mode' : (nxt === 'oled' ? '⬛ OLED Black' : '🌙 Cinema Night'));
  });

  // Theatre controls
  document.querySelector('.btn-back')?.addEventListener('click', () => {
    document.getElementById('theatreModal')?.classList.remove('active');
    document.body.style.overflow = 'auto';
    closePlayer();
    updateUrlState({ lib: activeCategory, page: currentPageNum });
  });

  document.getElementById('lightsBtn')?.addEventListener('click', () => {
    const stage = document.getElementById('theatreStageArea');
    const btn = document.getElementById('lightsBtn');
    const isOff = btn?.classList.toggle('active');
    if (stage) stage.style.background = isOff ? '#000' : 'transparent';
    if (btn) btn.innerHTML = isOff ? '<i class="fas fa-lightbulb"></i> Lights On' : '<i class="fas fa-lightbulb"></i> Lights Off';
  });

  document.getElementById('widescreenBtn')?.addEventListener('click', () => {
    document.getElementById('playerContainer')?.classList.toggle('widescreen');
    document.getElementById('widescreenBtn')?.classList.toggle('active');
  });

  document.getElementById('serverSelect')?.addEventListener('change', (e) => changeServerMode(e.target.value));
  
  document.getElementById('modalWatchlistBtn')?.addEventListener('click', () => {
    if (!activeMovieState) return;
    const list = getStoredList(WATCHLIST_KEY);
    if (list.some(item => item.id === activeMovieState.id)) {
      removeFromWatchlist(activeMovieState.id);
    } else {
      addToWatchlist(activeMovieState);
    }
    updateWatchlistBtnUI();
  });

  // Clear watchlist / history buttons
  document.querySelector('#savedStage .section-head button[onclick="clearWatchlist()"]')?.addEventListener('click', () => {
    localStorage.removeItem(WATCHLIST_KEY);
    renderSavedTabs();
    showToastAlert('🗑️ Watchlist Cleared');
  });
  document.querySelector('#savedStage .section-head button[onclick="clearHistory()"]')?.addEventListener('click', () => {
    localStorage.removeItem('jash_history_v2');
    renderSavedTabs();
    showToastAlert('🗑️ History Cleared');
  });
}

document.addEventListener('DOMContentLoaded', bootstrap);
