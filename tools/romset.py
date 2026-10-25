"""The cotton2e ROM set and the patch that rebuilds it from cotton2."""
import lzma, os, struct, zipfile, zlib

import c2lib

SET = 'cotton2e'
MAGIC = b'C2E1\0'


def new_name(name):
    """mpr20117.2 -> c2e20117.2"""
    return 'c2e' + name[3:]


def chips(reg):
    """[(original name, new name, data)] of the English cartridge"""
    out = []
    for name, data in c2lib.save_chips(reg):
        out.append((name, new_name(name), data))
    return out


def write_zip(reg, path):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for src, dst, data in chips(reg):
            z.writestr(dst, data)
    return [(dst, zlib.crc32(data), data) for src, dst, data in chips(reg)]


def make_patch(orig_chips, reg):
    """XOR of every chip against the original, lzma compressed"""
    blob = MAGIC
    for src, dst, data in chips(reg):
        old = orig_chips[src]
        x = lzma.compress(bytes(p ^ q for p, q in zip(data, old)), preset=9)
        for s in (src.encode(), dst.encode()):
            blob += struct.pack('B', len(s)) + s
        blob += struct.pack('>III', zlib.crc32(old), zlib.crc32(data), len(x)) + x
    return blob
