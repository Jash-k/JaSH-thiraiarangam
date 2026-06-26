import os
import json
import re
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
LEGACY_DATA_FILE = ROOT_DIR / "data.json"
TRACKING_FILE = DATA_DIR / "tracking.json"
ITEMS_PER_PAGE = 24

def clean_title(title):
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'(isaidub|isaimini|moviesda|tamilyogi)\.[a-z]+\s*-\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*-\s*onestream', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(1080p|720p|480p|360p|hd|sample|mp4|hq|lq|predvd|original|remastered|x264|hevc|dd5\.1|aac|tc|ts|camrip|dvdrip|webrip|web-dl)\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(season|s|part|pt|ep|episode|vol|volume|chapter)[\s\-:.]*\d+', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bs\d+[\s\-:.]*e\d+\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bsingle\s*part\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(19|20)\d{2}\b', '', t)
    t = re.sub(r'[-_:]+$', '', t)
    t = re.sub(r'\s+', ' ', t).trim() if hasattr(t, 'trim') else ' '.join(t.split())
    return t

def load_tracking_db():
    if TRACKING_FILE.exists():
        with open(TRACKING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    elif LEGACY_DATA_FILE.exists():
        with open(LEGACY_DATA_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        # Save tracking file
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRACKING_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
        return db
    return {"tamil_movies": [], "tamil_dubbed": [], "last_movie_id": 2999, "last_dubbed_id": 37999}

def group_library(items, lib_type):
    valid = [i for i in (items or []) if i and i.get("omdb") and i["omdb"].get("Response") != "False"]
    groups = {}
    for item in valid:
        key = clean_title(item.get("title", "")) or str(item["id"])
        if key not in groups:
            groups[key] = []
        groups[key].append(item)

    grouped_list = []
    for key, group_items in groups.items():
        group_items.sort(key=lambda x: int(x["id"]), reverse=True)
        rep = group_items[0]
        o = rep.get("omdb", {})

        poster = o.get("Poster") if o.get("Poster") != "N/A" else ""
        rating = o.get("imdbRating") if o.get("imdbRating") != "N/A" else ""
        genres = o.get("Genre") if o.get("Genre") != "N/A" else ""
        runtime = o.get("Runtime") if o.get("Runtime") != "N/A" else ""
        released = o.get("Released") if o.get("Released") != "N/A" else ""
        year = o.get("Year")[:4] if o.get("Year") and o.get("Year") != "N/A" else "Unknown"

        # Check siblings for missing metadata
        for sib in group_items:
            so = sib.get("omdb", {})
            if not poster and so.get("Poster") and so.get("Poster") != "N/A":
                poster = so.get("Poster")
            if not rating and so.get("imdbRating") and so.get("imdbRating") != "N/A":
                rating = so.get("imdbRating")
            if not genres and so.get("Genre") and so.get("Genre") != "N/A":
                genres = so.get("Genre")
            if year == "Unknown" and so.get("Year") and so.get("Year") != "N/A":
                year = so.get("Year")[:4]

        prints = []
        for p in group_items:
            sub = p.get("title", "")
            sub = re.sub(r'(isaimini|isaidub|moviesda|tamilyogi)\.[a-z]+', '', sub, flags=re.IGNORECASE)
            sub = re.sub(r'[\s\-\|]+onestream', '', sub, flags=re.IGNORECASE).strip()
            sub = re.sub(r'^[-_:\s|]+|[-_:\s|]+$', '', sub).strip()
            if not sub:
                sub = f"Part #{p['id']}"
            prints.append({
                "id": str(p["id"]),
                "title": sub,
                "stream_url": p.get("stream_url", "")
            })

        display_title = clean_title(rep.get("title", ""))
        display_title = display_title.title() if display_title else (o.get("Title") or f"Title #{rep['id']}")

        grouped_list.append({
            "id": str(rep["id"]),
            "title": display_title,
            "raw_title": rep.get("title") or o.get("Title"),
            "poster": poster,
            "category": "Series" if o.get("Type", "").lower() == "series" else "Movie",
            "rating": rating,
            "genres": genres,
            "runtime": runtime,
            "released": released,
            "year": year,
            "plot": o.get("Plot") if o.get("Plot") != "N/A" else "",
            "director": o.get("Director") if o.get("Director") != "N/A" else "",
            "actors": o.get("Actors") if o.get("Actors") != "N/A" else "",
            "language": o.get("Language") if o.get("Language") != "N/A" else "Tamil",
            "lib": lib_type,
            "prints": prints
        })

    grouped_list.sort(key=lambda x: int(x["id"]), reverse=True)
    return grouped_list

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_category_tree(grouped_list, cat_dir):
    # 1. latest.json
    save_json(cat_dir / "latest.json", grouped_list[:ITEMS_PER_PAGE])

    # 2. years/
    years_dir = cat_dir / "years"
    years_map = {"2026": [], "2025": [], "2024": [], "older": []}
    for m in grouped_list:
        yr = m.get("year", "")
        if yr in ["2026", "2025", "2024"]:
            years_map[yr].append(m)
        else:
            years_map["older"].append(m)

    for yr_key, list_data in years_map.items():
        save_json(years_dir / f"{yr_key}.json", list_data)

    # 3. pages/
    pages_dir = cat_dir / "pages"
    total_pages = max(1, (len(grouped_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    for p in range(1, total_pages + 1):
        start = (p - 1) * ITEMS_PER_PAGE
        save_json(pages_dir / f"page-{p}.json", grouped_list[start : start + ITEMS_PER_PAGE])

    return total_pages

def run():
    print("--- 📦 Building JaSH திரையரங்கம் Modular Static JSON Chunks ---")
    db = load_tracking_db()
    
    play_list = group_library(db.get("tamil_movies", []), "play")
    dub_list = group_library(db.get("tamil_dubbed", []), "dub")

    play_pages = build_category_tree(play_list, DATA_DIR / "play")
    dub_pages = build_category_tree(dub_list, DATA_DIR / "dub")

    # Filter metadata
    genres_set = set()
    years_set = set()
    for m in play_list + dub_list:
        if m.get("genres"):
            for g in m["genres"].split(","):
                g_cl = g.strip()
                if g_cl:
                    genres_set.add(g_cl)
        yr = m.get("year", "")
        if yr and yr != "Unknown" and yr.isdigit():
            years_set.add(int(yr))

    sorted_genres = sorted(list(genres_set))
    sorted_years = sorted(list(years_set), reverse=True)

    featured = [m for m in play_list + dub_list if m.get("poster") and m.get("plot") and float(m.get("rating") or 0) >= 7.0][:12]

    manifest = {
        "brand": "JaSH திரையரங்கம்",
        "tagline": "Premium Tamil & Dubbed Cinema",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "stats": {
            "tamil_count": len(play_list),
            "dubbed_count": len(dub_list),
            "total_titles": len(play_list) + len(dub_list),
            "play_pages": play_pages,
            "dub_pages": dub_pages,
            "last_movie_id": db.get("last_movie_id", 2999),
            "last_dubbed_id": db.get("last_dubbed_id", 37999)
        },
        "genres": sorted_genres,
        "years": sorted_years,
        "featured": featured
    }
    save_json(DATA_DIR / "manifest.json", manifest)

    search_index = []
    for m in play_list + dub_list:
        search_index.append({
            "id": m["id"],
            "t": m["title"],
            "y": m["year"],
            "r": m["rating"],
            "p": m["poster"],
            "c": m["category"],
            "l": m["lib"],
            "g": m["genres"],
            "pts": [p["id"] for p in m.get("prints", [])]
        })
    save_json(DATA_DIR / "search-index.json", search_index)

    print(f"✅ Generated manifest.json ({len(featured)} featured titles)")
    print(f"✅ Generated play/ tree ({len(play_list)} titles across {play_pages} pages)")
    print(f"✅ Generated dub/ tree ({len(dub_list)} titles across {dub_pages} pages)")
    print(f"✅ Generated search-index.json ({len(search_index)} indexed titles)")

if __name__ == "__main__":
    run()
