#!/usr/bin/env python3
"""Dump the 4bpp sprites of an MF container (Saturn or arcade) to a PNG sheet.
usage: spritesheet.py MF OUT.png [first] [count]"""
import sys, struct
from PIL import Image, ImageDraw
sys.path.insert(0, __import__('os').path.dirname(__file__))
import c2lib
mf = open(sys.argv[1], 'rb').read()
if mf[4:8] != b'\0\0\0\0' and mf[0x20 + 4:0x20 + 8] == b'CHR_':
    pass
subs = {n: d for n, d, s in c2lib.mf_parse(mf)}
spt = [d for n, d in subs.items() if n.endswith('.SPT')][0]
first = int(sys.argv[3]) if len(sys.argv) > 3 else 0
count = int(sys.argv[4]) if len(sys.argv) > 4 else 9999
ims = []
for k, (o, h, d) in enumerate(c2lib.spt_entries(spt)):
    if k < first or k >= first + count:
        continue
    w, hh = struct.unpack('>HH', h[4:8])
    if d[:4] == b'LZ00':
        d = c2lib.unlz(d)
    im = Image.new('L', (w, hh), 40)
    d = d[:w * hh // 2]
    if len(d) == w * hh // 2:
        px = bytearray()
        for b in d:
            px += bytes(((b >> 4) * 17, (b & 15) * 17))
        im = Image.frombytes('L', (w, hh), bytes(px))
    ims.append((k, im))
W = 1600
x = y = rowh = 0
pos = []
for k, im in ims:
    if x + im.width > W:
        x = 0; y += rowh + 12; rowh = 0
    pos.append((k, im, x, y)); x += im.width + 4; rowh = max(rowh, im.height)
out = Image.new('L', (W, y + rowh + 12), 0)
dr = ImageDraw.Draw(out)
for k, im, x, y in pos:
    out.paste(im, (x, y + 10)); dr.text((x, y), str(k), fill=255)
out.save(sys.argv[2])
