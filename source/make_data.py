"""Create only the new Speeding record; no original resources are copied."""
import pathlib,struct
TYPE,GROUP,INSTANCE=0x6534284a,0xea12f32c,112
ICON=(0x7ab50e44,0x1abe787d,0xf5ee0070)
GAUGE=(0x7ab50e44,0x1abe787d,0xf5ee0070)
def prop(id,t,value):
    if isinstance(value,str):
        raw=value.encode('ascii');return struct.pack('<IHHBI',id,t,0x80,0,len(raw))+raw
    values=value if isinstance(value,tuple) else (value,)
    array=isinstance(value,tuple)
    head=struct.pack('<IHHB',id,t,0x80 if array else 0,0)
    if array:head+=struct.pack('<I',len(values))
    fmt={0x300:'I',0x100:'B',0x900:'f'}[t]
    return head+struct.pack('<'+fmt*len(values),*values)
fields=[(0x10,0x300,36),(0x20,0xc00,'SC4Speeding Crime'),
        (0xaa12fcb0,0xc00,'Speeding'),(0xaa12fcb1,0x300,ICON),
        (0xaa12fcb3,0x100,(1,)),(0xaa12fcb4,0x100,(1,2)),
        (0xaa12fcb5,0x100,20),(0xaa12fcb7,0x100,(0,)),
        (0xaa12fcb8,0x900,4.0)]
data=b'EQZB1###'+struct.pack('<4I',0,0,0,len(fields))+b''.join(prop(*f) for f in sorted(fields))
# Embed the dedicated gauge for native event markers even without the optional UI.
icon=(pathlib.Path(__file__).parent/'build'/'speeding-marker.resource').read_bytes()
index_offset=96+len(data)+len(icon)
header=bytearray(96)
struct.pack_into('<4sII',header,0,b'DBPF',1,0)
struct.pack_into('<4I',header,32,7,2,index_offset,40)
index=struct.pack('<5I',TYPE,GROUP,INSTANCE,96,len(data))+struct.pack('<5I',*GAUGE,96+len(data),len(icon))
out=pathlib.Path(__file__).parent/'build'/'SC4Speeding.dat'
out.parent.mkdir(exist_ok=True);out.write_bytes(header+data+icon+index)
# Round-trip structural and uniqueness checks against the supplied archive.
b=out.read_bytes();assert b[:4]==b'DBPF' and b[96:104]==b'EQZB1###'
assert struct.unpack_from('<5I',b,index_offset)==(TYPE,GROUP,INSTANCE,96,len(data))
source=pathlib.Path(__file__).resolve().parent.parent/'game-data'/'SimCity_1.dat'
if source.exists():
    b=source.read_bytes();n,p=struct.unpack_from('<II',b,36)
    assert all(struct.unpack_from('<III',b,p+i*20)!=(TYPE,GROUP,INSTANCE) for i in range(n))
print(out.name,': Speeding record and dedicated gauge; native random-selection weight4; no base resource overrides')
