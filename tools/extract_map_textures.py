#!/usr/bin/env python3
"""
extract_map_textures.py - find and extract Control's in-game map textures.

Scans the game's package archives (.bin/.rmdp) for the map overlay textures
(the files the pause-menu map renders) and extracts them for inspection.

The map textures are named after sectors and live under the UI/texture
folders. This script:

  1. Locates the game's data directory (or takes --game-dir)
  2. Lists all package triplets (*.bin + *.rmdp)
  3. Searches file listings for map-like texture names
  4. Extracts matches to <outdir>/<package>/<path>

Usage:
    python tools/extract_map_textures.py [--game-dir <path>] [-o outdir]
"""

import argparse
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rmdp_extract import extract, read_cstring

# patterns that identify the map overlay textures
MAP_PATTERNS = [
    re.compile(r'map', re.I),
    re.compile(r'blueprint', re.I),
    re.compile(r'overlay', re.I),
    re.compile(r'(executive|research|maintenance|containment|foundation|investigations)', re.I),
]

COMMON_GAME_DIRS = [
    r'C:\Program Files (x86)\Steam\steamapps\common\Control',
    r'C:\Program Files\Steam\steamapps\common\Control',
    r'C:\Program Files\Epic Games\Control',
    r'C:\Program Files (x86)\Epic Games\Control',
    r'D:\SteamLibrary\steamapps\common\Control',
    r'D:\Epic Games\Control',
    r'E:\SteamLibrary\steamapps\common\Control',
    r'E:\Epic Games\Control',
]


def find_game_dir():
    for d in COMMON_GAME_DIRS:
        if os.path.isdir(d):
            return d
    return None


def list_packages(game_dir):
    """Return list of package paths (without extension) found under game_dir."""
    pkgs = set()
    for root, _, files in os.walk(game_dir):
        for f in files:
            if f.endswith('.bin'):
                base = os.path.join(root, f[:-4])
                if os.path.exists(base + '.rmdp'):
                    pkgs.add(base)
    return sorted(pkgs)


def list_files_in_package(package):
    """Return list of (rel_path, content_len) without extracting everything."""
    bin_path = package + '.bin'
    with open(bin_path, 'rb') as f:
        b = f.read()
    off = 0
    off += 1
    version, num_dirs, num_files = struct.unpack_from('<III', b, off)
    off += 12 + 0x90

    dirs = []
    for _ in range(num_dirs):
        u0, parent, u1, name_off, u2, u3, u4 = struct.unpack_from('<qqiqiqq', b, off)
        off += 48
        dirs.append({'parent': parent, 'name_off': name_off})

    files = []
    for _ in range(num_files):
        u0, parent, u1, name_off, u2, content_off, content_len = struct.unpack_from('<qqiqiqq', b, off)
        off += 48
        files.append({'parent': parent, 'name_off': name_off,
                      'content_off': content_off, 'content_len': content_len})

    def dir_name(idx):
        if idx < 0:
            return ''
        d = dirs[idx]
        name, _ = read_cstring(b, d['name_off'])
        parent = dir_name(d['parent'])
        return os.path.join(parent, name) if parent else name

    out = []
    for fi in files:
        name, _ = read_cstring(b, fi['name_off'])
        rel = os.path.join(dir_name(fi['parent']), name)
        out.append((rel, fi['content_len']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game-dir', help='Control install directory')
    ap.add_argument('-o', '--output', default='map_textures')
    args = ap.parse_args()

    game_dir = args.game_dir or find_game_dir()
    if not game_dir:
        print('ERROR: could not find Control install. Pass --game-dir <path>.')
        sys.exit(1)
    print(f'game dir: {game_dir}')

    os.makedirs(args.output, exist_ok=True)
    found = []
    for pkg in list_packages(game_dir):
        try:
            listing = list_files_in_package(pkg)
        except Exception as e:
            print(f'  skip {os.path.basename(pkg)}: {e}')
            continue
        hits = [(rel, ln) for rel, ln in listing
                if any(p.search(rel) for p in MAP_PATTERNS) and rel.lower().endswith('.tex')]
        if hits:
            print(f'  {os.path.basename(pkg)}: {len(hits)} map-like files')
            for rel, ln in hits:
                print(f'    {rel}  ({ln} bytes)')
            found.append((pkg, hits))

    if not found:
        print('No map textures found. The map files may live in a differently-named package.')
        print('Extract everything and search manually:')
        print('  python tools/rmdp_extract.py <package> -o extracted')
        sys.exit(0)

    print()
    print('Extracting matched files...')
    for pkg, hits in found:
        pkg_name = os.path.basename(pkg)
        # extract only the matched files via full extract then copy (simple + safe)
        tmp = os.path.join(args.output, pkg_name)
        extract(pkg, tmp)
        for rel, _ in hits:
            src = os.path.join(tmp, rel)
            if os.path.exists(src):
                print(f'  OK {pkg_name}/{rel}')
    print()
    print(f'Done. Inspect the .tex files with neat (TomEvin) to convert to DDS/PNG.')
    print('Then convert the matching improved texture from maps/improved/ and repack.')


if __name__ == '__main__':
    main()