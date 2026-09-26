#!/usr/bin/env python3
"""
rmdp_extract.py - minimal Northlight (Remedy) package extractor.

Extracts files from Control's .bin/.rmdp/.packmeta package triplets.
Format spec from profMagija/control-unpack (file_formats.md).

Usage:
    python tools/rmdp_extract.py <package-path-without-ext> -o <outdir>
"""

import argparse
import os
import struct
import sys


def read_cstring(data, off):
    end = data.index(b'\0', off)
    return data[off:end].decode('utf-8', 'replace'), end + 1


def extract(package, outdir):
    bin_path = package + '.bin'
    rmdp_path = package + '.rmdp'
    if not os.path.exists(bin_path) or not os.path.exists(rmdp_path):
        raise FileNotFoundError(f'need {bin_path} and {rmdp_path}')

    with open(bin_path, 'rb') as f:
        b = f.read()
    with open(rmdp_path, 'rb') as f:
        r = f.read()

    off = 0
    zero = b[off]; off += 1
    version, num_dirs, num_files = struct.unpack_from('<III', b, off); off += 12
    off += 0x90  # unknown_1

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

    count = 0
    for fi in files:
        name, _ = read_cstring(b, fi['name_off'])
        rel = os.path.join(dir_name(fi['parent']), name)
        dest = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        data = r[fi['content_off']:fi['content_off'] + fi['content_len']]
        with open(dest, 'wb') as f:
            f.write(data)
        count += 1
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('package', help='package path WITHOUT extension (e.g. ep100-000-generic)')
    ap.add_argument('-o', '--output', default='extracted')
    args = ap.parse_args()
    n = extract(args.package, args.output)
    print(f'extracted {n} files to {args.output}')


if __name__ == '__main__':
    main()