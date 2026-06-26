// UI Dom Rendering & Manipulation
const WATCHLIST_KEY = 'jash_watchlist_v2';
const HISTORY_KEY = 'jash_history_v2';

export function showToastAlert(text) {
  const toast = document.getElementById('toastMsg');
  const textEl = document.getElementById('toastText');
  if (textEl) textEl.innerText = text;
  if (toast) {
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
  }
}

export function createMovieCard(m) {
  const colors = ['#e50914', '#f5c14a', '#8b5cf6', '#3b82f6', '#10b981', '#ec4899'];
  const bg = colors[parseInt(m.id || 0, 10) % colors.length];
  const ini = m.title ? m.title.substring(0, 2).toUpperCase() : 'JA';
  const pts = m.prints ? m.prints.length : 1;

  return `
    <div class="movie-card" data-id="${m.id}" data-lib="${m.lib}">
      <div class="poster-box">
        <div class="fallback-avatar" style="color:${bg};">${ini}</div>
        ${m.poster ? `<img src="${m.poster}" class="poster-img" loading="lazy" alt="${m.title}" onerror="this.style.display='none'">` : ''}
        <div class="card-badges">
          <span class="card-badge new">${m.lib === 'play' ? 'Tamil' : 'Dubbed'}</span>
          ${pts > 1 ? `<span class="card-badge parts"><i class="fas fa-layer-group"></i> ${pts} Parts</span>` : ''}
        </div>
        <div class="hover-overlay">
          <div class="play-circle"><i class="fas fa-play"></i></div>
        </div>
      </div>
      <div class="card-info">
        <div class="card-title">${m.title}</div>
        <div class="card-meta">
          <span>⭐ ${m.rating || 'N/A'}</span>
          <span>${m.year || ''}</span>
        </div>
        <div class="card-genres">${m.genres || 'General'}</div>
      </div>
    </div>`;
}

export function renderGrid(containerId, list) {
  const grid = document.getElementById(containerId);
  if (!grid) return;

  if (!list || list.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1;">
        <div class="empty-icon"><i class="fas fa-search"></i></div>
        <div class="empty-title">No Titles Found</div>
        <div class="empty-desc">Try adjusting your search terms or filter selection.</div>
      </div>`;
    return;
  }

  grid.innerHTML = list.map(m => createMovieCard(m)).join('');
}

export function renderPaginationControls(containerId, currentPage, totalPages, onPageClick) {
  const ctl = document.getElementById(containerId);
  if (!ctl) return;
  if (totalPages <= 1) { ctl.innerHTML = ''; return; }

  let h = '';
  if (currentPage > 1) h += `<button class="page-btn" data-page="${currentPage - 1}"><i class="fas fa-chevron-left"></i></button>`;
  
  let s = Math.max(1, currentPage - 2), e = Math.min(totalPages, s + 4);
  if (e - s < 4) s = Math.max(1, e - 4);

  if (s > 1) h += `<button class="page-btn" data-page="1">1</button>${s > 2 ? '<span class="page-ellipsis">…</span>' : ''}`;
  for (let i = s; i <= e; i++) {
    h += `<button class="page-btn${i === currentPage ? ' active' : ''}" data-page="${i}">${i}</button>`;
  }
  if (e < totalPages) h += `${e < totalPages - 1 ? '<span class="page-ellipsis">…</span>' : ''}<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;
  if (currentPage < totalPages) h += `<button class="page-btn" data-page="${currentPage + 1}"><i class="fas fa-chevron-right"></i></button>`;

  ctl.innerHTML = h;
  ctl.querySelectorAll('.page-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const pg = parseInt(btn.getAttribute('data-page'), 10);
      if (onPageClick && pg) onPageClick(pg);
    });
  });
}

// Watchlist & History
export function getStoredList(key) {
  try { return JSON.parse(localStorage.getItem(key) || '[]'); } catch (e) { return []; }
}
export function saveStoredList(key, list) {
  localStorage.setItem(key, JSON.stringify(list));
}

export function addToWatchlist(movie) {
  if (!movie) return;
  let list = getStoredList(WATCHLIST_KEY);
  if (!list.some(item => item.id === movie.id)) {
    list.unshift(movie);
    saveStoredList(WATCHLIST_KEY, list);
    showToastAlert('🔖 Added to Watchlist');
  } else {
    showToastAlert('⚠️ Already in Watchlist');
  }
}

export function removeFromWatchlist(id) {
  let list = getStoredList(WATCHLIST_KEY);
  list = list.filter(item => item.id !== id);
  saveStoredList(WATCHLIST_KEY, list);
  showToastAlert('🗑️ Removed from Watchlist');
}

export function addToHistory(movie) {
  if (!movie) return;
  let list = getStoredList(HISTORY_KEY);
  list = list.filter(item => item.id !== movie.id);
  list.unshift(movie);
  if (list.length > 30) list.pop();
  saveStoredList(HISTORY_KEY, list);
}

export function renderSavedTabs() {
  const wList = getStoredList(WATCHLIST_KEY);
  const hList = getStoredList(HISTORY_KEY);

  const wGrid = document.getElementById('watchlistGrid');
  const hGrid = document.getElementById('historyGrid');

  if (wGrid) wGrid.innerHTML = wList.length ? wList.map(m => createMovieCard(m)).join('') : '<div class="empty-state" style="grid-column:1/-1;"><div class="empty-desc">Your watchlist is empty</div></div>';
  if (hGrid) hGrid.innerHTML = hList.length ? hList.map(m => createMovieCard(m)).join('') : '<div class="empty-state" style="grid-column:1/-1;"><div class="empty-desc">No watch history recorded</div></div>';
}
