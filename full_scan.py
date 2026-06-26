#!/usr/bin/env python3
"""
full_scan.py — Full OneStream ID Scanner

Scans ALL OneStream IDs to discover movies across two databases:
  - Tamil:  https://play.onestream.today/stream/page/{id}   (IDs 1–100343, skip 51307–98250)
  - Dubbed: https://dub.onestream.today/stream/video/{id}    (IDs 1–120221)

Designed for GitHub Actions with batch processing and resume-safe operation.

Usage:
    python full_scan.py [--batch-size N]

The GitHub Actions workflow loops this script, committing between batches.
"""

import json
import os
import re
import sys
import time
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = "data"
MOVIES_FILE = os.path.join(DATA_DIR, "movies.json")
MOVIES_DUB_FILE = os.path.join(DATA_DIR, "movies_dub.json")
EMPTY_PLAY_FILE = os.path.join(DATA_DIR, "empty_play.json")
EMPTY_DUB_FILE = os.path.join(DATA_DIR, "empty_dub.json")
TRACKING_FILE = os.path.join(DATA_DIR, "tracking.json")

MAX_WORKERS = 20
PROGRESS_INTERVAL = 500

DATABASES = {
    "play": {
        "base_url": "https://play.onestream.today",
        "route": "/stream/page/{id}",
        "max_id": 100343,
        "dead_zone": (51307, 98250),
        "movies_file": MOVIES_FILE,
        "empty_file": EMPTY_PLAY_FILE,
        "tracking_key": "last_play_id",
    },
    "dub": {
        "base_url": "https://dub.onestream.today",
        "route": "/stream/video/{id}",
        "max_id": 120221,
        "dead_zone": None,
        "movies_file": MOVIES_DUB_FILE,
        "empty_file": EMPTY_DUB_FILE,
        "tracking_key": "last_dub_id",
    },
}

# Title patterns to strip
TITLE_STRIP_PATTERNS = [
    re.compile(r"Moviesda\.\S+\s*-\s*", re.IGNORECASE),
    re.compile(r"\s*-\s*OneStream", re.IGNORECASE),
    re.compile(r"\s*\|\s*OneStream", re.IGNORECASE),
]

JUNK_TITLES = {"onestream", "home", "404", "error", "video player"}

QUALITY_TAGS = re.compile(
    r"\(.*?\)|1080p|720p|480p|360p|HD|HQ|PreDVD|Original|Remastered|mp4|sample",
    re.IGNORECASE,
)

SERIES_PATTERN = re.compile(r"season|episode|epi|s\d+e\d+", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_json(path: str, default=None):
    """Load a JSON file, returning *default* on any error."""
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, (dict, list)) else default
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to load %s: %s — using default", path, exc)
        return default


def save_json(data, path: str):
    """Atomically save JSON (write-tmp + rename)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        # On Windows, os.replace handles atomic overwrites
        os.replace(tmp_path, path)
    except OSError as exc:
        log.error("Failed to save %s: %s", path, exc)
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def clean_title(raw_title: str) -> str:
    """Remove site branding from a raw HTML title."""
    title = raw_title
    for pat in TITLE_STRIP_PATTERNS:
        title = pat.sub("", title)
    return title.strip()


def is_junk_title(title: str) -> bool:
    """Return True if the title is empty, a known junk string, or too short."""
    if not title or title.lower() in JUNK_TITLES:
        return True
    cleaned = QUALITY_TAGS.sub("", title).strip()
    return len(cleaned) < 2


def extract_metadata(title: str) -> dict:
    """Extract year and category from the title using regex only."""
    year_match = YEAR_PATTERN.search(title)
    year = year_match.group(1) if year_match else "Unknown"
    category = "Series" if SERIES_PATTERN.search(title) else "Movie"
    return {"year": year, "category": category}


# ---------------------------------------------------------------------------
# Core scanning logic
# ---------------------------------------------------------------------------


def check_id(session: requests.Session, movie_id: int, base_url: str, route: str):
    """
    Check a single OneStream ID.

    Returns:
        dict   — movie data if the page has a valid title
        None   — page is empty / not found
        'rate_limited' — server responded with 423/429/403
    """
    url = base_url + route.format(id=movie_id)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        resp = session.get(url, timeout=8, headers=headers)
    except requests.RequestException:
        return None

    # Rate-limit detection
    if resp.status_code in (423, 429, 403):
        return "rate_limited"

    if resp.status_code != 200:
        return None

    text = resp.text
    if "Video not found" in text or "File Not Found" in text or "The video player code provided" in text:
        return None

    # Extract <title> via regex (avoid heavy HTML parser dependency)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    raw_title = title_match.group(1).strip() if title_match else ""
    title = clean_title(raw_title)

    if is_junk_title(title):
        return None

    meta = extract_metadata(title)
    return {
        "title": title,
        "year": meta["year"],
        "category": meta["category"],
        "poster": None,
        "rating": None,
        "genres": None,
    }


def check_id_with_retry(session: requests.Session, movie_id: int, base_url: str, route: str):
    """Wrapper that retries once on rate-limit after a 5-second pause."""
    result = check_id(session, movie_id, base_url, route)
    if result == "rate_limited":
        log.info("Rate limited on ID %d — pausing 5s and retrying…", movie_id)
        time.sleep(5)
        result = check_id(session, movie_id, base_url, route)
    return result


# ---------------------------------------------------------------------------
# Database scanner
# ---------------------------------------------------------------------------


def scan_database(db_name: str, cfg: dict, batch_size: int):
    """
    Scan a single OneStream database (play or dub).

    Returns:
        (movies_db, empty_set, highest_scanned_id, rate_limited_flag)
    """
    movies_db = load_json(cfg["movies_file"])
    empty_list = load_json(cfg["empty_file"], default=[])
    empty_set = set(empty_list) if isinstance(empty_list, list) else set()
    tracking = load_json(TRACKING_FILE)

    base_url = cfg["base_url"]
    route = cfg["route"]
    max_id = cfg["max_id"]
    dead_zone = cfg["dead_zone"]
    tracking_key = cfg["tracking_key"]

    # Determine the range of IDs to scan
    last_scanned = tracking.get(tracking_key, 0)
    start_id = last_scanned + 1 if last_scanned > 0 else 1

    log.info(
        "═══════════════════════════════════════════════════════════════"
    )
    log.info("Scanning %s: %s", db_name.upper(), base_url)
    log.info("Range: %d → %d  |  Batch size: %d", start_id, max_id, batch_size)
    log.info("Existing movies: %d  |  Known empty: %d", len(movies_db), len(empty_set))
    log.info(
        "═══════════════════════════════════════════════════════════════"
    )

    # Build list of IDs to scan (skip already-known and dead zone)
    ids_to_scan = []
    for mid in range(start_id, max_id + 1):
        if len(ids_to_scan) >= batch_size:
            break
        # Skip dead zone for play database
        if dead_zone and dead_zone[0] <= mid <= dead_zone[1]:
            continue
        str_mid = str(mid)
        if str_mid in movies_db or str_mid in empty_set:
            continue
        ids_to_scan.append(mid)

    if not ids_to_scan:
        log.info("No new IDs to scan for %s — all caught up!", db_name)
        return movies_db, empty_set, last_scanned, False

    log.info("IDs queued for scanning: %d", len(ids_to_scan))

    found_count = 0
    empty_count = 0
    scanned_count = 0
    rate_limited = False
    highest_scanned = last_scanned

    def worker(movie_id: int):
        """Thread worker — each thread gets its own session."""
        with requests.Session() as sess:
            return movie_id, check_id_with_retry(sess, movie_id, base_url, route)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all IDs
        future_to_id = {executor.submit(worker, mid): mid for mid in ids_to_scan}

        for future in as_completed(future_to_id):
            mid = future_to_id[future]
            try:
                _, result = future.result()
            except Exception as exc:
                log.debug("Exception scanning ID %d: %s", mid, exc)
                result = None

            scanned_count += 1

            if result == "rate_limited":
                log.warning(
                    "⚠️  Rate limited at ID %d after retry — stopping %s scan for this batch.",
                    mid,
                    db_name,
                )
                rate_limited = True
                # Cancel remaining futures
                for f in future_to_id:
                    f.cancel()
                break

            str_mid = str(mid)
            if result and isinstance(result, dict):
                movies_db[str_mid] = result
                found_count += 1
                log.debug("✅ ID %d → %s", mid, result["title"])
            else:
                empty_set.add(str_mid)
                empty_count += 1

            if mid > highest_scanned:
                highest_scanned = mid

            # Progress reporting
            if scanned_count % PROGRESS_INTERVAL == 0:
                log.info(
                    "📊 Progress [%s]: scanned %d / %d  |  found: %d  |  empty: %d",
                    db_name,
                    scanned_count,
                    len(ids_to_scan),
                    found_count,
                    empty_count,
                )

    # Update highest scanned from all IDs that were actually processed
    # (for cancelled futures, highest_scanned stays at whatever was last processed)
    if highest_scanned < last_scanned:
        highest_scanned = last_scanned

    log.info(
        "✅ %s scan complete: scanned %d  |  found: %d  |  empty: %d  |  highest ID: %d",
        db_name.upper(),
        scanned_count,
        found_count,
        empty_count,
        highest_scanned,
    )

    return movies_db, empty_set, highest_scanned, rate_limited


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Full OneStream ID scanner — discovers movies across all IDs."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Number of IDs to process per invocation (default: 5000).",
    )
    args = parser.parse_args()
    batch_size = args.batch_size

    log.info("🚀 Full scan starting — batch size: %d", batch_size)
    start_time = time.time()

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Load tracking
    tracking = load_json(TRACKING_FILE)

    # --- Scan Tamil (play) database ---
    play_db, play_empty, play_highest, play_rate_limited = scan_database(
        "play", DATABASES["play"], batch_size
    )

    # --- Scan Dubbed database ---
    dub_db, dub_empty, dub_highest, dub_rate_limited = scan_database(
        "dub", DATABASES["dub"], batch_size
    )

    # --- Update tracking ---
    tracking["last_play_id"] = play_highest
    tracking["last_dub_id"] = dub_highest
    tracking["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # --- Save everything ---
    log.info("💾 Saving databases…")
    save_json(play_db, MOVIES_FILE)
    save_json(dub_db, MOVIES_DUB_FILE)
    save_json(sorted(list(play_empty)), EMPTY_PLAY_FILE)
    save_json(sorted(list(dub_empty)), EMPTY_DUB_FILE)
    save_json(tracking, TRACKING_FILE)

    elapsed = time.time() - start_time
    log.info(
        "═══════════════════════════════════════════════════════════════"
    )
    log.info("🏁 Full scan complete in %.1fs", elapsed)
    log.info("   Tamil movies:  %d  |  Dubbed movies:  %d", len(play_db), len(dub_db))
    log.info("   Tamil empty:   %d  |  Dubbed empty:   %d", len(play_empty), len(dub_empty))
    log.info("   Tracking: play→%d  dub→%d", play_highest, dub_highest)
    log.info(
        "═══════════════════════════════════════════════════════════════"
    )

    # Exit with non-zero if rate-limited on both databases (signals CI to retry later)
    if play_rate_limited and dub_rate_limited:
        log.warning("Both databases rate-limited — exiting with code 2 for CI retry.")
        sys.exit(2)


if __name__ == "__main__":
    main()
