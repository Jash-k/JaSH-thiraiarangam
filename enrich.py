#!/usr/bin/env python3
"""
enrich.py — Daily OMDB Enrichment

Enriches movies that have `poster: null` with data from the OMDB API.
Processes both movies.json and movies_dub.json.

Designed to run daily on GitHub Actions, staying under the 1000/day OMDB limit.

Usage:
    python enrich.py
"""

import json
import os
import re
import time
import logging

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = "data"
MOVIES_FILE = os.path.join(DATA_DIR, "movies.json")
MOVIES_DUB_FILE = os.path.join(DATA_DIR, "movies_dub.json")

OMDB_API_KEY = "28288dd3"
OMDB_ENDPOINT = "http://www.omdbapi.com/"

# Stay safely under OMDB's 1000/day free-tier limit
MAX_LOOKUPS_PER_RUN = 950

# Patterns for cleaning titles before OMDB search
TITLE_CLEAN_PATTERNS = [
    re.compile(r"\(.*?\)"),                                          # Parenthesized text
    re.compile(r"1080p|720p|480p|360p|HD|HQ|PreDVD|Original|Remastered|mp4|sample|DVDRip|DVDScr|BDRip|BluRay|WEBRip|WEB-DL|HDRip|CAMRip|HDTS|HDTC|TC|TS|LQ", re.IGNORECASE),
    re.compile(r"Moviesda\.\S+\s*-\s*", re.IGNORECASE),            # Moviesda.xxx -
    re.compile(r"isaiDub\.\S+\s*-\s*", re.IGNORECASE),             # isaiDub.xxx -
    re.compile(r"isaimini\.\S+\s*-\s*", re.IGNORECASE),            # isaimini.xxx -
    re.compile(r"tamilyogi\.\S+\s*-\s*", re.IGNORECASE),           # TamilYogi.xxx -
    re.compile(r"\s*-\s*OneStream\b", re.IGNORECASE),               # - OneStream
    re.compile(r"\s*\|\s*OneStream\b", re.IGNORECASE),              # | OneStream
    re.compile(r"\bPart[-\s]*\d+", re.IGNORECASE),                  # Part-1, Part 2
    re.compile(r"\bSingle\s+Part\b", re.IGNORECASE),                # Single Part
    re.compile(r"\bSeason[-\s]*\d+", re.IGNORECASE),                # Season-1, Season 2
    re.compile(r"\bS\d+\s*E\d+", re.IGNORECASE),                   # S01E02 format
    re.compile(r"\bEp(?:isode)?[-.\s]*\d+", re.IGNORECASE),        # Episode 1, Ep.2
    re.compile(r"\bVol(?:ume)?[-.\s]*\d+", re.IGNORECASE),         # Volume 1, Vol.2
    re.compile(r"\bx264\b|\bHEVC\b|\bAAC\b|\bDD5\.1\b|\b10bit\b", re.IGNORECASE),
    re.compile(r"\b(?:Tamil|Telugu|Hindi|Malayalam|Kannada)\s+(?:Dubbed?|Movies?)\b", re.IGNORECASE),
    re.compile(r"_"),                                                # Underscores to spaces
]

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
            return data if isinstance(data, dict) else default
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
        os.replace(tmp_path, path)
    except OSError as exc:
        log.error("Failed to save %s: %s", path, exc)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def clean_title_for_search(title: str) -> str:
    """
    Strip site branding, quality tags, part numbers, and parenthesized text
    to produce a clean movie name for OMDB search.
    """
    cleaned = title
    for pat in TITLE_CLEAN_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    # Collapse whitespace and strip
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Remove trailing year if it's the last token (OMDB handles year separately)
    cleaned = re.sub(r"\s+\d{4}\s*$", "", cleaned).strip()
    # Remove trailing dash/pipe artifacts
    cleaned = re.sub(r"\s*[-|]+\s*$", "", cleaned).strip()
    return cleaned


def omdb_value(val):
    """Return None if OMDB returned 'N/A', else the value."""
    return None if val in (None, "N/A", "") else val


# ---------------------------------------------------------------------------
# OMDB lookup
# ---------------------------------------------------------------------------


def fetch_omdb(session: requests.Session, search_title: str) -> dict | None:
    """
    Query OMDB for a title. Returns parsed fields or None on failure.
    """
    try:
        resp = session.get(
            OMDB_ENDPOINT,
            params={"t": search_title, "apikey": OMDB_API_KEY},
            timeout=5,
        )
        if resp.status_code != 200:
            log.debug("OMDB returned status %d for '%s'", resp.status_code, search_title)
            return None

        data = resp.json()
        if data.get("Response") != "True":
            log.debug("OMDB: no match for '%s'", search_title)
            return None

        return {
            "poster": omdb_value(data.get("Poster")),
            "rating": omdb_value(data.get("imdbRating")),
            "genres": omdb_value(data.get("Genre")),
            "year": omdb_value(data.get("Year")),
            "type": data.get("Type", "").lower(),
            "plot": omdb_value(data.get("Plot")),
            "director": omdb_value(data.get("Director")),
            "writer": omdb_value(data.get("Writer")),
            "actors": omdb_value(data.get("Actors")),
            "runtime": omdb_value(data.get("Runtime")),
            "released": omdb_value(data.get("Released")),
            "rated": omdb_value(data.get("Rated")),
            "language": omdb_value(data.get("Language")),
            "country": omdb_value(data.get("Country")),
            "imdb_votes": omdb_value(data.get("imdbVotes")),
            "imdb_id": omdb_value(data.get("imdbID")),
        }
    except requests.RequestException as exc:
        log.warning("OMDB request failed for '%s': %s", search_title, exc)
        return None
    except (ValueError, KeyError) as exc:
        log.warning("OMDB response parse error for '%s': %s", search_title, exc)
        return None


# ---------------------------------------------------------------------------
# Enrichment logic
# ---------------------------------------------------------------------------


def build_title_groups(db: dict) -> dict:
    """
    Group ALL movie entries by cleaned title.

    Returns:
        {clean_title: [(movie_id, entry), ...]}
    """
    groups = {}
    for movie_id, entry in db.items():
        raw_title = entry.get("title", "")
        clean = clean_title_for_search(raw_title)
        if not clean or len(clean) < 2:
            continue
        groups.setdefault(clean, []).append((movie_id, entry))
    return groups


def enrich_database(session: requests.Session, db: dict, db_name: str, budget: int) -> int:
    """
    Enrich ONLY the parent card for each group.
    Ensures child cards have poster: None.

    Args:
        session:  requests session for OMDB
        db:       movie database dict (modified in-place)
        db_name:  human-readable name for logging
        budget:   maximum number of OMDB lookups allowed

    Returns:
        Number of OMDB lookups consumed.
    """
    title_groups = build_title_groups(db)
    
    # Identify which groups need OMDB lookups and clear posters for child entries
    lookups_todo = {}
    for clean_title, entries in title_groups.items():
        # Sort entries by ID descending (highest ID first)
        sorted_entries = sorted(entries, key=lambda x: int(x[0]), reverse=True)
        parent_id, parent_entry = sorted_entries[0]
        
        # Clear posters for all child entries
        for child_id, child_entry in sorted_entries[1:]:
            if child_entry.get("poster") is not None:
                child_entry["poster"] = None
        
        # Check if parent entry needs enrichment (missing poster or core metadata fields like plot, director, actors)
        has_metadata = all(parent_entry.get(f) is not None for f in ["plot", "director", "actors"])
        if parent_entry.get("poster") is None or not has_metadata:
            lookups_todo[clean_title] = sorted_entries
            
    unenriched_titles = len(lookups_todo)

    log.info(
        "═══════════════════════════════════════════════════════════════"
    )
    log.info("Enriching %s", db_name)
    log.info("Parent cards needing OMDB enrichment: %d unique titles", unenriched_titles)
    log.info("OMDB budget for this database: %d lookups", budget)
    log.info(
        "═══════════════════════════════════════════════════════════════"
    )

    lookups = 0
    enriched_entries = 0
    missed_titles = 0

    for clean_title, entries in lookups_todo.items():
        if lookups >= budget:
            log.info("Budget exhausted (%d lookups used). Stopping.", lookups)
            break

        omdb_data = fetch_omdb(session, clean_title)
        lookups += 1

        if omdb_data is None:
            missed_titles += 1
            log.debug("No OMDB data for '%s'", clean_title)
            continue

        # Apply OMDB data ONLY to the parent card (highest ID)
        sorted_entries = sorted(entries, key=lambda x: int(x[0]), reverse=True)
        parent_id, parent_entry = sorted_entries[0]
        
        if omdb_data["poster"]:
            parent_entry["poster"] = omdb_data["poster"]
        if omdb_data["rating"]:
            parent_entry["rating"] = omdb_data["rating"]
        if omdb_data["genres"]:
            parent_entry["genres"] = omdb_data["genres"]
        if parent_entry.get("year") == "Unknown" and omdb_data["year"]:
            parent_entry["year"] = omdb_data["year"][:4]
        if omdb_data["type"]:
            parent_entry["category"] = "Series" if omdb_data["type"] == "series" else "Movie"

        # Apply new metadata fields
        for field in ["plot", "director", "writer", "actors", "runtime", "released", "rated", "language", "country", "imdb_votes", "imdb_id"]:
            if omdb_data.get(field):
                parent_entry[field] = omdb_data[field]

        enriched_entries += 1

        if lookups % 100 == 0:
            log.info(
                "📊 Progress [%s]: %d lookups  |  %d parent entries enriched  |  %d misses",
                db_name,
                lookups,
                enriched_entries,
                missed_titles,
            )

    log.info(
        "✅ %s enrichment done: %d lookups  |  %d parent entries enriched  |  %d misses",
        db_name,
        lookups,
        enriched_entries,
        missed_titles,
    )

    return lookups


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------


def count_unenriched(db: dict) -> int:
    """Count parent entries where poster is still None."""
    groups = {}
    for movie_id, entry in db.items():
        raw_title = entry.get("title", "")
        clean = clean_title_for_search(raw_title)
        if not clean or len(clean) < 2:
            continue
        groups.setdefault(clean, []).append((movie_id, entry))
        
    count = 0
    for clean_title, entries in groups.items():
        sorted_entries = sorted(entries, key=lambda x: int(x[0]), reverse=True)
        parent_id, parent_entry = sorted_entries[0]
        has_metadata = all(parent_entry.get(f) is not None for f in ["plot", "director", "actors"])
        if parent_entry.get("poster") is None or not has_metadata:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    log.info("🚀 OMDB enrichment starting (max %d lookups/run)", MAX_LOOKUPS_PER_RUN)
    start_time = time.time()

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # --- Enrich Tamil (play) database ---
    play_db = load_json(MOVIES_FILE)
    total_play = len(play_db)
    unenriched_play_before = count_unenriched(play_db)

    with requests.Session() as session:
        play_lookups = enrich_database(
            session, play_db, "Tamil (play)", budget=MAX_LOOKUPS_PER_RUN
        )

    # Save immediately after processing play database
    save_json(play_db, MOVIES_FILE)
    log.info("💾 Saved %s (%d entries)", MOVIES_FILE, total_play)

    remaining_budget = MAX_LOOKUPS_PER_RUN - play_lookups

    # --- Enrich Dubbed database ---
    dub_db = load_json(MOVIES_DUB_FILE)
    total_dub = len(dub_db)
    unenriched_dub_before = count_unenriched(dub_db)

    if remaining_budget > 0:
        with requests.Session() as session:
            dub_lookups = enrich_database(
                session, dub_db, "Dubbed", budget=remaining_budget
            )
        # Save after processing dub database
        save_json(dub_db, MOVIES_DUB_FILE)
        log.info("💾 Saved %s (%d entries)", MOVIES_DUB_FILE, total_dub)
    else:
        dub_lookups = 0
        log.info("⏩ Skipping dubbed enrichment — no OMDB budget remaining.")

    # --- Summary ---
    unenriched_play_after = count_unenriched(play_db)
    unenriched_dub_after = count_unenriched(dub_db)
    elapsed = time.time() - start_time

    log.info(
        "═══════════════════════════════════════════════════════════════"
    )
    log.info("🏁 Enrichment complete in %.1fs", elapsed)
    log.info(
        "   OMDB lookups: %d (play: %d, dub: %d)",
        play_lookups + dub_lookups,
        play_lookups,
        dub_lookups,
    )
    log.info(
        "   Tamil:  %d/%d enriched  →  %d remaining",
        unenriched_play_before - unenriched_play_after,
        total_play,
        unenriched_play_after,
    )
    log.info(
        "   Dubbed: %d/%d enriched  →  %d remaining",
        unenriched_dub_before - unenriched_dub_after,
        total_dub,
        unenriched_dub_after,
    )
    log.info(
        "═══════════════════════════════════════════════════════════════"
    )


if __name__ == "__main__":
    main()
