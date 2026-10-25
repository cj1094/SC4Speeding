"""Execute native collision candidate filtering before/after parking flags."""
import contextlib,io,pathlib,runpy,sys
sys.argv=[str(pathlib.Path(__file__).with_name('emulate_dll.py')),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];call=d['call'];p32=d['p32'];i32=d['i32'];stub=d['stub']
vt=alloc(220*4);p32(vt+31*4,0x4fad60);p32(vt+85*4,stub(lambda t,a:0))
source=alloc(0x300);p32(source,vt)
scene=[]
for _ in range(3):
 a=alloc(0x300);p32(a,vt);p32(a+0x84,8);scene.append(a)
for a in scene:assert call(0x5059c0,source,(a,))&255
for a in scene[:2]:
 call(0x4fad20,a,(8,0))
 assert not call(0x5059c0,source,(a,))&255
assert call(0x5059c0,source,(scene[2],))&255
assert i32(scene[2]+0x84)==8
print('PASS: original EXE collision filter accepts moving collision-enabled vehicles.')
print('PASS: clearing Collide on parked scene cars excludes them from the native candidate filter.')
print('PASS: an unrelated vehicle remains eligible and its flags unchanged.')
print('Native filter in emulation; live traffic resumption still requires in-game confirmation.')
