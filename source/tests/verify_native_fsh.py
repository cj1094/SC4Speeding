"""Feed the new marker to the original EXE's real SHPI resource loader.
Simulated memory stream and allocator only; the parser and resource load code
execute from the supplied executable, not a Python reimplementation.
"""
import contextlib,io,pathlib,runpy,sys,struct
sys.argv=[str(pathlib.Path(__file__).with_name('emulate_dll.py')),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];stub=d['stub'];obj=d['obj'];setmethod=d['setmethod'];call=d['call'];p32=d['p32'];i32=d['i32']
raw=(pathlib.Path(__file__).resolve().parents[1]/'build/speeding-marker.resource').read_bytes()
assert raw[:4]==b'SHPI'
stub(lambda t,a:alloc(a[0]),1,fixed=0x5e55e0)
stub(lambda t,a:0,1,fixed=0x5e5620)
resource=alloc(128);vtable=alloc(32);p32(resource,vtable);p32(vtable+20,stub(lambda t,a:0x7ab50e44))
p32(resource+0x18+0xc,0xffffffff)
stream,_=obj(40);offset=[0]
def read(t,a):
 dest,n=a
 if offset[0]+n>len(raw):return 0
 u.mem_write(dest,raw[offset[0]:offset[0]+n]);offset[0]+=n;return 1
setmethod(stream,27,read,2)
assert call(0x800860,0,(resource,stream))&255,'Native bitmap resource loader rejected SHPI gauge'
assert i32(resource+0x34)==16 and i32(resource+0x38)==16
assert i32(resource+0x30)==1,'Unexpected mip count'
assert offset[0]==len(raw)
print('PASS: original EXE 0x800860 loader accepts dedicated SHPI gauge; 16x16; one mip.')
# Verify the parser retains the complete BGRA pixel payload in its SHPI buffer.
pixels=i32(resource+0x18)+40
assert bytes(u.mem_read(pixels,1024))==raw[40:]
print('PASS: native loader retains all 256 BGRA pixels exactly; no PNG decoder or stock icon replacement.')
print('Original loader in emulation; actual game minimap rendering still unverified.')

# Regression: the formerly packaged PNG is rejected by this same native loader.
raw=(pathlib.Path(__file__).resolve().parents[1]/'build/speeding-gauge.png').read_bytes()
offset[0]=0
bad=alloc(128);p32(bad,vtable);p32(bad+0x18+0xc,0xffffffff)
assert not (call(0x800860,0,(bad,stream))&255)
print('PASS: the same native loader rejects the old PNG payload.')
