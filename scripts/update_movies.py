import json
import urllib.request
import urllib.error
import re
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TRACKING_FILE = ROOT_DIR / "data" / "tracking.json"

BATCH_SIZE = 50 # Daily quick batch

def fetch_title(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            if m:
                return m.group(1).strip()
    except Exception:
        pass
    return None

def run():
    print("--- 🎬 Running Daily Quick Stream Scraper ---")
    if TRACKING_FILE.exists():
        with open(TRACKING_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    else:
        db = {"tamil_movies": [], "tamil_dubbed": [], "last_movie_id": 2999, "last_dubbed_id": 37999}

    last_mov = db.get("last_movie_id", 2999)
    last_dub = db.get("last_dubbed_id", 37999)

    print(f"Starting Tamil check from ID #{last_mov + 1}")
    for i in range(BATCH_SIZE):
        curr_id = last_mov + 1
        url = f"https://play.onestream.today/stream/page/{curr_id}"
        title = fetch_title(url)
        if title:
            db["tamil_movies"].append({"id": curr_id, "title": title, "stream_url": url, "omdb": None})
            print(f"✅ Found Movie #{curr_id}: {title}")
        last_mov = curr_id
        time.sleep(0.2)
    db["last_movie_id"] = last_mov

    print(f"Starting Dubbed check from ID #{last_dub + 1}")
    for i in range(BATCH_SIZE):
        curr_id = last_dub + 1
        url = f"https://dub.onestream.today/stream/video/{curr_id}"
        title = fetch_title(url)
        if title:
            db["tamil_dubbed"].append({"id": curr_id, "title": title, "stream_url": url, "omdb": None})
            print(f"✅ Found Dubbed #{curr_id}: {title}")
        last_dub = curr_id
        time.sleep(0.2)
    db["last_dubbed_id"] = last_dub

    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)
    print("💾 Scraper state saved to data/tracking.json")

if __name__ == "__main__":
    run()
