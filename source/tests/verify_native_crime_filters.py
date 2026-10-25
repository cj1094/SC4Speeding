"""Exercise native scalar/array variants and the crime mask builder."""
import contextlib,io,pathlib,runpy,sys,struct
from unicorn.x86_const import *
sys.argv=[str(pathlib.Path(__file__).with_name('emulate_dll.py')),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];call=d['call'];p32=d['p32'];i32=d['i32']
def mask(values):
 vector=alloc(12);data=alloc(max(1,len(values)));out=alloc(4)
 u.mem_write(data,bytes(values));p32(vector,data);p32(vector+4,data+len(values));p32(vector+8,data+len(values))
 u.reg_write(UC_X86_REG_ESI,vector);u.reg_write(UC_X86_REG_EDI,out);call(0x69fcf0)
 return i32(out)
# Run native scalar setter, not a mocked GetCount result.
scalar=alloc(32);p32(scalar,0xaa6788);call(0x9157d9,scalar,[1])
assert call(0x40ce60,scalar)==0
assert mask([])==0,'The native empty-vector path excludes every lot'
# An explicit one-element array supplies the required native count.
array=alloc(32);data=alloc(1);u.mem_write(data,b'\x01');p32(array,0xaa6788);p32(array+4,data);u.mem_write(array+14,struct.pack('<H',0x8002));p32(array+16,1)
assert call(0x40ce60,array)==1
assert mask([1])==1
assert mask([1,2])==3
assert mask([0])==0xffffffff
# Confirm the shipped DBPF actually stores all filter values as arrays.
b=(pathlib.Path(__file__).resolve().parents[1]/'build/SC4Speeding.dat').read_bytes()
n,index=struct.unpack_from('<II',b,36);entry=next(struct.unpack_from('<5I',b,index+20*i) for i in range(n) if struct.unpack_from('<III',b,index+20*i)==(0x6534284a,0xea12f32c,112))
e=b[entry[3]:entry[3]+entry[4]];count=struct.unpack_from('<I',e,20)[0];o=24;found={}
for _ in range(count):
 id,t,kind,unknown=struct.unpack_from('<IHHB',e,o);o+=9;length=1
 if kind==0x80:length=struct.unpack_from('<I',e,o)[0];o+=4
 size={0x100:1,0x300:4,0x900:4,0xc00:1}[t]*length
 if id in (0xaa12fcb3,0xaa12fcb4,0xaa12fcb7):
  assert kind==0x80 and length>0,(hex(id),kind,length)
  found[id]=mask(list(e[o:o+size]))
 o+=size
assert found=={0xaa12fcb3:1,0xaa12fcb4:3,0xaa12fcb7:0xffffffff}
print('PASS: shipped DBPF filter arrays produce the expected nonzero native masks.')
print('PASS: actual native scalar Uint8 setter leaves count0; crime empty-array mask is0 (rejects all lots).')
print('PASS: explicit Uint8 array[1] gives wealth mask1; array[1,2] purpose mask3; array[0] condition maskFFFFFFFF.')
print('Native variant and mask code run in emulation; serialized arrays are additionally checked structurally. Full game not run.')
