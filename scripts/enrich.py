import os
import json
import urllib.request
import urllib.parse
import re
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TRACKING_FILE = ROOT_DIR / "data" / "tracking.json"

def clean_for_omdb(title):
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
    return ' '.join(t.split()).strip()

def fetch_omdb(title, keys, key_idx):
    if not keys:
        return None, key_idx
    curr_key = keys[key_idx]
    url = f"http://www.omdbapi.com/?t={urllib.parse.quote(title)}&apikey={curr_key}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("Response") == "False" and "limit" in data.get("Error", "").lower():
                print(f"⚠️ Key {curr_key} exhausted. Rotating...")
                key_idx = (key_idx + 1) % len(keys)
                return fetch_omdb(title, keys, key_idx)
            if data.get("Response") == "True":
                return data, key_idx
    except Exception:
        pass
    return None, key_idx

def run():
    print("--- ⭐ Enriching Titles with OMDb Metadata ---")
    raw_keys = os.environ.get("OMDB_KEYS", "28288dd3,45b3f252,e3a59ff9,6a70997d")
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    key_idx = 0

    if not TRACKING_FILE.exists():
        print("No tracking database found.")
        return

    with open(TRACKING_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)

    # Build memory cache
    cache = {}
    for cat in ["tamil_movies", "tamil_dubbed"]:
        for item in db.get(cat, []):
            if item.get("omdb") and item.get("title"):
                cache[clean_for_omdb(item["title"])] = item["omdb"]

    enriched_count = 0
    for cat in ["tamil_movies", "tamil_dubbed"]:
        for item in db.get(cat, []):
            if not item.get("omdb") and item.get("title"):
                ct = clean_for_omdb(item["title"])
                if ct in cache:
                    item["omdb"] = cache[ct]
                else:
                    omdb_data, key_idx = fetch_omdb(ct, keys, key_idx)
                    if omdb_data:
                        item["omdb"] = omdb_data
                        cache[ct] = omdb_data
                        enriched_count += 1
                        print(f"✅ Enriched #{item['id']}: {omdb_data.get('Title')}")
                    time.sleep(0.2)

    with open(TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)
    print(f"💾 Saved {enriched_count} newly enriched items to data/tracking.json")

if __name__ == "__main__":
    run()
