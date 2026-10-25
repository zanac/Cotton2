#!/usr/bin/env python3
"""Cotton 2 English (ST-V) - full build. Python 3 standard library only.

usage: build.py ROMDIR DISC PATCH [OUTDIR]

ROMDIR  folder with the arcade cotton2.zip
DISC    Japanese Saturn disc (.cue, Track 1 .bin or .iso)
PATCH   ss_cotton_2_eng_v0.9.zip (or the .SSP inside it)
OUTDIR  work and output folder (default: ./out)

Steps:
  1. rebuild the English Saturn files (OUTDIR/saturn/orig, OUTDIR/saturn/eng)
  2. verify the Saturn -> arcade graphics converter on the original data
  3. build the English cartridge (dialogue, continue screen hints,
     attract screens)
  4. write OUTDIR/cotton2e.zip and the patch patch/cotton2e.dat

Users who only want the ROM set do not need this: patch/make_cotton2e.py
rebuilds it from cotton2.zip alone.
"""
import os, subprocess, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import c2lib, romset, translate


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
    print('[3] English cartridge')
    reg, orig_chips = c2lib.load_cart(romdir)
    eng, log = translate.build(bytes(reg), os.path.join(sat, 'orig'), os.path.join(sat, 'eng'))
    for line in log:
        print('  ' + line)
    print('[4] ROM set and patch')
    for name, crc, data in romset.write_zip(eng, os.path.join(out, romset.SET + '.zip')):
        print('  %-12s %08x' % (name, crc))
    dat = os.path.join(HERE, 'patch', romset.SET + '.dat')
    open(dat, 'wb').write(romset.make_patch(orig_chips, eng))
    print('  written %s and %s' % (os.path.join(out, romset.SET + '.zip'), dat))
    return 0


if __name__ == '__main__':
    sys.exit(main())
