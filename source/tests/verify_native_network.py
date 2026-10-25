"""Verify network edge masks using the original executable methods."""
import contextlib,io,pathlib,runpy,sys,struct
sys.argv=[str(pathlib.Path(__file__).with_name('emulate_dll.py')),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];call=d['call'];p32=d['p32']
network=alloc(0x180)
for mask in range(16):
 raw=sum((1<<(edge*8)) for edge in range(4) if mask&(1<<edge))
 p32(network+0x110,raw)
 # Store's primary network type defaults to Road(0).
 assert call(0x61aee0,network,(0,))==mask
 assert call(0x61ae90,network)==mask
extra=alloc(8);p32(extra,1);p32(extra+4,0x00000100)
u.mem_write(network+0x108,b'\x01');p32(network+0x114,extra);p32(network+0x110,0x00010001)
assert call(0x61aee0,network,(0,))==5
assert call(0x61ae90,network)==7
print('PASS: original EXE network methods return four cyclic edge bits for all16 masks.')
print('PASS: combined network mask exposes a side branch absent from the Road-only mask.')
print('Original code in emulation; actual game placement remains unverified.')
