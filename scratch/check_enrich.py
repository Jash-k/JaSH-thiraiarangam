import json

d = json.load(open('data/movies.json', 'r', encoding='utf-8'))
has_poster = [k for k, v in d.items() if v.get('poster')]
has_rating = [k for k, v in d.items() if v.get('rating')]
has_genres = [k for k, v in d.items() if v.get('genres')]

print(f"Total movies: {len(d)}")
print(f"With poster:  {len(has_poster)}")
print(f"With rating:  {len(has_rating)}")
print(f"With genres:  {len(has_genres)}")

if has_poster:
    for k in has_poster[:3]:
        print(f"  Sample #{k}: poster={d[k]['poster'][:60]}...")
else:
    print("  >> NO movies have posters yet!")

# Also check dubbed
d2 = json.load(open('data/movies_dub.json', 'r', encoding='utf-8'))
has_poster2 = [k for k, v in d2.items() if v.get('poster')]
print(f"\nDubbed total: {len(d2)}")
print(f"Dubbed with poster: {len(has_poster2)}")
