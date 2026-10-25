import struct,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def unpack(b):
    if len(b)<9 or b[4:6]!=b'\x10\xfb':return b
    n=int.from_bytes(b[6:9],'big');i=9;o=bytearray()
    while i<len(b):
        c=b[i];i+=1
        if c>=252:
            k=c&3;o+=b[i:i+k];break
        if c>=224:
            k=((c&31)<<2)+4;o+=b[i:i+k];i+=k;continue
        if c>=192:
            a,d,e=b[i:i+3];i+=3;k=c&3;dist=((c&16)<<12)+(a<<8)+d+1;ln=((c&12)<<6)+e+5
        elif c>=128:
            a,d=b[i:i+2];i+=2;k=a>>6;dist=((a&63)<<8)+d+1;ln=(c&63)+4
        else:
            a=b[i];i+=1;k=c&3;dist=((c&96)<<3)+a+1;ln=((c&28)>>2)+3
        o+=b[i:i+k];i+=k
        for _ in range(ln):o.append(o[-dist])
    assert len(o)==n,(len(o),n)
    return bytes(o)
def entries():
    b=(ROOT/'game-data/SimCity_1.dat').read_bytes();n,p=struct.unpack_from('<II',b,36)
    for j in range(n):
        t,g,k,off,size=struct.unpack_from('<5I',b,p+j*20)
        yield (t,g,k),b[off:off+size]
if __name__=='__main__':
    dest=ROOT/'analysis/ui';dest.mkdir(exist_ok=True)
    for tgi,b in entries():
        if tgi[0]==0 or tgi==(0x7ab50e44,0x1abe787d,0xaa63a98d):
            d=unpack(b);(dest/('%08x-%08x-%08x.bin'%tgi)).write_bytes(d)
            if b'crime' in d.lower():print(tgi,len(d),d[:180])
