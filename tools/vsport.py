"""Find where the Saturn VS*.BIN changes go in the arcade overlays."""
import struct
CODE_END = 0x12000  # below this the changes are engine code, ported by hand


def groups(a, b, gap=4):
    g = []
    for i in range(len(a)):
        if a[i] != b[i]:
            if g and i - g[-1][1] <= gap:
                g[-1][1] = i
            else:
                g.append([i, i])
    return g


def score(sat, arc, x, y, d, ctx=48):
    """matching bytes around [x,y] (Saturn) vs [x+d,y+d] (arcade), pointer
    words (0x06xxxxxx) count as matching"""
    ok = tot = 0
    for i in range(x - ctx, y + ctx + 1):
        j = i + d
        if i < 0 or i >= len(sat) or j < 0 or j >= len(arc):
            continue
        tot += 1
        if sat[i] == arc[j]:
            ok += 1
    return ok / max(tot, 1)


def locate(sat, eng, arc):
    """[(x, y, arcade x, score)] for the data changes"""
    G = [g for g in groups(sat, eng) if g[0] >= CODE_END]
    out = []
    deltas = []
    for x, y in G:
        best = None
        for ctx in (24, 16, 12, 8):
            pat = sat[x - ctx:y + 1 + ctx]
            k = arc.find(pat)
            if k >= 0 and arc.find(pat, k + 1) < 0:
                best = k + ctx - x
                break
        if best is not None:
            deltas.append(best)
        out.append([x, y, best])
    # unresolved: try the known shifts, keep the best scoring one
    for o in out:
        if o[2] is None:
            cands = sorted(set(deltas))
            sc = [(score(sat, arc, o[0], o[1], d), d) for d in cands]
            if sc:
                s, d = max(sc)
                o[2] = d
                o.append(s)
        else:
            o.append(1.0)
    return out


def wild_find(sat, arc, x, y, ctx=24):
    """positions in arc matching sat[x-ctx:y+ctx] with 0x06xxxxxx words as wildcards"""
    import re
    s = x - ctx
    s -= s % 2
    pat = b''
    i = s
    while i < y + 1 + ctx:
        if i % 2 == 0 and sat[i] == 0x06 and i + 4 <= len(sat) and sat[i + 1] in (0x06, 0x07, 0x08):
            pat += b'\x06[\x06-\x08]..'
            i += 4
        else:
            pat += re.escape(sat[i:i + 1])
            i += 1
    return [m.start() + (x - s) for m in re.finditer(pat, arc, re.S)]
