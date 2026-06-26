# JaSH திரையரங்கம் (JaSH Thiraiyarangam) 🎬

**JaSH திரையரங்கம்** is a modern, ultra-fast, Vercel-ready Tamil cinema & dubbed OTT catalogue website. It features a complete modular architecture separating static frontend assets (`src/*.js`, `styles.css`), chunked static JSON data (`data/`), Python scraper scripts (`scripts/*.py`), and automated GitHub Actions workflows.

![JaSH திரையரங்கம் Banner](https://img.shields.io/badge/JaSH_திரையரங்கம்-Tamil_OTT_Catalogue-ef3a3f?style=for-the-badge&logo=film&logoColor=white)
![Vercel Ready](https://img.shields.io/badge/Vercel-Ready-black?style=for-the-badge&logo=vercel)
![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)

---

## 📁 Complete Repository Architecture

```text
jash-thiraiarangam/
├── .github/
│   └── workflows/
│       ├── auto_updater.yml         # Daily midnight cron scraper & builder
│       ├── enrich.yml               # Manual OMDb metadata enrichment
│       ├── audit.yml                # Weekly scheduled stream & poster health audit
│       └── full_scan.yml            # Background historical deep scanner
├── data/
│   ├── manifest.json                # Global stats, carousel items, genres, years
│   ├── search-index.json            # Flat client-side instant fuzzy search index
│   ├── tracking.json                # Backend scraper master tracking database
│   ├── play/                        # Direct Tamil streams hierarchy
│   │   ├── latest.json              # Top 24 recent direct Tamil releases
│   │   ├── years/                   # Grouped by year (2026.json, 2025.json...)
│   │   └── pages/                   # Paginated chunks (page-1.json, page-2.json...)
│   └── dub/                         # Tamil Dubbed streams hierarchy
│       ├── latest.json              # Top 24 recent dubbed releases
│       ├── years/                   # Grouped by year
│       └── pages/                   # Paginated chunks
├── scripts/
│   ├── update_movies.py             # Scrapes latest endpoints (play & dub)
│   ├── enrich.py                    # Queries OMDb API with key rotation
│   ├── audit.py                     # Health checks existing links
│   ├── full_scan.py                 # Deep scan ID #1 to #50000
│   ├── build_chunks.py              # Compiles master db into static data/ hierarchy
│   └── validate_data.py             # Validates JSON schema & syntax integrity
├── src/
│   ├── app.js                       # Main SPA coordinator entry point
│   ├── data-loader.js               # Asynchronous JSON fetcher
│   ├── search.js                    # Client fuzzy search engine
│   ├── player.js                    # Iframe theatre embed & episode manager
│   ├── router.js                    # URL deep linking state manager
│   └── ui.js                        # DOM manipulation & Watchlist engine
├── index.html                       # Clean static SPA index markup
├── styles.css                       # Glassmorphism design system
├── vercel.json                      # Vercel CDN routing & edge Cache-Control
├── package.json                     # Project metadata & runner scripts
├── README.md                        # Project documentation
└── .gitignore                       # Git exclusion rules
```

---

## ✨ Architectural Highlights

### 1. ⚡ Modular Frontend (`index.html`, `styles.css`, `src/`)
- Pure ES Modules architecture. Zero runtime heavyweight JS frameworks.
- All English UI copy (except brand heading **JaSH திரையரங்கம்**).
- Features instant Dark / Daylight / OLED OLED Black theme switching.

### 2. 📦 High-Performance Static JSON Chunks (`data/`)
- Monolithic files are eliminated.
- The frontend loads lightweight paginated chunks (`pages/page-X.json`) or instant summaries (`manifest.json`), ensuring peak Web Vitals on mobile CDN networks.

### 3. 🐍 Python Scraper Suite (`scripts/*.py`)
- Standard library pure Python scripts requiring zero pip installations.
- Fast execution inside GitHub Actions runners.

---

## 🛠️ Quick Vercel Deployment

1. Fork or Clone this repository.
2. Import into [Vercel](https://vercel.com/new).
3. Select Framework Preset: **Other / Static**.
4. Click **Deploy**. Edge caching headers are automatically applied via `vercel.json`.

---

## 🔑 Automated Scraper Setup (GitHub Secrets)

To allow GitHub Actions to enrich OMDb metadata:
1. Obtain free API keys from [OMDb API](http://www.omdbapi.com/apikey.aspx).
2. In your GitHub Repo -> **Settings** -> **Secrets and variables** -> **Actions**, add a repository secret:
   - Name: `OMDB_KEYS`
   - Value: `key1,key2,key3,key4`
3. Ensure *Read and write permissions* are enabled under Workflow Permissions.

---

## 💻 Local Execution Commands

```bash
# Scrape latest daily streams
python3 scripts/update_movies.py

# Enrich titles missing OMDb details
python3 scripts/enrich.py

# Recompile static JSON chunk hierarchy
python3 scripts/build_chunks.py

# Validate JSON syntax & schema
python3 scripts/validate_data.py
```
