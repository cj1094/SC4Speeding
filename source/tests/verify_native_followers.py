"""Execute original cached-leader refresh, path query and candidate filter."""
import contextlib,io,pathlib,runpy,sys,struct
sys.argv=[str(pathlib.Path(__file__).with_name('emulate_dll.py')),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];call=d['call'];p32=d['p32'];i32=d['i32'];stub=d['stub']
# Fixed-address emulator callbacks do not overwrite EXE instructions.
d['functions'].pop(0x54fbc0)
refs={};queries=[]
def ref(t,delta):refs[t]=refs.get(t,0)+delta;return 10
vt=alloc(201*4)
for slot,fn in [(1,stub(lambda t,a:ref(t,1))),(2,stub(lambda t,a:ref(t,-1))),
 (7,stub(lambda t,a:u.mem_write(a[0],bytes(u.mem_read(t+0x40,12))) or 0,1)),
 (31,0x4fad60),(73,0x5059c0),(85,0x4fad80),(136,0x504f70),
 (140,stub(lambda t,a:t+0x40)),(148,0x551c20)]:p32(vt+slot*4,fn)
def car(z):
 a=alloc(0x400);p32(a,vt);p32(a+0x84,8)
 u.mem_write(a+0x40,struct.pack('<fff',0,0,z))
 # An empty valid route deque: one map block and equal begin/end cursors.
 block=alloc(128);mp=alloc(4);p32(mp,block)
 for off in (0x204,0x208,0x214,0x218):p32(a+off,block)
 for off in (0x20c,0x21c):p32(a+off,block+120)
 p32(a+0x210,mp);p32(a+0x220,mp)
 p32(a+0x1ec,7);p32(a+0x1f4,0)
 return a
follower=car(0);second=car(-5);police=car(10);speeder=car(20);ordinary=car(40);unrelated=car(-20)
def linked(items):
 sentinel=alloc(12);nodes=[alloc(12) for _ in items];allnodes=[sentinel]+nodes
 for j,n in enumerate(allnodes):
  p32(n,allnodes[(j+1)%len(allnodes)]);p32(n+4,allnodes[(j-1)%len(allnodes)])
 for n,a in zip(nodes,items):p32(n+8,a)
 return sentinel
record=alloc(64);p32(record+0x1c,linked([follower,second,police,speeder,ordinary]))
network,nvt=d['obj'](64)
def lookup(t,a):queries.append(a[0]);return record if a[0]==7 else 0
p32(nvt+16*4,stub(lookup,1));p32(nvt+15*4,stub(lambda t,a:0,4));p32(0xb43d54,network)
manager,mvt=d['obj'](80);p32(manager+0x44,linked([follower,second,unrelated]))
p32(follower+0xb0,police);p32(second+0xb0,speeder);p32(unrelated+0xb0,ordinary)
# Existing behavior: each parked car is eligible; refreshing while collision
# remains enabled finds a scene car again and cannot release the queue.
assert call(0x551c20,follower)==second # nearest other eligible car
# Second follower is behind the source in this synthetic list, so disable it
# as a candidate to isolate the two parked leaders and a real car farther on.
call(0x4fad20,second,(8,0))
assert call(0x551c20,follower)==police
call(0x54fbc0,manager,(police,));assert i32(follower+0xb0)==police
refs.clear()
for a in (police,speeder):call(0x4fad20,a,(8,0))
assert i32(follower+0xb0)==police and i32(second+0xb0)==speeder
# New behavior: same original removal-time refresh, without removing actors.
for a in (police,speeder):call(0x54fbc0,manager,(a,))
assert i32(follower+0xb0)==ordinary and i32(second+0xb0)==ordinary
assert i32(unrelated+0xb0)==ordinary
assert refs=={ordinary:2,police:-1,speeder:-1},refs
assert all(i32(a+0x84)==0 for a in (police,speeder))
# With no eligible car ahead, native fallback clears the cached leader.
call(0x4fad20,ordinary,(8,0));p32(follower+0xb0,police)
call(0x54fbc0,manager,(police,));assert i32(follower+0xb0)==0
print('PASS: original EXE follower cache stays attached when only Collide is cleared.')
print('PASS: native 54fbc0 -> 551c20 -> 54fc30 -> 5059c0 selects the next eligible car.')
print('PASS: native AddRef/Release balances; unrelated follower is unchanged; empty lane clears leader.')
print('Native functions in emulation; actual game traffic still requires confirmation.')
