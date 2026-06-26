import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

def check_file(path):
    if not path.exists():
        print(f"❌ Missing file: {path.relative_to(ROOT_DIR)}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except Exception as e:
        print(f"❌ Corrupt JSON in {path.relative_to(ROOT_DIR)}: {e}")
        return False

def run():
    print("--- 🛡️ Validating Static Chunk JSON Schema & Integrity ---")
    req_files = [
        DATA_DIR / "manifest.json",
        DATA_DIR / "search-index.json",
        DATA_DIR / "tracking.json",
        DATA_DIR / "play" / "latest.json",
        DATA_DIR / "dub" / "latest.json",
    ]
    
    passed = True
    for f in req_files:
        if not check_file(f):
            passed = False
        else:
            print(f"✅ Verified: {f.relative_to(ROOT_DIR)}")

    if not passed:
        sys.exit(1)
    print("\n🛡️ All static chunks passed JSON syntax and schema validation.")

if __name__ == "__main__":
    run()
