#!/usr/bin/env python3
"""Cotton 2 English (ST-V) - build pipeline. Python 3 standard library only.

usage: build.py ROMDIR DISC PATCH [OUTDIR]

ROMDIR  folder with the arcade cotton2.zip
DISC    Japanese Saturn disc (.cue, Track 1 .bin or .iso)
PATCH   ss_cotton_2_eng_v0.9.zip (or the .SSP inside it)
OUTDIR  work and output folder (default: ./out)

Work in progress. What runs today:
  1. rebuild the English Saturn files (OUTDIR/saturn/orig, OUTDIR/saturn/eng)
  2. verify the Saturn -> arcade graphics converter on the original data
  3. convert the English CHR_VS*.MF dialogue graphics to the arcade layout
     (OUTDIR/arcade/)
The last step, writing the new ROM set, is not implemented yet: see
README.md, "Status".
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import c2lib


def run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'tools', script)] + list(args))
    if r.returncode:
        raise SystemExit('%s failed' % script)


def main():
    if len(sys.argv) not in (4, 5):
        print(__doc__)
        return 1
    romdir, disc, patch = sys.argv[1:4]
    out = sys.argv[4] if len(sys.argv) == 5 else 'out'
    sat = os.path.join(out, 'saturn')
    print('[1] English Saturn files')
    run('make_saturn_english.py', disc, patch, sat)
    print('[2] converter check')
    run('check_converter.py', romdir, os.path.join(sat, 'orig'))
    print('[3] English dialogue graphics in arcade layout')
    reg, _ = c2lib.load_cart(romdir)
    arc = os.path.join(out, 'arcade')
    os.makedirs(arc, exist_ok=True)
    for n in sorted(c2lib.ARC_MF):
        if not n.startswith('CHR_VS'):
            continue
        eng = open(os.path.join(sat, 'eng', n), 'rb').read()
        old = c2lib.arc_file(reg, n)
        new = c2lib.to_arcade(eng, old)
        open(os.path.join(arc, n), 'wb').write(new)
        print('  %-12s arcade %6x  english %6x' % (n, len(old), len(new)))
    print('[4] ROM set: not implemented yet (see README.md, Status)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
