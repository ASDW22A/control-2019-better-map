import struct, sys
import numpy as np
from PIL import Image

def read_dds(path):
    with open(path, 'rb') as f:
        magic = struct.unpack('<I', f.read(4))[0]
        hdr = f.read(124)
        size, flags, h, w, pitch, depth, mips = struct.unpack('<7I', hdr[:28])
        pf = hdr[72:104]
        pf_size, pf_flags, fourcc = struct.unpack('<II4s', pf[:12])
        data = f.read()
    return w, h, fourcc.decode('ascii', 'replace'), data

def rgb565_to_rgb(v):
    r = (v >> 11) & 0x1F; g = (v >> 5) & 0x3F; b = v & 0x1F
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)

def decode_dxt5(data, w, h):
    out = np.zeros((h, w, 4), dtype=np.uint8)
    bw, bh = (w + 3)//4, (h + 3)//4
    for by in range(bh):
        for bx in range(bw):
            off = (by * bw + bx) * 16
            blk = data[off:off+16]
            a0, a1 = blk[0], blk[1]
            if a0 > a1:
                ap = [a0, a1] + [a0 + (a1-a0)*k//5 for k in range(1,5)] + [0, 255]
            else:
                ap = [a0, a1] + [a0 + (a1-a0)*k//7 for k in range(1,7)]
            aidx = [ (blk[2+i//8] >> (3*(i%8))) & 7 for i in range(16) ]
            c0 = rgb565_to_rgb(blk[8] | (blk[9] << 8))
            c1 = rgb565_to_rgb(blk[10] | (blk[11] << 8))
            if c0 > c1:
                cp = [c0, c1, tuple((2*np.array(c0)+np.array(c1))//3), tuple((np.array(c0)+2*np.array(c1))//3)]
            else:
                cp = [c0, c1, tuple((np.array(c0)+np.array(c1))//2), (0,0,0)]
            cidx = [ (blk[12+i//4] >> (2*(i%4))) & 3 for i in range(16) ]
            for i in range(16):
                px, py = bx*4 + i%4, by*4 + i//4
                if px < w and py < h:
                    out[py, px] = (*cp[cidx[i]], ap[aidx[i]])
    return out

w, h, fourcc, data = read_dds(sys.argv[1])
print(f'DDS: {w}x{h} {fourcc} data={len(data)} bytes')
if fourcc == 'DXT5':
    dec = decode_dxt5(data, w, h)
    src = np.asarray(Image.open(sys.argv[2]).convert('RGBA'))
    # compare only where source alpha > 0 (visible content)
    m = src[:, :, 3] > 0
    err = np.abs(dec[m].astype(int) - src[m].astype(int)).mean()
    print(f'mean abs error on visible pixels: {err:.2f} / 255')
    print(f'alpha preserved: {np.abs(dec[:,:,3].astype(int)-src[:,:,3].astype(int)).mean():.2f} / 255')