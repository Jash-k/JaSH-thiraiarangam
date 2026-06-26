import json
import requests
import os
import re
import time
from bs4 import BeautifulSoup

TRACKING_FILE = 'data/tracking.json'
MOVIES_FILE = 'data/movies.json'
DUB_FILE = 'data/movies_dub.json'
EMPTY_PLAY_FILE = 'data/empty_play.json'
EMPTY_DUB_FILE = 'data/empty_dub.json'

OMDB_API_KEY = "28288dd3"

IS_MANUAL_RUN = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

if IS_MANUAL_RUN:
    print("🚀 MANUAL MODE: Extended scan")
    DISCOVERY_TARGET = 1000
    MAX_EMPTY_GAP = 300
else:
    print("🕒 AUTO MODE: Quick 15-min scan")
    DISCOVERY_TARGET = 100
    MAX_EMPTY_GAP = 100


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return default
    return default


def save_json(data, path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_metadata(session, title):
    """Get category, year, poster, rating, and genres from OMDB, with regex fallbacks."""
    search = re.sub(
        r'\(.*?\)|1080p|720p|360p|HD|HQ|PreDVD|Original|Remastered|Moviesda.*',
        '', title, flags=re.IGNORECASE
    ).strip()
    year = re.search(r'\b(19\d{2}|20\d{2})\b', title)
    year = year.group(1) if year else "Unknown"
    try:
        res = session.get(
            f"http://www.omdbapi.com/?t={search}&apikey={OMDB_API_KEY}",
            timeout=3
        ).json()
        if res.get("Response") == "True":
            poster = res.get("Poster")
            if poster == "N/A":
                poster = None
            rating = res.get("imdbRating")
            if rating == "N/A":
                rating = None
            genres = res.get("Genre")
            if genres == "N/A":
                genres = None
            return {
                "category": "Series" if res.get("Type") == "series" else "Movie",
                "year": res.get("Year")[:4] if res.get("Year") else year,
                "poster": poster,
                "rating": rating,
                "genres": genres
            }
    except:
        pass
    return {
        "category": "Series" if re.search(r'season|episode|epi|s\d+e\d+', title, re.IGNORECASE) else "Movie",
        "year": year,
        "poster": None,
        "rating": None,
        "genres": None
    }


def check_id(session, movie_id, base_url, route_type):
    """Check if an ID has any content (valid title).
    Keeps the movie even if the video source is broken/offline.
    Returns a movie dict on success, None if truly empty, or 'rate_limited' string.
    """
    url = f"{base_url}/stream/{route_type}/{movie_id}"
    try:
        r = session.get(url, timeout=4, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })

        if r.status_code in [423, 429, 403]:
            return "rate_limited"
        if r.status_code != 200:
            return None
        if "Video not found" in r.text or "File Not Found" in r.text or "The video player code provided" in r.text:
            return None

        # Extract title using simple regex to avoid Bs4 where possible, fallback to Bs4
        title_match = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.IGNORECASE | re.DOTALL)
        raw_title = title_match.group(1).strip() if title_match else ""
        if not raw_title:
            soup = BeautifulSoup(r.text, 'html.parser')
            raw_title = soup.title.string if soup.title else ""
            
        title = re.sub(
            r'(?i)(Moviesda\.[a-z]+\s*-\s*| - OneStream| \| OneStream)',
            '', raw_title
        ).strip()

        if not title or title.lower() in ["onestream", "home", "404", "error", "video player"]:
            return None

        # Junk title filter (keep only if title has actual content)
        cleaned = re.sub(
            r'\(.*?\)|mp4|hd|sample|hq|1080p|720p|480p|360p|original|remastered',
            '', title, flags=re.IGNORECASE
        ).strip()
        if len(cleaned) < 2:
            return None

        # Return title with default empty metadata fields to avoid fetching OMDB for each print ID
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', title)
        year = year_match.group(1) if year_match else "Unknown"
        return {
            "title": title,
            "category": "Series" if re.search(r'season|episode|epi|s\d+e\d+', title, re.IGNORECASE) else "Movie",
            "year": year,
            "poster": None,
            "rating": None,
            "genres": None
        }
    except:
        return None


def scan_forward(session, tracking_key, base_url, route_type, db, tracking, empty_ids):
    """Scan forward from last known ID. Add any movie with a valid title.
    Tracks empty IDs and skips already-known empties.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    pointer = tracking[tracking_key] + 1
    discovered = 0
    consecutive_empty = 0
    max_workers = 10
    new_empties = []
    
    # dead zone skip logic for play (Tamil)
    is_play = tracking_key == "last_play_id"
    
    print(f"\n🔍 Scanning {base_url} from ID {pointer} in parallel...")
    print(f"   📋 Known empty IDs: {len(empty_ids)} (will be skipped)")
    
    empty_set = set(empty_ids)
    
    while discovered < DISCOVERY_TARGET and consecutive_empty < MAX_EMPTY_GAP:
        # Determine a batch of next unknown IDs to scan
        batch_ids = []
        curr = pointer
        while len(batch_ids) < 20:
            str_curr = str(curr)
            # Skip play database dead zone
            if is_play and 51307 <= curr <= 98250:
                curr = 98251
                continue
            if str_curr not in db and str_curr not in empty_set:
                batch_ids.append(curr)
            elif str_curr in empty_set:
                if curr > tracking[tracking_key]:
                    tracking[tracking_key] = curr
            curr += 1

        if not batch_ids:
            break
            
        batch_results = {}
        
        def worker(movie_id):
            with requests.Session() as s:
                return movie_id, check_id(s, movie_id, base_url, route_type)
                
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(worker, mid): mid for mid in batch_ids}
            for future in as_completed(futures):
                mid, res = future.result()
                batch_results[mid] = res
                
        # Process results in order to maintain tracking pointer, discovery target, and consecutive empty counts
        rate_limit_hit = False
        for mid in sorted(batch_ids):
            result = batch_results.get(mid)
            
            if mid > tracking[tracking_key]:
                tracking[tracking_key] = mid
                
            if result == "rate_limited":
                print(f"   ⚠️ Rate limited at ID {mid}. Stopping scan.")
                rate_limit_hit = True
                break
                
            str_mid = str(mid)
            if result:
                db[str_mid] = result
                discovered += 1
                consecutive_empty = 0
                print(f"   ✅ [{discovered}] ID {mid} → {result['title']}")
            else:
                consecutive_empty += 1
                new_empties.append(str_mid)
                
            if discovered >= DISCOVERY_TARGET or consecutive_empty >= MAX_EMPTY_GAP:
                break
                
        if rate_limit_hit or discovered >= DISCOVERY_TARGET or consecutive_empty >= MAX_EMPTY_GAP:
            break
            
        pointer = tracking[tracking_key] + 1
        time.sleep(0.05)

    # Append new empties
    empty_ids.extend(new_empties)
    print(f"   📊 Found: {discovered} new | Empty: {len(new_empties)} | Scanned to ID: {tracking[tracking_key]}")


def main():
    tracking = load_json(TRACKING_FILE, {"last_play_id": 0, "last_dub_id": 0})
    play_db = load_json(MOVIES_FILE, {})
    dub_db = load_json(DUB_FILE, {})

    # Load existing empty ID lists (flat arrays)
    empty_play = load_json(EMPTY_PLAY_FILE, [])
    empty_dub = load_json(EMPTY_DUB_FILE, [])

    # Self-healing: Update tracking pointer if database has higher IDs than tracking.json
    if play_db:
        max_play_id = max(int(k) for k in play_db.keys() if k.isdigit())
        if max_play_id > tracking.get("last_play_id", 0):
            print(f"🔄 Self-healing: Advancing tracking['last_play_id'] from {tracking.get('last_play_id')} to database max ID {max_play_id}")
            tracking["last_play_id"] = max_play_id

    if dub_db:
        max_dub_id = max(int(k) for k in dub_db.keys() if k.isdigit())
        if max_dub_id > tracking.get("last_dub_id", 0):
            print(f"🔄 Self-healing: Advancing tracking['last_dub_id'] from {tracking.get('last_dub_id')} to database max ID {max_dub_id}")
            tracking["last_dub_id"] = max_dub_id

    with requests.Session() as session:
        scan_forward(session, "last_play_id", "https://play.onestream.today", "page", play_db, tracking, empty_play)
        scan_forward(session, "last_dub_id", "https://dub.onestream.today", "video", dub_db, tracking, empty_dub)

    tracking["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    save_json(tracking, TRACKING_FILE)
    save_json(play_db, MOVIES_FILE)
    save_json(dub_db, DUB_FILE)
    save_json(sorted(list(set(empty_play)), key=int), EMPTY_PLAY_FILE)
    save_json(sorted(list(set(empty_dub)), key=int), EMPTY_DUB_FILE)

    print(f"\n✅ Done! Tamil: {len(play_db)} | Dubbed: {len(dub_db)}")
    print(f"   Empty tracked: Play={len(empty_play)} | Dub={len(empty_dub)}")


if __name__ == "__main__":
    main()
