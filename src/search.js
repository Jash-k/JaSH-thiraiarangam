// Client-side instant fuzzy search engine across search-index.json
let indexCache = null;

export function setSearchIndex(data) {
  indexCache = data || [];
}

export function searchTitles(query, filters = {}) {
  if (!indexCache) return [];
  const q = (query || '').trim().toLowerCase();

  return indexCache.filter(item => {
    let matchQ = true;
    if (q) {
      matchQ = item.t.toLowerCase().includes(q) ||
               item.id.includes(q) ||
               item.pts?.some(pid => pid.includes(q)) ||
               (item.g && item.g.toLowerCase().includes(q));
    }
    let matchCat = !filters.category || filters.category === 'all' || item.c === filters.category;
    let matchLib = !filters.lib || item.l === filters.lib;
    let matchYear = !filters.year || filters.year === 'all' || item.y === filters.year;
    
    let matchGenres = true;
    if (filters.genres && filters.genres.length > 0) {
      matchGenres = filters.genres.every(g => item.g && item.g.includes(g));
    }

    return matchQ && matchCat && matchLib && matchYear && matchGenres;
  });
}
