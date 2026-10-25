import capstone
md=capstone.Cs(capstone.CS_ARCH_SH, capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_SH2)
def dis(b,start,end,base):
    out=[]
    o=start&~1
    while o<end:
        w=b[o:o+2]
        ins=list(md.disasm(w,base+o))
        s=(ins[0].mnemonic+' '+ins[0].op_str) if ins else '.word 0x'+w.hex()
        out.append('%08x: %s  %s'%(base+o,w.hex(),s)); o+=2
    return '\n'.join(out)
