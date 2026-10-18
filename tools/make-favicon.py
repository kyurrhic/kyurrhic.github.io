#!/usr/bin/env python3
"""Rebuild favicon.ico as a classic BMP/DIB-based ICO (Safari-compatible).

Input : the PNG payload extracted from the old PNG-in-ICO file.
Output: favicon.ico (16x16 + 32x32 DIB entries), favicon.png (32x32 RGBA).
No third-party deps: PNG decode/encode via zlib only.
"""
import struct, sys, zlib

SRC = "/tmp/fav16.png"

def read_png(path):
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a png"
    pos, idat, w, h, depth, ctype = 8, b"", None, None, None, None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos+4])[0]
        typ = data[pos+4:pos+8]
        body = data[pos+8:pos+8+ln]
        if typ == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and ctype == 6, f"expected 8-bit RGBA, got depth={depth} ctype={ctype}"
        elif typ == b"IDAT":
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    bpp, stride = 4, w * 4
    out, prev, i = bytearray(), bytearray(stride), 0
    for _ in range(h):
        ft = raw[i]; i += 1
        line = bytearray(raw[i:i+stride]); i += stride
        if ft == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x-bpp]) & 0xFF
        elif ft == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ft == 3:
            for x in range(stride):
                a = line[x-bpp] if x >= bpp else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif ft == 4:
            for x in range(stride):
                a = line[x-bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x-bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        elif ft != 0:
            raise ValueError(f"bad filter {ft}")
        out += line
        prev = line
    return w, h, bytes(out)

def upscale2(w, h, px):
    out = bytearray(w*2*h*2*4)
    for y in range(h*2):
        for x in range(w*2):
            s = ((y//2)*w + (x//2)) * 4
            d = (y*w*2 + x) * 4
            out[d:d+4] = px[s:s+4]
    return bytes(out)

def dib(w, h, rgba):
    """BITMAPINFOHEADER + bottom-up BGRA XOR data + AND mask."""
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h*2, 1, 32, 0, len(rgba), 0, 0, 0, 0)
    xor = bytearray()
    for y in range(h-1, -1, -1):                      # bottom-up
        row = rgba[y*w*4:(y+1)*w*4]
        for x in range(w):
            r, g, b, a = row[x*4:x*4+4]
            xor += bytes((b, g, r, a))
    mask_row = ((w + 31)//32)*4                       # 1bpp, 4-byte aligned rows
    return hdr + bytes(xor) + bytes(mask_row*h)       # fully transparent handled by alpha

def ico(images, path):
    n = len(images)
    out = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16*n
    entries, blobs = b"", b""
    for w, h, rgba in images:
        d = dib(w, h, rgba)
        entries += struct.pack("<BBBBHHII", w if w < 256 else 0, h if h < 256 else 0,
                               0, 0, 1, 32, len(d), offset)
        blobs += d
        offset += len(d)
    open(path, "wb").write(out + entries + blobs)

def write_png(w, h, rgba, path):
    raw = b"".join(b"\x00" + rgba[y*w*4:(y+1)*w*4] for y in range(h))
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t+b) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    open(path, "wb").write(png)

w, h, px = read_png(SRC)
small = (w, h, px)
big = (w*2, h*2, upscale2(w, h, px))
ico([small, big], "favicon.ico")
write_png(*big, path="favicon.png")
print(f"wrote favicon.ico (16x16 + 32x32 DIB) and favicon.png (32x32) from {w}x{h} source")
