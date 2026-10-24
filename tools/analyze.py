#!/usr/bin/env python3
"""Report what the English patch changes in each Saturn file.

usage: analyze.py SATDIR

SATDIR is the folder written by make_saturn_english.py (orig/ and eng/).
For MF containers it lists the changed subfiles and sprite entries; for
the VS*.BIN overlays it lists the changed byte ranges.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c2lib


def ranges(a, b, gap=4):
    g = []
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            if g and i - g[-1][1] <= gap:
                g[-1][1] = i
            else:
                g.append([i, i])
    return g


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    od, ed = (os.path.join(sys.argv[1], s) for s in ('orig', 'eng'))
    for n in sorted(os.listdir(ed)):
        o = open(os.path.join(od, n), 'rb').read()
        e = open(os.path.join(ed, n), 'rb').read()
        if n.endswith('.MF'):
            so = {x[0]: x[1] for x in c2lib.mf_parse(o)}
            se = {x[0]: x[1] for x in c2lib.mf_parse(e)}
            parts = []
            for k in so:
                if so[k] == se.get(k):
                    continue
                if k.endswith('.SPT'):
                    eo = [x[1:] for x in c2lib.spt_entries(so[k])]
                    ee = [x[1:] for x in c2lib.spt_entries(se[k])]
                    d = sum(1 for p, q in zip(eo, ee) if p != q)
                    parts.append('%s %d->%d sprites, %d changed' % (k[-3:], len(eo), len(ee), d))
                else:
                    parts.append(k[-3:])
            print('%-12s %s' % (n, ', '.join(parts)))
        else:
            g = ranges(o, e)
            print('%-12s %d ranges: %s' % (n, len(g), ' '.join('%x' % x for x, y in g)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
