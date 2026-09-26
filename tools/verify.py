import json, os
import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
SOURCE = os.path.join(BASE, 'maps', 'source')
OUT = os.path.join(BASE, 'maps', 'improved')

# count location markers per sector
for f in sorted(os.listdir(DATA)):
    d = json.load(open(os.path.join(DATA, f), encoding='utf-8-sig'))
    cats = {c['id']: c['name'].strip().lower() for c in d.get('categories', [])}
    loc_cat = [k for k, v in cats.items() if v == 'locations']
    n = 0
    if loc_cat:
        n = sum(1 for m in d.get('markers', []) if m.get('categoryId') == loc_cat[0])
    print(f'{f}: location markers = {n}')

print()
# quality comparison: source vs better
for f in sorted(os.listdir(SOURCE)):
    if not f.endswith('.png'):
        continue
    sector = f.replace('_blueprint.png', '').replace('_blueprint_original.png', '')
    src = np.asarray(Image.open(os.path.join(SOURCE, f)).convert('RGB'))
    better_file = os.path.join(OUT, sector + '_better.png')
    if not os.path.exists(better_file):
        continue
    btr = np.asarray(Image.open(better_file).convert('RGB'))
    print(f'{sector}: src mean={src.mean():.1f} std={src.std():.1f} -> better mean={btr.mean():.1f} std={btr.std():.1f}')