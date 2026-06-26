import json

def inspect(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    ids = sorted([int(k) for k in data.keys()])
    print(f"File: {filepath}")
    print(f"  Count: {len(ids)}")
    print(f"  Min ID: {ids[0] if ids else None}")
    print(f"  Max ID: {ids[-1] if ids else None}")
    print(f"  First 10 IDs: {ids[:10]}")

inspect('data/movies.json')
inspect('data/movies_dub.json')
