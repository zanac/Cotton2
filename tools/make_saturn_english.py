#!/usr/bin/env python3
"""Stage 1: rebuild the English Saturn files of Cotton 2.

usage: make_saturn_english.py DISC PATCH OUTDIR

DISC   the Japanese Saturn disc: a .cue, the Track 1 .bin (2352-byte raw
       sectors) or a 2048-byte .iso of the data track
PATCH  ss_cotton_2_eng_v0.9.zip or the Cotton2_eng_v0.9.SSP inside it
OUTDIR receives orig/ (the 26 original files) and eng/ (the same files
       with the English patch applied)

The original files are checked against the MD5 list shipped in the patch.
"""
import hashlib, io, os, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsdiff, c2lib


def open_ssp(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    if 'CHANGES._MD5' in names:
        return z
    for n in names:
        if n.upper().endswith('.SSP'):
            return zipfile.ZipFile(io.BytesIO(z.read(n)))
    raise SystemExit('no .SSP found in ' + path)


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 1
    disc, patch, out = sys.argv[1:]
    files = c2lib.load_disc(disc)
    ssp = open_ssp(patch)
    md5 = {}
    for line in ssp.read('CHANGES._MD5').decode().split():
        n, h = line.split(':')
        md5[n] = h.lower()
    for sub in ('orig', 'eng'):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    for n in sorted(md5):
        if n not in files:
            raise SystemExit('%s not on the disc' % n)
        old = files[n]
        if hashlib.md5(old).hexdigest() != md5[n]:
            raise SystemExit('%s: MD5 mismatch, not the expected disc' % n)
        new = bsdiff.apply(old, ssp.read(n + '._DFR'))
        open(os.path.join(out, 'orig', n), 'wb').write(old)
        open(os.path.join(out, 'eng', n), 'wb').write(new)
        print('  %-12s %6x -> %6x' % (n, len(old), len(new)))
    print('%d files written to %s' % (len(md5), out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
