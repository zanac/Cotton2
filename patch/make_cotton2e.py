#!/usr/bin/env python3
"""Build cotton2e.zip (Cotton 2, English translation) from the original
cotton2 ROM set. Python 3 standard library only.

usage: make_cotton2e.py ROMDIR [OUTDIR]

ROMDIR must hold cotton2.zip (the MAME set). The result is
OUTDIR/cotton2e.zip (OUTDIR defaults to ROMDIR). The ST-V BIOS
(stvbios.zip) is needed to run it, as for cotton2.
"""
import os, sys, zipfile, zlib, lzma, struct

HERE = os.path.dirname(os.path.abspath(__file__))


def find_member(zips, crc):
    for z in zips:
        for info in z.infolist():
            if info.CRC == crc:
                return z.read(info)
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    romdir = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else romdir
    p = os.path.join(romdir, 'cotton2.zip')
    if not os.path.exists(p):
        print('cotton2.zip not found in ' + romdir)
        return 1
    zips = [zipfile.ZipFile(p)]

    patch = open(os.path.join(HERE, 'cotton2e.dat'), 'rb').read()
    assert patch[:5] == b'C2E1\0', 'bad patch file'
    o = 5
    out = []
    while o < len(patch):
        names = []
        for _ in range(2):
            n = patch[o]
            names.append(patch[o + 1:o + 1 + n].decode())
            o += 1 + n
        src_crc, dst_crc, size = struct.unpack('>III', patch[o:o + 12])
        o += 12
        xor = lzma.decompress(patch[o:o + size])
        o += size
        src = find_member(zips, src_crc)
        if src is None:
            print('%s (CRC %08x) not found in cotton2.zip' % (names[0], src_crc))
            return 1
        dst = bytes(a ^ b for a, b in zip(src, xor))
        if zlib.crc32(dst) != dst_crc:
            print('%s: wrong result' % names[1])
            return 1
        out.append((names[1], dst))

    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, 'cotton2e.zip')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in out:
            z.writestr(name, data)
    print('written ' + path)
    for name, data in out:
        print('  %-12s %08x' % (name, zlib.crc32(data)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
