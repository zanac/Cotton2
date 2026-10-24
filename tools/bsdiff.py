import bz2, struct
def offtin(b):
    y=int.from_bytes(b[:7]+bytes([b[7]&0x7f]),'little')
    return -y if b[7]&0x80 else y
def info(patch):
    assert patch[:8]==b'BSDIFF40'
    return offtin(patch[8:16]),offtin(patch[16:24]),offtin(patch[24:32])
def apply(old, patch):
    cl,dl,ns=info(patch)
    c=bz2.decompress(patch[32:32+cl]); d=bz2.decompress(patch[32+cl:32+cl+dl]); e=bz2.decompress(patch[32+cl+dl:])
    new=bytearray(ns); op=0; np_=0; ci=di=ei=0
    while np_<ns:
        x=offtin(c[ci:ci+8]); y=offtin(c[ci+8:ci+16]); z=offtin(c[ci+16:ci+24]); ci+=24
        for i in range(x):
            ob=old[op+i] if 0<=op+i<len(old) else 0
            new[np_+i]=(d[di+i]+ob)&255
        di+=x; np_+=x; op+=x
        new[np_:np_+y]=e[ei:ei+y]; ei+=y; np_+=y; op+=z
    return bytes(new)
