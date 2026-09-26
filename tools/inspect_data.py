import json
import os

base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
for f in sorted(os.listdir(base)):
    d = json.load(open(os.path.join(base, f), encoding='utf-8-sig'))
    cats = {c['id']: c['name'] for c in d.get('categories', [])}
    loc_cat = [k for k, v in cats.items() if v.lower() == 'locations']
    print(f, '| mapImage=', d.get('mapImage'), '| markers=', len(d.get('markers', [])), '| loc_cat=', loc_cat)