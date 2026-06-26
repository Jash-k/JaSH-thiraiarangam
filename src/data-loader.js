// Fetches JSON chunks asynchronously
export async function loadManifest() {
  const res = await fetch('data/manifest.json?_=' + Date.now());
  return res.json();
}

export async function loadCategoryLatest(category) {
  const res = await fetch(`data/${category}/latest.json?_=` + Date.now());
  return res.json();
}

export async function loadCategoryPage(category, pageNum) {
  const res = await fetch(`data/${category}/pages/page-${pageNum}.json?_=` + Date.now());
  return res.json();
}

export async function loadCategoryYear(category, yearStr) {
  const res = await fetch(`data/${category}/years/${yearStr}.json?_=` + Date.now());
  return res.json();
}

export async function loadSearchIndex() {
  const res = await fetch('data/search-index.json?_=' + Date.now());
  return res.json();
}
