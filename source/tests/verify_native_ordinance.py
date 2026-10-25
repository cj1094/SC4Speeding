"""Validate the DAT and execute native ordinance state, cost and aggregation code."""
import contextlib,io,pathlib,runpy,sys,struct
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ui'));from resources import unpack
b=(ROOT/'build/140-ordinances/SC4Speeding-SpeedTraps.dat').read_bytes();count,index=struct.unpack_from('<II',b,36)
resources={}
for j in range(count):
 t,g,k,o,n=struct.unpack_from('<5I',b,index+j*20);resources[t,g,k]=unpack(b[o:o+n])
ID=0xf5ee0200;raw=resources[0x6534284a,0x2ecef8bb,ID];props={};p=24
for _ in range(struct.unpack_from('<I',raw,20)[0]):
 key,kind,flags=struct.unpack_from('<IHH',raw,p);p+=9;n=1
 if flags==0x80:n=struct.unpack_from('<I',raw,p)[0];p+=4
 if kind==0xc00:value=raw[p:p+n].decode('ascii');p+=n
 else:
  fmt={0x300:'I',0x700:'i',0x900:'f',0x800:'q',0xb00:'B'}[kind];sz=struct.calcsize(fmt);value=struct.unpack_from('<'+fmt*n,raw,p);p+=sz*n;value=value[0] if n==1 else value
 props[key]=value
assert props[0x10]==14
def ltext(key):
 value=resources[tuple(key)];length=struct.unpack_from('<I',value)[0]
 assert length>>24==0x10 and len(value)==4+(length&0xffffff)*2
 return value[4:].decode('utf-16le')
assert ltext(props[0x6a416b21])=='Speed Traps'
assert ltext(props[0xca416b2a])=='Speeding deterrent for cities.'
assert props[0x28ebbc30]==ID
assert set(props)=={0x10,0x20,0x28ebbc30,0x28ebbc37,0x28ebbc38,0x28ebbc39,0x6a416b21,0xca416b2a,0xaa5b8407,0x6b23d823,0x6b23d800,0x6b23d803,0x6b23d923}
assert props[0x28ebbc39]==-60 and props.get(0x28ebbc3a,0)==0
assert props[0x28ebbc37]==props[0x28ebbc38]==0
assert props[0xaa5b8407]==5 and props[0x6b23d923]==-10
assert props[0x6b23d823]==1
assert props[0x6b23d800]==1000 and props[0x6b23d803]==100
for stations in (0,1,2,10,100):assert -(props[0x28ebbc39]+stations*props[0x6b23d923])==60+10*stations
sys.argv=[str(ROOT/'tests/emulate_dll.py'),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];p32=d['p32'];i32=d['i32'];call=d['call'];stub=d['stub']
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EIP,UC_X86_REG_EDX
ordinance=alloc(0xa0);p32(ordinance,0xabea10);p32(ordinance+0x38,ID)
u.mem_write(ordinance+0x80,struct.pack('<qf',props[0x28ebbc39],props.get(0x28ebbc3a,0)))
u.mem_write(ordinance+0x91,b'\x01\x00\x01') # available, unchecked, enabled
population,pv=d['obj'](24);d['setmethod'](population,16,lambda t,a:1000000);p32(0xb43da4,population)
date,dv=d['obj'](20)
def year(t,a):p32(a[0],2000);return 0
d['setmethod'](date,6,year,5);p32(0xb43d5c,date)
sim=alloc(0x50);p32(sim,0xabeac0)
head=alloc(24);node=alloc(24);p32(sim+0x30,head)
for off in (4,8,12):p32(head+off,node)
p32(node+4,head);p32(node+0x10,ID);p32(node+0x14,ordinance)
# Run the entire native monthly aggregation loop. Bypass only its trailing
# budget-change message allocation/broadcast, after all totals are committed.
epilogue=d['THUNK']+0xe0000;u.mem_write(epilogue,b'\x5f\x5e\x5d\x5b\x83\xc4\x08\xc3')
def end_notification(mu,a,size,data):
 if a==0x80da80:mu.reg_write(UC_X86_REG_EIP,epilogue)
u.hook_add(UC_HOOK_CODE,end_notification)
def signed64(addr,this,args=()):
 lo=call(addr,this,args);n=lo|(u.reg_read(UC_X86_REG_EDX)<<32);return n-(1<<64) if n>>63 else n
assert call(0x80e040,sim,(ID,))==ordinance
assert not call(0x80d470,sim,(ID,))&255
call(0x80d950,sim);assert signed64(0x80d500,sim)==0
call(0x80ca50,ordinance,(1,));assert call(0x80d470,sim,(ID,))&255
for _ in range(2):
 call(0x80d950,sim);assert signed64(0x80d500,sim)==60
 assert signed64(0x80d510,sim)==0
 assert signed64(0x80bca0,ordinance)==-60
call(0x80ca50,ordinance,(0,));call(0x80d950,sim)
assert not call(0x80d470,sim,(ID,))&255
assert signed64(0x80d500,sim)==0
assert signed64(0x80bca0,ordinance)==-60 # native totals exclude unchecked rows
print('PASS: Example-based DAT contains new type14 Speed Traps, exact description, $60 constant cost, police factor -10, +5 mayor rating, three minimum-one requirements and no switching fee.')
print('PASS: original EXE lookup and checkbox query recognize the unique ID; native monthly aggregation gives $60 when checked and $0 when unchecked.')
print('PASS: one-million population does not increase cost; repeated native monthly updates remain $60.')
print('Original EXE simple-ordinance baseline only: host eligibility/factor/effect execution and live saved-city behavior are not tested by this native baseline. Variable costs additionally checked from parsed DAT values.')
