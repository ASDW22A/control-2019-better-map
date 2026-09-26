#!/usr/bin/env python3
"""
make_dds.py - pure-Python PNG -> DDS converter for the Control Better Map mod.

Writes DirectDraw Surface files the game's .tex wrapper can be rebuilt from
(via neat or the user's own pipeline). Supports:

  * DXT5 / BC3  (default) - 8-bit alpha, good quality, ~2.7 MB @ 2048x1152
  * DXT1 / BC1  - no alpha, ~1.3 MB
  * BGRA8       - uncompressed, lossless, ~9 MB

Usage:
    python tools/make_dds.py input.png output.dds [--format dxt5|dxt1|bgra8]
"""

import argparse
import struct
import sys

import numpy as np

DDS_MAGIC = 0x20534444  # 'DDS '

DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSD_LINEARSIZE = 0x80000

DDPF_ALPHAPIXELS = 0x1
DDPF_FOURCC = 0x4

DDSCAPS_TEXTURE = 0x1000


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def rgb565_to_rgb(v):
    r = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    b = v & 0x1F
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def farthest_pair(colors):
    """Return indices of the two colors farthest apart (approx via mean)."""
    mean = colors.mean(axis=0)
    d = ((colors - mean) ** 2).sum(axis=1)
    i0 = int(np.argmax(d))
    d = ((colors - colors[i0]) ** 2).sum(axis=1)
    i1 = int(np.argmax(d))
    return i0, i1


def pca_endpoints(colors):
    """Return the two colors at the extremes of the principal axis (PCA fit)."""
    mean = colors.mean(axis=0)
    centered = colors - mean
    cov = centered.T @ centered
    # principal axis = eigenvector of largest eigenvalue (power iteration)
    v = np.array([1.0, 0.0, 0.0])
    for _ in range(8):
        v = cov @ v
        n = np.linalg.norm(v)
        if n < 1e-12:
            break
        v = v / n
    proj = centered @ v
    i0 = int(np.argmin(proj))
    i1 = int(np.argmax(proj))
    return i0, i1


def compress_dxt5_block(block_rgba):
    """Compress one 4x4 RGBA block (16x4 uint8) to 16 bytes DXT5."""
    out = bytearray(16)
    alpha = block_rgba[:, 3].astype(np.float32)
    rgb = block_rgba[:, :3].astype(np.float32)

    # ---- alpha block (8 bytes) ----
    a0i, a1i = farthest_pair(alpha.reshape(-1, 1))
    a0, a1 = alpha[a0i], alpha[a1i]
    if a0 > a1:
        a0, a1 = a1, a0
        swap = True
    else:
        swap = False
    if a0 == a1:
        palette = np.full(8, a0)
    else:
        if swap:
            palette = np.array([a0, a1] + [a0 + (a1 - a0) * k / 5 for k in range(1, 5)] + [0, 255])
        else:
            palette = np.array([a0, a1] + [a0 + (a1 - a0) * k / 7 for k in range(1, 7)])
    idx = np.argmin(np.abs(alpha[:, None] - palette[None, :]), axis=1)
    out[0] = int(a0)
    out[1] = int(a1)
    bits = 0
    for i in range(8):
        bits |= int(idx[i]) << (3 * i)
    out[2:8] = bits.to_bytes(6, 'little')

    # ---- color block (8 bytes) ----
    c0i, c1i = pca_endpoints(rgb)
    c0, c1 = rgb[c0i], rgb[c1i]
    c0_565 = rgb565(*c0.astype(np.uint8))
    c1_565 = rgb565(*c1.astype(np.uint8))
    if c0_565 < c1_565:
        c0_565, c1_565 = c1_565, c0_565
        swap = True
    else:
        swap = False
    if c0_565 == c1_565:
        palette = np.array([c0, c0, c0, c0])
    else:
        if swap:
            palette = np.array([c0, c1, (2 * c0 + c1) / 3, (c0 + 2 * c1) / 3])
        else:
            palette = np.array([c0, c1, (2 * c0 + c1) / 3, (c0 + 2 * c1) / 3])
    d = ((rgb[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
    idx = np.argmin(d, axis=1)
    out[8] = c0_565 & 0xFF
    out[9] = (c0_565 >> 8) & 0xFF
    out[10] = c1_565 & 0xFF
    out[11] = (c1_565 >> 8) & 0xFF
    bits = 0
    for i in range(4):
        bits |= int(idx[i]) << (2 * i)
    out[12] = bits & 0xFF
    out[13] = (bits >> 8) & 0xFF
    out[14] = 0
    out[15] = 0
    return bytes(out)


def compress_dxt1_block(block_rgb):
    """Compress one 4x4 RGB block (16x3 uint8) to 8 bytes DXT1."""
    out = bytearray(8)
    rgb = block_rgb.astype(np.float32)
    c0i, c1i = pca_endpoints(rgb)
    c0, c1 = rgb[c0i], rgb[c1i]
    c0_565 = rgb565(*c0.astype(np.uint8))
    c1_565 = rgb565(*c1.astype(np.uint8))
    if c0_565 < c1_565:
        c0_565, c1_565 = c1_565, c0_565
        swap = True
    else:
        swap = False
    if c0_565 == c1_565:
        palette = np.array([c0, c0, c0, c0])
    else:
        if swap:
            palette = np.array([c0, c1, (c0 + c1) / 2, (0, 0, 0)])
        else:
            palette = np.array([c0, c1, (2 * c0 + c1) / 3, (c0 + 2 * c1) / 3])
    d = ((rgb[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
    idx = np.argmin(d, axis=1)
    out[0] = c0_565 & 0xFF
    out[1] = (c0_565 >> 8) & 0xFF
    out[2] = c1_565 & 0xFF
    out[3] = (c1_565 >> 8) & 0xFF
    bits = 0
    for i in range(4):
        bits |= int(idx[i]) << (2 * i)
    out[4] = bits & 0xFF
    out[5] = (bits >> 8) & 0xFF
    out[6] = 0
    out[7] = 0
    return bytes(out)


def write_dds(img, path, fmt='dxt5'):
    w, h = img.size
    if w % 4 or h % 4:
        raise ValueError(f'image must be multiple of 4x4, got {w}x{h}')
    rgba = np.asarray(img.convert('RGBA'))

    if fmt == 'bgra8':
        data = rgba[:, :, [2, 1, 0, 3]].tobytes()
        fourcc = b'\0\0\0\0'
        pf_flags = DDPF_ALPHAPIXELS
        pitch = w * 4
    elif fmt == 'dxt1':
        blocks = []
        for by in range(0, h, 4):
            for bx in range(0, w, 4):
                block = rgba[by:by + 4, bx:bx + 4, :3].reshape(16, 3)
                blocks.append(compress_dxt1_block(block))
        data = b''.join(blocks)
        fourcc = b'DXT1'
        pf_flags = DDPF_FOURCC
        pitch = max(1, ((w + 3) // 4) * 8)
    elif fmt == 'dxt5':
        blocks = []
        for by in range(0, h, 4):
            for bx in range(0, w, 4):
                block = rgba[by:by + 4, bx:bx + 4].reshape(16, 4)
                blocks.append(compress_dxt5_block(block))
        data = b''.join(blocks)
        fourcc = b'DXT5'
        pf_flags = DDPF_FOURCC
        pitch = max(1, ((w + 3) // 4) * 16)
    else:
        raise ValueError(f'unknown format {fmt}')

    header = struct.pack(
        '<I7I', DDS_MAGIC, 124, pf_flags | DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE,
        h, w, pitch, 0, 0,
    )
    header += b'\0' * 44  # reserved1[11]
    # pixel format (32 bytes): size, flags, fourcc, rgbBitCount, r/g/b/a masks
    if fmt == 'bgra8':
        pf = struct.pack('<II4sIIIII', 32, pf_flags, fourcc, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    else:
        pf = struct.pack('<II4sIIIII', 32, pf_flags, fourcc, 0, 0, 0, 0, 0)
    # caps (16 bytes) + reserved2 (4 bytes)
    caps = struct.pack('<IIIII', DDSCAPS_TEXTURE, 0, 0, 0, 0)
    header += pf + caps
    with open(path, 'wb') as f:
        f.write(header)
        f.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--format', choices=['dxt5', 'dxt1', 'bgra8'], default='dxt5')
    args = ap.parse_args()

    from PIL import Image
    img = Image.open(args.input)
    write_dds(img, args.output, args.format)
    size = img.size
    print(f'OK {args.output}  {size[0]}x{size[1]}  {args.format}')


if __name__ == '__main__':
    main()