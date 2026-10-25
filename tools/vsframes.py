import struct
from c2lib import mf_parse, spt_entries, unlz


def frames(mf):
    """per SCH pointer: (sprite pixels, rest of record, sprite index)"""
    m = {n: x for n, x, s in mf_parse(mf)}
    k = [n for n in m if n.endswith('.SCH')][0][:-4]
    sch = m[k + '.SCH']
    first = struct.unpack('>I', sch[:4])[0]
    ptr = [struct.unpack('>I', sch[i:i + 4])[0] for i in range(0, first, 4)]
    E = spt_entries(m[k + '.SPT'])
    idx = {o: i for i, (o, h, d) in enumerate(E)}
    img = {o: (unlz(d) if d[:4] == b'LZ00' else d) for o, h, d in E}
    out = []
    for p in ptr:
        r = sch[p:p + 20]
        if len(r) < 20:
            out.append(None)
            continue
        o = struct.unpack('>I', r[:4])[0]
        out.append((img.get(o), r[4:], idx.get(o, -1)))
    return out
