import json
import requests
import os
import re
import time
from bs4 import BeautifulSoup

MOVIES_FILE = 'data/movies.json'
DUB_FILE = 'data/movies_dub.json'
EMPTY_PLAY_FILE = 'data/empty_play.json'
EMPTY_DUB_FILE = 'data/empty_dub.json'
OMDB_API_KEY = "28288dd3"


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

        # Extract title using simple regex first, then fallback to BS4
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

        cleaned = re.sub(
            r'\(.*?\)|mp4|hd|sample|hq|1080p|720p|480p|360p|original|remastered',
            '', title, flags=re.IGNORECASE
        ).strip()
        if len(cleaned) < 2:
            return None

        return {"title": title, **get_metadata(session, title)}
    except:
        return None


def audit_and_fill(session, db, base_url, route_type, label, empty_ids, empty_file):
    """Find ALL missing IDs between first and last, scan them, fill the gaps.
    Skips confirmed-empty IDs and tracks new empties.
    """
    if not db:
        print(f"\n❌ {label}: Database is empty! Nothing to audit.")
        return

    ids = sorted([int(k) for k in db.keys()])
    first_id = ids[0]
    last_id = ids[-1]
    total_existing = len(ids)
    total_range = last_id - first_id + 1

    # Find missing IDs, excluding known empties
    id_set = set(ids)
    empty_set = set(empty_ids)
    missing = []
    skipped_empty = 0
    for i in range(first_id, last_id + 1):
        if i not in id_set:
            # Skip the known dead zone (51307 to 98250) for Tamil Movies
            if label == "TAMIL MOVIES" and 51307 <= i <= 98250:
                continue
            if str(i) in empty_set:
                skipped_empty += 1
                continue
            missing.append(i)

    # Sort descending to check most recent gaps first — scan ALL missing IDs (no limit)
    total_missing_gaps = len(missing)
    missing = sorted(missing, reverse=True)

    print(f"   Filtered Gaps: {total_missing_gaps} (excl. dead zones & {skipped_empty} known empties) | Scanning this run: {len(missing)} (latest first)")

    if not missing:
        print(f"\n   ✅ AUDIT PASSED — 100% active coverage, zero gaps!")
        return

    from concurrent.futures import ThreadPoolExecutor, as_completed

    print(f"\n   🔍 Scanning {len(missing)} missing IDs to fill gaps with 10 parallel threads...\n")

    found = 0
    empty = 0
    scanned = 0
    max_workers = 10
    new_empties = []

    def worker(movie_id):
        with requests.Session() as s:
            res = check_id(s, movie_id, base_url, route_type)
            return movie_id, res

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, mid): mid for mid in missing}
        
        for future in as_completed(futures):
            movie_id, result = future.result()

            if result == "rate_limited":
                print(f"   ⚠️ Rate limited at ID {movie_id}. Retrying after short pause...")
                time.sleep(2)
                # Retry once
                with requests.Session() as s:
                    result = check_id(s, movie_id, base_url, route_type)

            str_mid = str(movie_id)
            if result and result != "rate_limited":
                db[str_mid] = result
                found += 1
                if found <= 10 or found % 50 == 0:
                    print(f"   ✅ FOUND #{found} | ID {movie_id} → {result['title']}")
            else:
                empty += 1
                new_empties.append(str_mid)

            scanned += 1

            # Progress update every 100 IDs
            if scanned % 100 == 0:
                pct = scanned / len(missing) * 100
                print(f"   ⏳ Progress: {scanned}/{len(missing)} ({pct:.1f}%) | Found: {found} | Empty: {empty}")

            # Save progress every 500 IDs to prevent data loss
            if scanned % 500 == 0:
                if label == "TAMIL MOVIES":
                    save_json(db, MOVIES_FILE)
                else:
                    save_json(db, DUB_FILE)
                # Also save empty IDs during progress saves
                empty_ids.extend(new_empties)
                save_json(sorted(list(set(empty_ids)), key=int), empty_file)
                new_empties = []
                print(f"   💾 Auto-saved progress at {scanned} scanned IDs")

    # Merge all new empties into the empty_ids list
    empty_ids.extend(new_empties)

    # Final stats
    new_total = total_existing + found
    new_coverage = new_total / total_range * 100
    still_missing = len(missing) - found - empty  # unscanned due to rate limit

    print(f"\n   {'=' * 50}")
    print(f"   📋 AUDIT RESULTS: {label}")
    print(f"   {'=' * 50}")
    print(f"   IDs scanned     : {scanned}/{len(missing)}")
    print(f"   New IDs found   : {found}")
    print(f"   Truly empty     : {empty}")
    print(f"   New empties tracked: {len(new_empties)}")
    if still_missing > 0:
        print(f"   Not scanned yet : {still_missing} (rate limited, re-run audit)")
    print(f"   Previous total  : {total_existing}")
    print(f"   New total       : {new_total}")
    print(f"   Coverage        : {new_coverage:.2f}%")

    if new_coverage >= 99.9 and still_missing == 0:
        print(f"\n   ✅ AUDIT PASSED!")
    elif still_missing > 0:
        print(f"\n   ⚠️ AUDIT INCOMPLETE — re-run to scan remaining {still_missing} IDs")
    else:
        print(f"\n   ✅ AUDIT COMPLETE — {empty} IDs are genuinely empty (no content on server)")


def main():
    play_db = load_json(MOVIES_FILE, {})
    dub_db = load_json(DUB_FILE, {})

    # Load existing empty ID lists
    empty_play = load_json(EMPTY_PLAY_FILE, [])
    empty_dub = load_json(EMPTY_DUB_FILE, [])

    print("🔎 TAMILSTREAM CROSS-CHECK AUDIT")
    print("=" * 60)
    print("Checking every ID from first to last — zero gaps allowed.\n")

    with requests.Session() as session:
        # Audit 1: Tamil Movies
        audit_and_fill(session, play_db, "https://play.onestream.today", "page", "TAMIL MOVIES", empty_play, EMPTY_PLAY_FILE)
        save_json(play_db, MOVIES_FILE)
        save_json(sorted(list(set(empty_play)), key=int), EMPTY_PLAY_FILE)
        print(f"\n   💾 Saved {MOVIES_FILE} & {EMPTY_PLAY_FILE}")

        # Audit 2: Tamil Dubbed
        audit_and_fill(session, dub_db, "https://dub.onestream.today", "video", "TAMIL DUBBED", empty_dub, EMPTY_DUB_FILE)
        save_json(dub_db, DUB_FILE)
        save_json(sorted(list(set(empty_dub)), key=int), EMPTY_DUB_FILE)
        print(f"\n   💾 Saved {DUB_FILE} & {EMPTY_DUB_FILE}")

    print(f"\n{'=' * 60}")
    print(f"🏁 FULL AUDIT COMPLETE")
    print(f"   Tamil Movies : {len(play_db)} total IDs | {len(empty_play)} known empties")
    print(f"   Tamil Dubbed : {len(dub_db)} total IDs | {len(empty_dub)} known empties")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
