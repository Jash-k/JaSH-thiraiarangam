import json, re, sys, os, requests
sys.stdout.reconfigure(encoding='utf-8')

TITLE_CLEAN_PATTERNS = [
    re.compile(r"\(.*?\)"),
    re.compile(r"1080p|720p|480p|360p|HD|HQ|PreDVD|Original|Remastered|mp4|sample|DVDRip|DVDScr|BDRip|BluRay|WEBRip|WEB-DL|HDRip|CAMRip|HDTS|HDTC|TC|TS|LQ", re.IGNORECASE),
    re.compile(r"Moviesda\.\S+\s*-\s*", re.IGNORECASE),
    re.compile(r"isaiDub\.\S+\s*-\s*", re.IGNORECASE),
    re.compile(r"isaimini\.\S+\s*-\s*", re.IGNORECASE),
    re.compile(r"tamilyogi\.\S+\s*-\s*", re.IGNORECASE),
    re.compile(r"\s*-\s*OneStream\b", re.IGNORECASE),
    re.compile(r"\s*\|\s*OneStream\b", re.IGNORECASE),
    re.compile(r"\bPart[-\s]*\d+", re.IGNORECASE),
    re.compile(r"\bSingle\s+Part\b", re.IGNORECASE),
    re.compile(r"\bSeason[-\s]*\d+", re.IGNORECASE),
    re.compile(r"\bS\d+\s*E\d+", re.IGNORECASE),
    re.compile(r"\bEp(?:isode)?[-.\s]*\d+", re.IGNORECASE),
    re.compile(r"\bVol(?:ume)?[-.\s]*\d+", re.IGNORECASE),
    re.compile(r"\bx264\b|\bHEVC\b|\bAAC\b|\bDD5\.1\b|\b10bit\b", re.IGNORECASE),
    re.compile(r"\b(?:Tamil|Telugu|Hindi|Malayalam|Kannada)\s+(?:Dubbed?|Movies?)\b", re.IGNORECASE),
    re.compile(r"_"),
]

def clean(title):
    cleaned = title
    for pat in TITLE_CLEAN_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+\d{4}\s*$", "", cleaned).strip()
    cleaned = re.sub(r"\s*[-|]+\s*$", "", cleaned).strip()
    return cleaned

d = json.load(open('data/movies.json', 'r', encoding='utf-8'))

# Show first 20 cleaned titles
print("=== TITLE CLEANING TEST ===")
seen = set()
for k, v in list(d.items())[:100]:
    raw = v.get('title', '')
    c = clean(raw)
    if c and c not in seen:
        seen.add(c)
        print(f"  '{raw}' -> '{c}'")
    if len(seen) >= 20:
        break

# Test with OMDB using NEW key
API_KEY = "28288dd3"
print(f"\n=== OMDB TEST WITH CLEANED TITLES ===")
test_raw = ["Papanasam Part-2", "Papanasam Single Part LQ", "Mooch (2015) HD DVDRip",
            "Maari Part-3", "Orange Mittai Part-1", "Selvanthan DVDScr"]
for raw in test_raw:
    c = clean(raw)
    r = requests.get(f"http://www.omdbapi.com/?t={c}&apikey={API_KEY}", timeout=5)
    data = r.json()
    if data.get("Response") == "True":
        print(f"  OK '{raw}' -> '{c}' -> {data.get('Title')} | Rating: {data.get('imdbRating')} | Poster: YES")
    else:
        print(f"  MISS '{raw}' -> '{c}' -> {data.get('Error')}")
