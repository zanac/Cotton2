"""Move the English dialogue of the Saturn CHR_VS*.MF into the arcade ones.

All three containers are taken in the arcade layout (raw sprites):
  O  Saturn original   (c2lib.to_arcade of the disc file)
  E  Saturn English    (c2lib.to_arcade of the patched file)
  A  arcade original   (from the cartridge)
The arcade VS overlays address frames (SCH records) by index, and the
arcade frame list is not always the Saturn one (VS5 and VS7 have extra
frames), so frame indices are mapped O -> A and every English change is
carried over through that map.
"""
import difflib
import struct

from c2lib import mf_parse, mf_build, spt_entries


class VSMF:
    def __init__(self, data):
        self.subs = mf_parse(data)
        self.end = data[-4:]
        self.names = {n: i for i, (n, d, s) in enumerate(self.subs)}
        base = [n for n in self.names if n.endswith('.SCH')][0][:-4]
        self.base = base
        sch = self.sub('.SCH')
        first = struct.unpack('>I', sch[:4])[0]
        ptr = [struct.unpack('>I', sch[i:i + 4])[0] for i in range(0, first, 4)]
        assert ptr[-1] == 0xffffffff
        self.frames = [bytes(sch[p:p + 20]) for p in ptr[:-1]]
        assert all(len(f) == 20 for f in self.frames)
        self.sprites = {}            # offset -> (header, data)
        self.order = []
        for o, h, d in spt_entries(self.sub('.SPT')):
            self.sprites[o] = (h, d)
            self.order.append(o)

    def sub(self, ext):
        return self.subs[self.names[self.base + ext]][1]

    def set_sub(self, ext, data):
        self.subs[self.names[self.base + ext]][1] = data

    def frame_sprite(self, k):
        o = struct.unpack('>I', self.frames[k][:4])[0]
        return self.sprites.get(o)

    def key(self, k):
        s = self.frame_sprite(k)
        return (self.frames[k][4:], s[0][4:8] + s[1] if s else None)


def frame_map(O, A):
    """{O frame index: A frame index}"""
    ko = [O.key(i)[1] for i in range(len(O.frames))]
    ka = [A.key(j)[1] for j in range(len(A.frames))]
    sm = difflib.SequenceMatcher(None, ko, ka, autojunk=False)
    m = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal' or (op == 'replace' and i2 - i1 == j2 - j1):
            for t in range(i2 - i1):
                m[i1 + t] = j1 + t
    return m


def merge(Od, Ed, Ad):
    O, E, A = VSMF(Od), VSMF(Ed), VSMF(Ad)
    amap = frame_map(O, A)
    nO, nA = len(O.frames), len(A.frames)
    # English frame index -> arcade index
    M = {}
    new_frames = list(A.frames)
    new_sprites = []               # (header, data) of the frames we write, per index
    frame_sprite = {j: A.frame_sprite(j) for j in range(nA)}
    appended = 0
    for k in range(len(E.frames)):
        same = k < nO and O.key(k) == E.key(k)
        if k < nO and k in amap:
            M[k] = amap[k]
            if same:
                continue
            j = amap[k]
        else:
            if same and k in amap:
                M[k] = amap[k]
                continue
            j = nA + appended
            appended += 1
            new_frames.append(None)
            M[k] = j
        new_frames[j] = E.frames[k]
        frame_sprite[j] = E.frame_sprite(k)
    unmapped_O = [i for i in range(nO) if i not in amap]
    return O, E, A, amap, M, new_frames, frame_sprite, unmapped_O


def word_merge(o, e, a, amap, M, nO):
    """3-way merge of a 16-bit word table (SAN): English changes carried over.
    Returns (new bytes, list of conflicts)"""
    wo = [struct.unpack('>H', o[i:i + 2])[0] for i in range(0, len(o) - 1, 2)]
    we = [struct.unpack('>H', e[i:i + 2])[0] for i in range(0, len(e) - 1, 2)]
    wa = [struct.unpack('>H', a[i:i + 2])[0] for i in range(0, len(a) - 1, 2)]
    assert len(wo) == len(we), 'English table changed length'
    sm = difflib.SequenceMatcher(None, wo, wa, autojunk=False)
    pos = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal' or (op == 'replace' and i2 - i1 == j2 - j1):
            for t in range(i2 - i1):
                pos[i1 + t] = j1 + t
    out = list(wa)
    bad = []
    for p in range(len(wo)):
        if wo[p] == we[p]:
            continue
        q = pos.get(p)
        if q is None:
            bad.append((p, wo[p], we[p], None))
            continue
        if wo[p] < nO and wa[q] == amap.get(wo[p]) and we[p] in M:
            out[q] = M[we[p]]
        elif wa[q] == wo[p]:
            out[q] = M.get(we[p], we[p]) if wo[p] < nO and we[p] in M else we[p]
        else:
            bad.append((p, wo[p], we[p], wa[q]))
    return b''.join(struct.pack('>H', w) for w in out) + (a[len(wa) * 2:]), bad


def build(A, frames, frame_sprite, keep_unused=True, limit=None, mf_at=None,
          alloc=None, writes=None):
    """serialize an arcade MF from A with new frames/sprites.
    With limit, new sprites that do not fit go outside the container:
    alloc(size) gives a cartridge address, (address, data) is appended to
    writes and the frame points there (offsets past the end of the SPT)."""
    used = {}
    for j, s in frame_sprite.items():
        if s is not None:
            used[s[0][4:8] + s[1]] = s
    entries = []          # (key, header, data, new)
    seen = set()
    for o in A.order:
        h, d = A.sprites[o]
        k = h[4:8] + d
        if (not keep_unused and k not in used) or k in seen:
            continue
        seen.add(k)
        entries.append((k, h, d, False))
    for k, (h, d) in used.items():
        if k in seen:
            continue
        seen.add(k)
        entries.append((k, h[:8] + struct.pack('>I', len(d)) + h[12:], d, True))
    blob = lambda h, d: h + d + b'\0' * ((-len(d)) & 3)
    n = len(frames)
    first = 4 * (n + 1)
    sch_len = first + 4 + 20 * n

    def total(inside):
        extra = sum(len(blob(h, d)) for k, h, d, nw in entries if k in inside) + sch_len
        return sum(len(x[1]) + 0x20 + ((-len(x[1])) & 3) for x in A.subs
                   if not x[0].endswith(('.SCH', '.SPT'))) + 0x40 + extra + 4
    inside = set(k for k, h, d, nw in entries)
    if limit is not None and total(inside) > limit:
        for k, h, d, nw in sorted(entries, key=lambda e: -len(e[2])):
            if nw and total(inside) > limit:
                inside.discard(k)
        assert total(inside) <= limit, 'does not fit even with sprites outside'
    spt = bytearray()
    where = {}
    for k, h, d, nw in entries:
        if k in inside:
            where[k] = len(spt)
            spt += blob(h, d)

    def make(outside_off):
        sch = bytearray()
        for j in range(n):
            sch += struct.pack('>I', first + 20 * j)
        sch += b'\xff\xff\xff\xff'
        for j in range(n):
            f = bytearray(frames[j])
            s = frame_sprite.get(j)
            if s is not None:
                k = s[0][4:8] + s[1]
                f[:4] = struct.pack('>I', where[k] if k in where else outside_off[k])
            sch += f
        A.set_sub('.SCH', bytes(sch))
        A.set_sub('.SPT', bytes(spt))
        sif = bytearray(A.sub('.SIF'))
        sif[0:2] = struct.pack('>H', (struct.unpack('>H', A.orig_sif[0:2])[0] + n - len(A.frames)) & 0xffff)
        A.set_sub('.SIF', bytes(sif))
        return mf_build(A.subs, A.end)
    if not hasattr(A, 'orig_sif'):
        A.orig_sif = A.sub('.SIF')
    outside = [(k, h, d) for k, h, d, nw in entries if k not in inside]
    mf = make({k: 0 for k, h, d in outside})
    if outside:
        # cartridge address of the SPT data
        o = 0
        while True:
            sz = struct.unpack('>I', mf[o:o + 4])[0]
            if mf[o + 4:o + 20].split(b'\0')[0].decode().endswith('.SPT'):
                break
            o += sz
        spt_base = mf_at + o + 0x20
        offs = {}
        for k, h, d in outside:
            b = blob(h, d)
            at = alloc(len(b))
            writes.append((at, b))
            offs[k] = at - spt_base
        mf = make(offs)
    return mf


def regions(O, E):
    """(text start, art start in O, delta): English rewrote [ts, art) and
    moved the art frames [art, end) by delta"""
    No, Ne = len(O.frames), len(E.frames)
    d = Ne - No
    i = No - 1
    while i >= 0 and O.key(i)[1] == E.key(i + d)[1]:
        i -= 1
    art = i + 1
    ts = next(k for k in range(No) if O.key(k) != E.key(k))
    return ts, art, d


def san_remap(san, fn):
    """apply fn to every frame field of a SAN table"""
    b = bytearray(san)
    first = struct.unpack('>I', b[:4])[0]
    offs = []
    for i in range(0, first, 4):
        o = struct.unpack('>I', b[i:i + 4])[0]
        if o == 0xffffffff:
            break
        offs.append(o)
    bounds = sorted(set(offs)) + [len(b)]
    for o in sorted(set(offs)):
        end = bounds[bounds.index(o) + 1]
        for r in range(o, end - 7, 8):
            f = struct.unpack('>H', b[r:r + 2])[0]
            b[r:r + 2] = struct.pack('>H', fn(f))
    return bytes(b)


def region_merge(Od, Ed, Ad):
    O, E, A = VSMF(Od), VSMF(Ed), VSMF(Ad)
    ts, artO, d = regions(O, E)
    amap = frame_map(O, A)
    assert all(amap.get(i) == i for i in range(ts)), 'prefix differs'
    artA = amap.get(artO)
    if artA is None:
        # first arcade frame aligned to the O art region
        artA = min(amap[i] for i in range(artO, len(O.frames)) if i in amap)
    artE = artO + d
    frames = list(A.frames[:ts]) + list(E.frames[ts:artE]) + list(A.frames[artA:])
    fs = {}
    for j in range(ts):
        fs[j] = A.frame_sprite(j)
    for k in range(ts, artE):
        fs[k] = E.frame_sprite(k)
    for j in range(artA, len(A.frames)):
        fs[j - artA + artE] = A.frame_sprite(j)
    shift = artE - artA

    def remap(f):
        return f + shift if artA <= f < len(A.frames) else f
    return O, E, A, ts, artO, artA, artE, shift, remap, frames, fs


def remap_merge(Od, Ed, Ad):
    """English layout; arcade art kept where it differs; arcade-only frames
    appended. Returns the new frames and R: arcade index -> new index."""
    O, E, A = VSMF(Od), VSMF(Ed), VSMF(Ad)
    No, Ne, Na = len(O.frames), len(E.frames), len(A.frames)
    d = Ne - No
    amap = frame_map(O, A)
    inv = {j: i for i, j in amap.items()}
    frames = list(E.frames)
    fs = {k: E.frame_sprite(k) for k in range(Ne)}
    R = {}
    extra = []
    for j in range(Na):
        i = inv.get(j)
        if i is None:
            extra.append(j)
            continue
        if O.key(i) == E.key(i):
            k = i
        elif i + d < Ne and E.key(i + d)[1] == O.key(i)[1]:
            k = i + d
        else:
            k = i
        R[j] = k
        if A.key(j) != O.key(i) and (k != i or O.key(i) == E.key(i)):
            frames[k] = A.frames[j]
            fs[k] = A.frame_sprite(j)
    for j in extra:
        R[j] = len(frames)
        frames.append(A.frames[j])
        fs[R[j]] = A.frame_sprite(j)
    return O, E, A, R, frames, fs, amap


def table_runs(buf, start, lo, nmax):
    """bounds of the run of 16-bit words < nmax around start"""
    def ok(p):
        return 0 <= p < len(buf) - 1 and struct.unpack('>H', buf[p:p + 2])[0] < nmax
    a = start & ~1
    b = a
    while ok(a - 2) and a - 2 >= lo:
        a -= 2
    while ok(b + 2):
        b += 2
    return a, b + 2


def remap_tables(sat_o, sat_e, arc, R, n_o, n_a, start=0x12000):
    """remap the frame-list tables of an arcade VS overlay through R.
    The tables are the runs of frame numbers that the English patch
    changed in the Saturn overlay; the arcade copy is found at one of the
    shifts between the two overlays. Returns (new bytes, [(sat run, arc run)])"""
    import vsport
    groups = [g for g in vsport.groups(sat_o, sat_e) if g[0] >= start]
    sruns = []
    for x, y in groups:
        p = x & ~1
        if struct.unpack('>H', sat_o[p:p + 2])[0] >= n_o:
            continue
        sa, sb = table_runs(sat_o, p, start, n_o)
        if sb - sa >= 16 and (sa, sb) not in sruns:
            sruns.append((sa, sb))
    deltas = sorted(set(o[2] for o in vsport.locate(sat_o, sat_e, arc) if o[2] is not None))
    out = bytearray(arc)
    res = []
    for sa, sb in sruns:
        best = None
        for d in deltas:
            for dd in range(-0x40, 0x42, 2):
                q = sa + d + dd
                if q < 0 or q + (sb - sa) > len(arc):
                    continue
                eq = sum(1 for t in range(0, sb - sa, 2) if arc[q + t:q + t + 2] == sat_o[sa + t:sa + t + 2])
                if best is None or eq > best[0]:
                    best = (eq, q)
        q = best[1]
        aa, ab = table_runs(arc, q + 2, start, n_a)
        for t in range(aa, ab, 2):
            w = struct.unpack('>H', arc[t:t + 2])[0]
            out[t:t + 2] = struct.pack('>H', R.get(w, w))
        res.append(((sa, sb), (aa, ab), best[0] * 2 / (sb - sa)))
    return bytes(out), res


def san_frames(san):
    """positions of the frame fields of a SAN table"""
    first = struct.unpack('>I', san[:4])[0]
    offs = []
    for i in range(0, first, 4):
        o = struct.unpack('>I', san[i:i + 4])[0]
        if o == 0xffffffff:
            break
        offs.append(o)
    bounds = sorted(set(offs)) + [len(san)]
    pos = []
    for o in sorted(set(offs)):
        end = bounds[bounds.index(o) + 1]
        pos += list(range(o, end - 7, 8))
    return pos


def english_moves(O, E, vs_o, vs_e, table_runs_list):
    """{O frame: E frame} as renumbered by the English patch, from the SAN
    and the overlay frame tables; conflicts listed"""
    T = {}
    bad = []
    so, se = O.sub('.SAN'), E.sub('.SAN')
    pairs = []
    for p in san_frames(so):
        pairs.append((struct.unpack('>H', so[p:p + 2])[0], struct.unpack('>H', se[p:p + 2])[0]))
    for sa, sb in table_runs_list:
        for t in range(sa, sb, 2):
            pairs.append((struct.unpack('>H', vs_o[t:t + 2])[0], struct.unpack('>H', vs_e[t:t + 2])[0]))
    for v, w in pairs:
        if v in T and T[v] != w:
            bad.append((v, T[v], w))
        T.setdefault(v, w)
    return T, bad


def frame_table_changes(vs_o, vs_e, n_o, start=0x12000):
    """[(pos, old, new)] of the frame numbers the English patch changed in
    the overlay frame tables (runs of words below n_o, 64 bytes or more)"""
    import vsport
    out = []
    seen = set()
    for x, y in vsport.groups(vs_o, vs_e):
        if x < start:
            continue
        sa, sb = table_runs(vs_o, x & ~1, start, n_o)
        if sb - sa < 64:
            continue
        for t in range(x & ~1, (y | 1) + 1, 2):
            if t in seen or not sa <= t < sb:
                continue
            seen.add(t)
            v = struct.unpack('>H', vs_o[t:t + 2])[0]
            w = struct.unpack('>H', vs_e[t:t + 2])[0]
            if v != w:
                out.append((t, v, w))
    return out


def merge3(Od, Ed, Ad, vs_o, vs_e, vs_a, **build_args):
    """returns (new MF bytes, new overlay bytes, report, conflicts, counts)"""
    import vsport
    O, E, A = VSMF(Od), VSMF(Ed), VSMF(Ad)
    No, Ne, Na = len(O.frames), len(E.frames), len(A.frames)
    amap = frame_map(O, A)
    inv = {j: i for i, j in amap.items()}

    def moved_ok(v, w):
        return v < No and w < Ne and E.key(w)[1] == O.key(v)[1]
    # Saturn frame tables: long runs of frame numbers with key-consistent changes
    truns = []
    for t, v, w in frame_table_changes(vs_o, vs_e, No):
        sa, sb = table_runs(vs_o, t, 0x12000, No)
        if moved_ok(v, w) and (sa, sb) not in truns:
            truns.append((sa, sb))
    # English renumbering T: SAN (all used) and the changed frame-table entries
    T = {}
    conflicts = []
    ao, ae = san_anims(O.sub('.SAN')), san_anims(E.sub('.SAN'))
    aa = san_anims(A.sub('.SAN'))
    assert len(ae) >= len(ao) and len(aa) == len(ao)
    san_bad = set()
    for i in range(len(ao)):
        assert len(ao[i]) == len(ae[i]), 'English changed animation %d' % i
        for ro, re_ in zip(ao[i], ae[i]):
            v = struct.unpack('>H', ro[:2])[0]
            w = struct.unpack('>H', re_[:2])[0]
            if T.setdefault(v, w) != w:
                san_bad.add(v)
    for v in san_bad:
        # one original frame split into several English ones (text pages):
        # no single renumbering, the English animations are used as they are
        del T[v]
    for sa, sb in truns:
        for t in range(sa, sb, 2):
            v = struct.unpack('>H', vs_o[t:t + 2])[0]
            w = struct.unpack('>H', vs_e[t:t + 2])[0]
            if v != w and moved_ok(v, w) and T.setdefault(v, w) != w:
                conflicts.append(('tab', v, T[v], w))
    report = []
    frames = list(E.frames)
    fs = {k: E.frame_sprite(k) for k in range(Ne)}
    R = {}
    for j in range(Na):
        i = inv.get(j)
        if i is None:
            R[j] = len(frames)
            frames.append(A.frames[j])
            fs[R[j]] = A.frame_sprite(j)
            continue
        k = T.get(i, i)
        R[j] = k
        if A.key(j)[1] != O.key(i)[1] and k < Ne and E.key(k)[1] == O.key(i)[1]:
            frames[k] = A.frames[j]
            fs[k] = A.frame_sprite(j)
    # animations: the English one where the arcade has the original one,
    # else the arcade one renumbered; animations added by the patch at the end
    def same(i):
        if len(aa[i]) != len(ao[i]):
            return False
        for ra, ro in zip(aa[i], ao[i]):
            fa = struct.unpack('>H', ra[:2])[0]
            fo = struct.unpack('>H', ro[:2])[0]
            if ra[2:] != ro[2:] or fa >= Na or fo >= No or A.key(fa) != O.key(fo):
                return False
        return True
    new_anims = []
    kept = 0
    for i in range(len(ao)):
        if same(i):
            new_anims.append(b''.join(ae[i]))
        else:
            kept += 1
            new_anims.append(b''.join(struct.pack('>H', R.get(struct.unpack('>H', r[:2])[0],
                                                              struct.unpack('>H', r[:2])[0])) + r[2:]
                                      for r in aa[i]))
            if any(struct.unpack('>H', r[:2])[0] in [j for j in range(Na) if inv.get(j) in san_bad] for r in aa[i]):
                conflicts.append(('arcade anim uses a split frame', i))
    # written in place over the arcade table (keeps any shared records)
    san = bytearray(A.sub('.SAN'))
    first = struct.unpack('>I', san[:4])[0]
    aoffs = [struct.unpack('>I', san[t:t + 4])[0] for t in range(0, first - 4, 4)]
    for o, b in zip(aoffs, new_anims):
        san[o:o + len(b)] = b
    san = bytes(san)
    if len(ae) > len(ao):
        san = san_append(san, [b''.join(a) for a in ae[len(ao):]])
    if len(ae) > len(ao):
        sif = bytearray(A.sub('.SIF'))
        sif[4:6] = struct.pack('>H', struct.unpack('>H', sif[4:6])[0] + len(ae) - len(ao))
        A.set_sub('.SIF', bytes(sif))
    A.set_sub('.SAN', san)
    report.append(('arcade animations kept', kept))
    mf = build(A, frames, fs, keep_unused=False, **build_args)
    vs = bytearray(vs_a)
    inrun = lambda t: any(sa <= t < sb for sa, sb in truns)
    for x, y, d, sc in vsport.locate(vs_o, vs_e, vs_a):
        if x < 0x12000:
            continue
        cands = []
        if sc < 1:
            for ctx in (24, 16, 10, 6):
                cands = vsport.wild_find(vs_o, vs_a, x, y, ctx)
                if cands:
                    break
            if len(cands) == 1:
                d = cands[0] - x
        if any(vs_o[t] != vs_e[t] and not inrun(t) and vs_a[t + d] != vs_o[t] for t in range(x, y + 1)):
            found = False
            for c in (8, 6, 5, 4, 3):
                for lc, rc in ((c, c), (c, 0), (0, c)):
                    pat = vs_o[x - lc:y + 1 + rc]
                    k = vs_a.find(pat)
                    if k >= 0 and vs_a.find(pat, k + 1) < 0:
                        d = k + lc - x
                        found = True
                        break
                if found:
                    break
        for t in range(x, y + 1):
            if vs_o[t] == vs_e[t] or inrun(t):
                continue
            if vs_a[t + d] == vs_o[t]:
                vs[t + d] = vs_e[t]
            else:
                report.append(('byte-skip', hex(t), hex(t + d)))
        report.append(('group', hex(x), hex(y), hex(d), round(sc, 2), len(cands)))
    deltas = sorted(set(o[2] for o in vsport.locate(vs_o, vs_e, vs_a) if o[2] is not None))
    for sa, sb in truns:
        best = None
        for d in deltas:
            for dd in range(-0x40, 0x42, 2):
                q = sa + d + dd
                if q < 0 or q + (sb - sa) > len(vs_a):
                    continue
                eq = 0
                for t in range(0, sb - sa, 2):
                    v = struct.unpack('>H', vs_o[sa + t:sa + t + 2])[0]
                    a = struct.unpack('>H', vs_a[q + t:q + t + 2])[0]
                    eq += (a == amap.get(v, -1))
                if best is None or eq > best[0]:
                    best = (eq, q)
        eq, q = best
        aa, ab = table_runs(vs_a, q + 2, 0x12000, Na)
        for p in range(aa, ab, 2):
            a = struct.unpack('>H', vs_a[p:p + 2])[0]
            vs[p:p + 2] = struct.pack('>H', R.get(a, a))
        report.append(('table', hex(sa), hex(sb), hex(aa), hex(ab), round(eq * 2 / (sb - sa), 3)))
    return mf, bytes(vs), report, conflicts, (No, Ne, Na, len(frames))


def san_anims(san):
    """records (8 bytes each) of every animation of a SAN table"""
    first = struct.unpack('>I', san[:4])[0]
    offs = [struct.unpack('>I', san[i:i + 4])[0] for i in range(0, first, 4)]
    assert offs[-1] == 0xffffffff
    offs = offs[:-1]
    bounds = sorted(set(offs)) + [len(san)]
    out = []
    for o in offs:
        end = bounds[bounds.index(o) + 1]
        out.append([san[r:r + 8] for r in range(o, end - 7, 8)])
    return out


def san_append(san, extra):
    """add animations (record bytes) at the end of a SAN table"""
    first = struct.unpack('>I', san[:4])[0]
    offs = [struct.unpack('>I', san[i:i + 4])[0] for i in range(0, first - 4, 4)]
    grow = 4 * len(extra)
    body = san[first:]
    new_offs = [o + grow for o in offs]
    at = first + grow + len(body)
    tail = b''
    for x in extra:
        new_offs.append(at + len(tail))
        tail += x
    head = b''.join(struct.pack('>I', o) for o in new_offs) + b'\xff\xff\xff\xff'
    return head + body + tail


def san_build(anims):
    """SAN table from the record bytes of each animation"""
    first = 4 * (len(anims) + 1)
    head = b''
    body = b''
    for a in anims:
        head += struct.pack('>I', first + len(body))
        body += a
    return head + b'\xff\xff\xff\xff' + body
