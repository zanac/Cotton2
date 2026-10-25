"""Build the English cartridge region of Cotton 2 from the arcade cartridge
and the original/English Saturn files. Python 3 standard library only."""
import os
import struct

import c2lib
import vsmerge

OTHER = {'BGM_VS0.MF': 0x474d40, 'CHR_TTL.MF': 0x370ba0}
CHAIN_END = 0x1eb3a20      # end of the cartridge file chain; zeros follow
REGION_END = 0x2000000


class Cart:
    def __init__(self, reg):
        self.reg = bytearray(reg)
        assert not any(self.reg[CHAIN_END:CHAIN_END + 0x1000])
        self.free = CHAIN_END
        self.chain_tail = CHAIN_END
        self.allocated = False
        self.log = []

    def alloc(self, size, align=0x20):
        self.allocated = True
        at = max(self.free, self.chain_tail + 4)
        at = (at + align - 1) & ~(align - 1)
        assert at + size <= REGION_END - 4, 'cartridge full'
        self.free = at + size
        return at

    def entry(self, name):
        off = c2lib.ARC_MF.get(name) or c2lib.ARC_VS.get(name) or OTHER[name]
        n, s2, d = c2lib.fs_entry(self.reg, off)
        assert n == name
        return off, s2, d

    def put(self, name, data):
        """replace a file: in place when it fits, else renamed and moved to
        the end of the file chain"""
        off, s2, d = self.entry(name)
        if len(data) <= s2:
            self.reg[d:d + s2] = data + b'\xff' * (s2 - len(data))
            self.log.append('%-12s in place  %6x/%6x' % (name, len(data), s2))
            return
        self.put_moved(name, data)

    def put_moved(self, name, data):
        off, s2, d = self.entry(name)
        self.reg[off + 4:off + 20] = (name[:-1] + 'X').encode().ljust(16, b'\0')
        pad = (-len(data)) & 3
        blob = struct.pack('>I', 0x20 + len(data) + pad) + name.encode().ljust(16, b'\0')
        blob += struct.pack('>I', len(data)) + bytes(self.reg[off + 0x18:off + 0x20]) + data + b'\0' * pad
        # the file chain continues at its old end: moved files follow each
        # other there, before anything else goes to the free area
        assert not self.allocated, 'move files before using the free area'
        at = self.chain_tail
        assert at + len(blob) + 4 <= REGION_END
        self.reg[at:at + len(blob)] = blob
        self.chain_tail = at + len(blob)
        self.reg[self.chain_tail:self.chain_tail + 4] = b'\0' * 4
        self.log.append('%-12s moved to %x (%x bytes, slot %x)' % (name, at, len(data), s2))

    def subfile_offsets(self, name):
        off, s2, d = self.entry(name)
        o = d
        out = {}
        while o < d + s2:
            sz = struct.unpack('>I', self.reg[o:o + 4])[0]
            if sz in (0, 0xffffffff):
                break
            out[self.reg[o + 4:o + 20].split(b'\0')[0].decode()] = o + 0x20
            o += sz
        return out


def load_sat(satdir, name):
    return open(os.path.join(satdir, name), 'rb').read()


# --- dialogue scenes ----------------------------------------------------

CODE_MUL = 0xeaca   # mov #13,r3: character advance (overlay offset)
CODE_SPD = 0xe542   # mov #5,r1: frames per character


def vs_scene(cart, n, orig, eng):
    mfn, vsn = 'CHR_VS%d.MF' % n, 'VS%d.BIN' % n
    Ad = c2lib.arc_file(cart.reg, mfn)
    Od = c2lib.to_arcade(load_sat(orig, mfn), Ad)
    Ed = c2lib.to_arcade(load_sat(eng, mfn), Ad)
    so, se = load_sat(orig, vsn), load_sat(eng, vsn)
    ha = c2lib.arc_file(cart.reg, vsn)
    off, s2, d = cart.entry(mfn)
    writes = []
    mf, vs, report, conflicts, counts = vsmerge.merge3(Od, Ed, Ad, so, se, ha, limit=s2, mf_at=d,
                                                       alloc=cart.alloc, writes=writes)
    for at, b in writes:
        cart.reg[at:at + len(b)] = b
    if writes:
        cart.log.append('%s: %d sprites outside (%x bytes)' % (mfn, len(writes), sum(len(b) for a, b in writes)))
    assert not conflicts, conflicts
    vs = bytearray(vs)
    # engine constants, as in the Saturn overlay
    assert vs[CODE_MUL:CODE_MUL + 2] == b'\xe3\x0d'
    vs[CODE_MUL + 1] = se[0x11035]
    if se[0x1091b] != so[0x1091b]:
        assert vs[CODE_SPD:CODE_SPD + 2] == b'\xe1\x05'
        vs[CODE_SPD + 1] = se[0x1091b]
    cart.put(mfn, mf)
    cart.put(vsn, bytes(vs))
    skipped = [r for r in report if r[0] == 'byte-skip']
    cart.log.append('VS%d frames %d/%d/%d -> %d, skipped bytes %d' % ((n,) + counts + (len(skipped),)))


# --- continue screen hints ----------------------------------------------

def raw_sprite(h, d):
    w, hh = struct.unpack('>HH', h[4:8])
    if d[:4] == b'LZ00':
        d = c2lib.unlz(d)
    d = d[:w * hh // 2]
    return h[:8] + struct.pack('>I', len(d)) + h[12:], d


def mf_frames(mf):
    m = {k: x for k, x, s in c2lib.mf_parse(mf)}
    k = [n for n in m if n.endswith('.SCH')][0][:-4]
    sch = m[k + '.SCH']
    first = struct.unpack('>I', sch[:4])[0]
    ptr = [struct.unpack('>I', sch[i:i + 4])[0] for i in range(0, first, 4)]
    return k, sch, ptr, c2lib.spt_entries(m[k + '.SPT'])


def stage_hints(cart, st, orig, eng):
    """the continue screen hint lines: English sprites go to the free area,
    the frames point at them (offsets past the end of the SPT work)"""
    n = 'CHR_ST%d.MF' % st
    ko, so, po, Eo = mf_frames(load_sat(orig, n))
    ke, se, pe, Ee = mf_frames(load_sat(eng, n))
    sub = cart.subfile_offsets(n)
    sch_at, spt_at = sub[ko + '.SCH'], sub[ko + '.SPT']
    first = struct.unpack('>I', cart.reg[sch_at:sch_at + 4])[0]
    pa = [struct.unpack('>I', cart.reg[sch_at + i:sch_at + i + 4])[0] for i in range(0, first, 4)]
    io = {o: raw_sprite(h, d)[1] for o, h, d in Eo}
    ie = {o: (h, d) for o, h, d in Ee}
    done = 0
    for k in range(min(len(po), len(pe)) - 1):
        ro, re_ = so[po[k]:po[k] + 20], se[pe[k]:pe[k] + 20]
        oo, oe = struct.unpack('>I', ro[:4])[0], struct.unpack('>I', re_[:4])[0]
        h, d = raw_sprite(*ie[oe])
        changed = d != io[oo]
        if ro[4:] == re_[4:] and not changed:
            continue
        p = sch_at + pa[k]
        if changed:
            blob = h + d + b'\0' * ((-len(d)) & 3)
            at = cart.alloc(len(blob))
            cart.reg[at:at + len(blob)] = blob
            cart.reg[p:p + 4] = struct.pack('>I', at - spt_at)
        cart.reg[p + 4:p + 20] = re_[4:]
        done += 1
    cart.log.append('ST%d hints: %d frames' % (st, done))


# --- attract screens (prologue scroll, character profiles) ----------------

def free_old_area(cart, name):
    """move a file to the end of the chain; its old data area is returned
    as free space (start, end)"""
    off, s2, d = cart.entry(name)
    data = bytes(cart.reg[d:d + s2])
    cart.put_moved(name, data)
    return [d, d + s2]


def ttl_screens(cart, orig, eng, area):
    """the attract screens of CHR_TTL.MF are maps of 8bpp cells (SCP);
    English cells go to area (reachable with a 16-bit cell number)"""
    name = 'CHR_TTL.MF'
    sub = cart.subfile_offsets(name)
    scp_at, spt_at = sub['CHR_TTL.SCP'], sub['CHR_TTL.SPT']
    m = {k: x for k, x, s in c2lib.mf_parse(c2lib.arc_file(cart.reg, name))}
    scp = m['CHR_TTL.SCP']
    ents = c2lib.spt_entries(m['CHR_TTL.SPT'])
    so = {k: x for k, x, s in c2lib.mf_parse(load_sat(orig, name))}
    se = {k: x for k, x, s in c2lib.mf_parse(load_sat(eng, name))}

    def sat(mf, k):
        return c2lib.unlz(c2lib.spt_entries(mf['CHR_TTL.SPT'])[k][2])[:352 * 224]
    cells = {}
    for u in range(len(scp) // 32 - 1, -1, -1):
        cells[scp[u * 32:u * 32 + 64]] = u
    new = 0

    def cell_unit(c):
        nonlocal new
        u = cells.get(c)
        if u is None:
            at = (area[0] - scp_at + 0x1f) // 0x20 * 0x20 + scp_at
            assert at + 64 <= area[1], 'no room for the title cells'
            area[0] = at + 64
            cart.reg[at:at + 64] = c
            u = (at - scp_at) // 0x20
            assert u < 0x10000
            cells[c] = u
            new += 1
        return u
    # screens: (arcade entries, Saturn screens) with the same pixels
    jobs = [((0, 1, 2), (0, 1, 2)), ((6,), (6,)), ((10,), (10,))]
    for arc_k, sat_k in jobs:
        before = b''.join(sat(so, k) for k in sat_k)
        after = b''.join(sat(se, k) + sat(so, k)[len(sat(se, k)):] for k in sat_k)
        y0 = 0
        for k in arc_k:
            o, h, d = ents[k]
            w, hh = struct.unpack('>HH', h[4:8])
            W, H = w // 8, hh // 8
            at = spt_at + o + 0x20
            for cy in range(H):
                for cx in range(W):
                    c = b''.join(after[(y0 + cy * 8 + y) * 352 + cx * 8:(y0 + cy * 8 + y) * 352 + cx * 8 + 8]
                                 for y in range(8))
                    p = at + (cy * W + cx) * 4 + 2
                    old = struct.unpack('>H', cart.reg[p:p + 2])[0]
                    if scp[old * 32:old * 32 + 64] == c:
                        continue
                    cart.reg[p:p + 2] = struct.pack('>H', cell_unit(c))
            y0 += hh
        assert y0 == len(after) // 352
    cart.log.append('CHR_TTL screens: %d new cells' % new)


# --- whole cartridge ------------------------------------------------------

def build(reg, orig, eng, scenes=range(8)):
    """English cartridge region from the arcade one; returns (region, log)"""
    cart = Cart(reg)
    area = free_old_area(cart, 'BGM_VS0.MF')
    ttl_screens(cart, orig, eng, area)
    for n in scenes:
        vs_scene(cart, n, orig, eng)
    for st in range(1, 8):
        stage_hints(cart, st, orig, eng)
    cart.log.append('chain tail %x, free area from %x, title area left %x'
                    % (cart.chain_tail, cart.free, area[1] - area[0]))
    return bytes(cart.reg), cart.log
