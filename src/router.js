// URL State Router
export function getQueryParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    lib: params.get('lib') || 'play',
    id: params.get('id') || null,
    cat: params.get('cat') || 'all',
    year: params.get('year') || 'all',
    page: parseInt(params.get('page') || '1', 10)
  };
}

export function updateUrlState(state = {}) {
  const params = new URLSearchParams(window.location.search);
  if (state.lib) params.set('lib', state.lib);
  if (state.id) params.set('id', state.id);
  else params.delete('id');

  if (state.page && state.page > 1) params.set('page', state.page);
  else params.delete('page');

  const newSearch = params.toString();
  const newPath = window.location.pathname + (newSearch ? '?' + newSearch : '');
  window.history.pushState(state, '', newPath);
}

export function cleanUrl() {
  window.history.pushState({}, '', window.location.pathname);
}
