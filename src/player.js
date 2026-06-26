// Cinema theatre iframe embed management
let currentMovieState = null;
let currentPartId = null;

export function initTheatre(movie, partId = null) {
  currentMovieState = movie;
  const pts = movie.prints || [];
  currentPartId = partId || pts[0]?.id || movie.id;

  const libType = movie.lib;
  const base = libType === 'play' ? 'https://play.onestream.today' : 'https://dub.onestream.today';
  const url = libType === 'play' ? `${base}/stream/page/${currentPartId}` : `${base}/stream/video/${currentPartId}`;

  const iframe = document.getElementById('playerIframe');
  if (iframe) iframe.src = url;

  return currentPartId;
}

export function switchEpisode(newPartId) {
  if (!currentMovieState) return;
  currentPartId = newPartId;
  const libType = currentMovieState.lib;
  const base = libType === 'play' ? 'https://play.onestream.today' : 'https://dub.onestream.today';
  const url = libType === 'play' ? `${base}/stream/page/${currentPartId}` : `${base}/stream/video/${currentPartId}`;

  const iframe = document.getElementById('playerIframe');
  if (iframe) iframe.src = url;
}

export function changeServerMode(mode) {
  if (!currentMovieState || !currentPartId) return;
  const libType = currentMovieState.lib;
  const base = libType === 'play' ? 'https://play.onestream.today' : 'https://dub.onestream.today';
  const url = libType === 'play' ? `${base}/stream/page/${currentPartId}` : `${base}/stream/video/${currentPartId}`;

  const iframe = document.getElementById('playerIframe');
  if (mode === 'direct' || mode === 'reload') {
    if (iframe) iframe.src = url + (mode === 'reload' ? '?reload=' + Date.now() : '');
  } else if (mode === 'external') {
    window.open(url, '_blank');
  }
}

export function closePlayer() {
  const iframe = document.getElementById('playerIframe');
  if (iframe) iframe.src = '';
  currentMovieState = null;
  currentPartId = null;
}
