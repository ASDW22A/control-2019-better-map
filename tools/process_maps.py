#!/usr/bin/env python3
"""
Control Better Map - texture processing pipeline.

Takes the raw Control (2019) map overlay textures (extracted from the game,
hosted on the Control wiki) and produces improved variants:

  * <sector>_better.png   - contrast-boosted, sharpened, vivid version
  * <sector>_labeled.png  - better version + clean room-name labels

The in-game map is notoriously hard to read: extremely dark, low contrast,
cluttered with baked-in text. This pipeline fixes readability while keeping
the exact original dimensions (2048x1152 RGBA) so the textures can be
converted back to the game's .tex format and dropped in as loose files.

Usage:
    python tools/process_maps.py [--sector NAME] [--skip-labels]
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(BASE, 'maps', 'source')
OUT = os.path.join(BASE, 'maps', 'improved')
DATA = os.path.join(BASE, 'data')

MAP_W, MAP_H = 2048, 1152

# sector name -> (source file, data file)
SECTORS = {
    'executive':      ('executive_blueprint.png', 'executive_blueprint.json'),
    'research':       ('research_blueprint.png', 'research.json'),
    'maintenance':    ('maintenance_blueprint.png', 'maintenance.json'),
    'containment':    ('containment_blueprint.png', 'containment.json'),
    'foundation':     ('foundation_blueprint.png', 'foundation.json'),
    'investigations': ('investigations_blueprint.png', 'investigations.json'),
    'quarry':         ('quarry_blueprint.png', 'quarry.json'),
    'unmapped':       ('unmapped_blueprint.png', None),
}

FONT_CANDIDATES = [
    r'C:\Windows\Fonts\segoeui.ttf',
    r'C:\Windows\Fonts\arial.ttf',
    r'C:\Windows\Fonts\calibri.ttf',
    r'C:\Windows\Fonts\verdana.ttf',
]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def enhance(img):
    """Contrast stretch + sharpen + saturation boost + brightness lift."""
    a = np.asarray(img).astype(np.float32)
    rgb, alpha = a[:, :, :3], a[:, :, 3]

    # --- contrast stretch on visible pixels only ---
    mask = alpha > 0
    if mask.any():
        vis = rgb[mask]
        lo, hi = np.percentile(vis, 2), np.percentile(vis, 98)
        lo = max(lo, 0.0)
        hi = min(hi, 255.0)
        if hi - lo > 8:
            rgb = (rgb - lo) * (255.0 / (hi - lo))
            rgb = np.clip(rgb, 0, 255)

    # --- brightness lift (maps are extremely dark) ---
    rgb = rgb * 1.18 + 6.0
    rgb = np.clip(rgb, 0, 255)

    # --- saturation boost (teal-blue scheme) ---
    gray = rgb.mean(axis=2, keepdims=True)
    rgb = gray + (rgb - gray) * 1.35
    rgb = np.clip(rgb, 0, 255)

    out = np.dstack([rgb, alpha]).astype(np.uint8)
    im = Image.fromarray(out, 'RGBA')

    # --- unsharp mask ---
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
    return im


def load_markers(sector):
    """Return list of (name, x_img, y_img) for Locations markers."""
    data_file = SECTORS[sector][1]
    if not data_file:
        return []
    path = os.path.join(DATA, data_file)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig') as f:
        d = json.load(f)
    cats = {c['id']: c['name'].strip().lower() for c in d.get('categories', [])}
    loc_cat = [k for k, v in cats.items() if v == 'locations']
    if not loc_cat:
        return []
    loc_cat = loc_cat[0]
    out = []
    for m in d.get('markers', []):
        if m.get('categoryId') != loc_cat:
            continue
        title = (m.get('popup') or {}).get('title', '').strip()
        if not title or title.lower() in ('chest', 'chst'):
            continue
        x, y = m['position']
        # map coords: origin bottom-left -> image coords: origin top-left
        out.append((title, float(x), MAP_H - float(y)))
    return out


def draw_labels(img, markers, font_path):
    """Overlay clean room-name labels with leader lines."""
    im = img.convert('RGBA')
    draw = ImageDraw.Draw(im, 'RGBA')

    font_large = ImageFont.truetype(font_path, 30)
    font_small = ImageFont.truetype(font_path, 24)

    placed = []  # (x0, y0, x1, y1) of placed label boxes

    def overlaps(box, placed, pad=6):
        x0, y0, x1, y1 = box
        for (px0, py0, px1, py1) in placed:
            if not (x1 + pad < px0 or x0 - pad > px1 or y1 + pad < py0 or y0 - pad > py1):
                return True
        return False

    # sort by y so labels flow top-to-bottom; longer names first for priority
    markers = sorted(markers, key=lambda m: (-len(m[0]), m[2]))

    for name, mx, my in markers:
        if len(name) > 42:
            name = name[:40] + '...'
        font = font_large if len(name) <= 22 else font_small
        bbox = draw.textbbox((0, 0), name, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # try positions around the marker: right, left, above, below
        candidates = [
            (mx + 14, my - th / 2),
            (mx - tw - 14, my - th / 2),
            (mx - tw / 2, my - th - 12),
            (mx - tw / 2, my + 12),
        ]
        chosen = None
        for cx, cy in candidates:
            cx = max(4, min(cx, MAP_W - tw - 4))
            cy = max(4, min(cy, MAP_H - th - 4))
            box = (cx, cy, cx + tw, cy + th)
            if not overlaps(box, placed):
                chosen = (cx, cy)
                break
        if chosen is None:
            continue
        cx, cy = chosen
        placed.append((cx, cy, cx + tw, cy + th))

        # leader line from label to marker
        lx = cx + tw / 2
        ly = cy + th / 2
        draw.line([(lx, ly), (mx, my)], fill=(120, 200, 210, 160), width=2)

        # label background pill
        pad_x, pad_y = 8, 5
        draw.rounded_rectangle(
            [cx - pad_x, cy - pad_y, cx + tw + pad_x, cy + th + pad_y],
            radius=8, fill=(10, 18, 22, 205), outline=(90, 190, 205, 220), width=2,
        )
        # text
        draw.text((cx, cy), name, font=font, fill=(225, 245, 248, 255))

    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sector', choices=list(SECTORS), default=None)
    ap.add_argument('--skip-labels', action='store_true')
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    font_path = find_font()
    if not font_path:
        print('WARNING: no truetype font found, labels will use default bitmap font')

    sectors = [args.sector] if args.sector else list(SECTORS)
    for sector in sectors:
        src_name = SECTORS[sector][0]
        src_path = os.path.join(SOURCE, src_name)
        if not os.path.exists(src_path):
            print(f'SKIP {sector}: missing {src_path}')
            continue

        img = Image.open(src_path).convert('RGBA')
        better = enhance(img)

        better_path = os.path.join(OUT, f'{sector}_better.png')
        better.save(better_path)
        print(f'OK {sector}_better.png  {better.size}')

        if not args.skip_labels:
            markers = load_markers(sector)
            if markers:
                labeled = draw_labels(better, markers, font_path)
                labeled_path = os.path.join(OUT, f'{sector}_labeled.png')
                labeled.save(labeled_path)
                print(f'OK {sector}_labeled.png  labels={len(markers)}')
            else:
                print(f'NOTE {sector}: no location markers, skipping labeled variant')


if __name__ == '__main__':
    main()