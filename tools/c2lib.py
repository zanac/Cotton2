"""Cotton 2 (Sega ST-V) English translation: shared helpers.

Python 3 standard library only.

Formats handled here:
  * the ST-V cartridge region of cotton2 and its chained file system
  * the Saturn disc image (ISO 9660 data track, raw 2352 or cooked 2048)
  * the "MF" graphics containers (SCH/SPT/SPL/SAN/SIF/SCP subfiles)
  * the LZ00 sprite compression used by the Saturn port
"""
import os, struct, zipfile, zlib

# ---------------------------------------------------------------- arcade

# (name, crc, region offset, size) - ROM_LOAD16_WORD_SWAP in src/drivers/stv.c
CART = [
    ('mpr20122.7', 0xd616f78a, 0x0200000, 0x200000),
    ('mpr20117.2', 0x893656ea, 0x0400000, 0x400000),
    ('mpr20118.3', 0x1b6a1d4c, 0x0800000, 0x400000),
    ('mpr20119.4', 0x5a76e72b, 0x0c00000, 0x400000),
    ('mpr20120.5', 0x7113dd7b, 0x1000000, 0x400000),
    ('mpr20121.6', 0x8c8fd521, 0x1400000, 0x400000),
    ('mpr20116.1', 0xd30b0175, 0x1800000, 0x400000),
    ('mpr20123.8', 0x35f1b89f, 0x1c00000, 0x400000),
]
REGION_SIZE = 0x2000000


def swap16(b):
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


def find_member(zips, name, crc):
    for z in zips:
        for i in z.infolist():
            if i.CRC == crc:
                return z.read(i)
    return None


def load_cart(romdir):
    """the cart region (big endian, as the SH-2 sees it) and the raw chips"""
    zips = [zipfile.ZipFile(os.path.join(romdir, n))
            for n in ('cotton2.zip',) if os.path.exists(os.path.join(romdir, n))]
    if not zips:
        raise SystemExit('cotton2.zip not found in ' + romdir)
    reg = bytearray(b'\xff' * REGION_SIZE)
    chips = {}
    for name, crc, off, size in CART:
        d = find_member(zips, name, crc)
        if d is None or len(d) != size:
            raise SystemExit('%s (CRC %08x) not found in cotton2.zip' % (name, crc))
        chips[name] = d
        reg[off:off + size] = swap16(d)
    return reg, chips


def save_chips(reg):
    """split a region back into chips"""
    return [(name, swap16(bytes(reg[off:off + size]))) for name, crc, off, size in CART]


def fs_entry(reg, off):
    """(name, size2, data offset) of the cart file at off"""
    name = reg[off + 4:off + 20].split(b'\0')[0].decode('latin1')
    s2 = struct.unpack('>I', reg[off + 0x14:off + 0x18])[0]
    return name, s2, off + 0x20


# cart files we touch (header offsets in the region)
ARC_MF = {
    'CHR_TTL.MF': 0x370ba0, 'CHR_VS0.MF': 0x4f8360, 'CHR_ST1.MF': 0x6191d0,
    'CHR_VS1.MF': 0xb025d0, 'CHR_ST2.MF': 0xc1b9c0, 'CHR_VS2.MF': 0xe576e0,
    'CHR_ST3.MF': 0xf2adf0, 'CHR_VS3.MF': 0x10cd600, 'CHR_ST4.MF': 0x11c7be0,
    'CHR_VS4.MF': 0x1495830, 'CHR_ST5.MF': 0x15712f0, 'CHR_VS5.MF': 0x17dc100,
    'CHR_ST6.MF': 0x190a1f0, 'CHR_VS6.MF': 0x1b60920, 'CHR_ST7.MF': 0x1c34890,
    'CHR_VS7.MF': 0x1dc1c80,
}
ARC_VS = {
    'VS0.BIN': 0x454bb0, 'VS1.BIN': 0xababa0, 'VS2.BIN': 0xe11ab0,
    'VS3.BIN': 0x1085520, 'VS4.BIN': 0x14500c0, 'VS5.BIN': 0x1794c00,
    'VS6.BIN': 0x1b18710, 'VS7.BIN': 0x1ccb750,
}


def arc_file(reg, name):
    off = ARC_MF.get(name) or ARC_VS[name]
    n, s2, d = fs_entry(reg, off)
    assert n == name, (n, name)
    return bytes(reg[d:d + s2])


# ---------------------------------------------------------------- Saturn

def read_sectors(path):
    """2048-byte user data of every sector of a data track"""
    raw = open(path, 'rb').read()
    if len(raw) % 2352 == 0 and raw[:12] == b'\x00' + b'\xff' * 10 + b'\x00':
        out = bytearray()
        for s in range(len(raw) // 2352):
            sec = raw[s * 2352:(s + 1) * 2352]
            base = 16 if sec[15] == 1 else 24
            out += sec[base:base + 2048]
        return bytes(out)
    return raw


def iso_files(img):
    """{name: data} of the root directory of an ISO 9660 image"""
    pvd = img[16 * 2048:17 * 2048]
    assert pvd[1:6] == b'CD001', 'not an ISO 9660 track'
    root = pvd[156:156 + 34]
    lba, size = struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0]
    d = img[lba * 2048:lba * 2048 + size]
    out = {}
    o = 0
    while o < len(d):
        ln = d[o]
        if ln == 0:
            o = (o // 2048 + 1) * 2048
            continue
        flba = struct.unpack('<I', d[o + 2:o + 6])[0]
        fsz = struct.unpack('<I', d[o + 10:o + 14])[0]
        nl = d[o + 32]
        name = d[o + 33:o + 33 + nl].decode('latin1').split(';')[0]
        if not d[o + 25] & 2 and name not in ('\0', '\1'):
            out[name] = img[flba * 2048:flba * 2048 + fsz]
        o += ln
    return out


def load_disc(path):
    """Saturn root files from track 1 (.bin raw or .iso); a .cue picks track 1"""
    if path.lower().endswith('.cue'):
        folder = os.path.dirname(path)
        for line in open(path, encoding='latin1'):
            line = line.strip()
            if line.upper().startswith('FILE'):
                path = os.path.join(folder, line.split('"')[1])
                break
    return iso_files(read_sectors(path))


# ---------------------------------------------------------------- MF

def mf_parse(b):
    """list of [name, data, stamp(8 bytes)] of an MF container"""
    o = 0
    out = []
    while o + 0x20 <= len(b):
        sz = struct.unpack('>I', b[o:o + 4])[0]
        if sz == 0:
            break
        name = b[o + 4:o + 20].split(b'\0')[0].decode('latin1')
        s2 = struct.unpack('>I', b[o + 0x14:o + 0x18])[0]
        out.append([name, b[o + 0x20:o + 0x20 + s2], b[o + 0x18:o + 0x20]])
        o += sz
    return out


def mf_build(subs, end=b'\0' * 4):
    out = bytearray()
    for name, data, stamp in subs:
        pad = (-len(data)) & 3
        hdr = struct.pack('>I', 0x20 + len(data) + pad) + name.encode().ljust(16, b'\0')
        hdr += struct.pack('>I', len(data)) + stamp
        out += hdr + data + b'\0' * pad
    out += end
    return bytes(out)


def unlz(c):
    """LZ00: byte b < 0x10 -> b+1 literals; else copy (next byte + 3) bytes
    from distance b - 0x0f (bytes before the start read as zero)"""
    assert c[:4] == b'LZ00'
    n = struct.unpack('>I', c[4:8])[0]
    i = 8
    o = bytearray()
    while len(o) < n:
        b = c[i]
        i += 1
        if b < 0x10:
            o += c[i:i + b + 1]
            i += b + 1
        else:
            d = b - 0x0f
            ln = c[i] + 3
            i += 1
            for _ in range(ln):
                s = len(o) - d
                o.append(o[s] if s >= 0 else 0)
    return bytes(o[:n])


def spt_entries(spt):
    """list of (offset, header, data) of a sprite pattern table"""
    out = []
    o = 0
    while o + 0x20 <= len(spt):
        h = spt[o:o + 0x20]
        sz = struct.unpack('>I', h[8:12])[0]
        out.append((o, h, spt[o + 0x20:o + 0x20 + sz]))
        o += 0x20 + ((sz + 3) & ~3)
    return out


def sch_offsets(sch):
    first = struct.unpack('>I', sch[:4])[0]
    n = (len(sch) - first) // 20
    return first, n


def to_arcade(sat_mf, arc_mf=None):
    """convert a Saturn MF to the arcade layout: LZ00 sprites stored raw
    and the SCH sprite offsets moved. Subfile stamps come from arc_mf."""
    subs = mf_parse(sat_mf)
    stamps = {}
    if arc_mf is not None:
        stamps = {n: s for n, d, s in mf_parse(arc_mf)}
    names = {n: i for i, (n, d, s) in enumerate(subs)}
    for n in list(names):
        if not n.endswith('.SPT'):
            continue
        spt = subs[names[n]][1]
        remap = {}
        new = bytearray()
        for off, h, d in spt_entries(spt):
            if d[:4] == b'LZ00':
                d = unlz(d)
                h = h[:8] + struct.pack('>I', len(d)) + h[12:]
            remap[off] = len(new)
            new += h + d + b'\0' * ((-len(d)) & 3)
        subs[names[n]][1] = bytes(new)
        sch_name = n[:-4] + '.SCH'
        sch = bytearray(subs[names[sch_name]][1])
        first, cnt = sch_offsets(sch)
        for k in range(cnt):
            p = first + k * 20
            o = struct.unpack('>I', sch[p:p + 4])[0]
            sch[p:p + 4] = struct.pack('>I', remap[o])
        subs[names[sch_name]][1] = bytes(sch)
    for s in subs:
        if s[0] in stamps:
            s[2] = stamps[s[0]]
    return mf_build(subs, arc_mf[-4:] if arc_mf is not None else b'\xff' * 4)
