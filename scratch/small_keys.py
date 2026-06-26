import json
with open('data/movies.json', 'r') as f:
    data = json.load(f)
keys = sorted([int(k) for k in data.keys()])
print("Smallest 20 keys in movies.json:")
print(keys[:20])
