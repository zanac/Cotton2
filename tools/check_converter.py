#!/usr/bin/env python3
"""Check the Saturn -> arcade MF converter against the real arcade data.

usage: check_converter.py ROMDIR SATDIR

ROMDIR holds cotton2.zip; SATDIR is the orig/ folder written by
make_saturn_english.py. Every CHR_VS*.MF of the Saturn disc is converted
(LZ00 sprites unpacked, SCH offsets moved) and compared with the file in
the arcade cartridge. CHR_VS0/2/3/4 must come out byte-identical; the
others differ because the arcade build has different content there.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c2lib

EXPECT_SAME = ('CHR_VS0.MF', 'CHR_VS2.MF', 'CHR_VS3.MF', 'CHR_VS4.MF')


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    reg, _ = c2lib.load_cart(sys.argv[1])
    bad = 0
    for n in sorted(c2lib.ARC_MF):
        if not n.startswith('CHR_VS'):
            continue
        sat = open(os.path.join(sys.argv[2], n), 'rb').read()
        arc = c2lib.arc_file(reg, n)
        same = c2lib.to_arcade(sat, arc) == arc
        print('  %-12s %s' % (n, 'identical' if same else 'differs'))
        if n in EXPECT_SAME and not same:
            bad += 1
    print('FAIL' if bad else 'OK')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
