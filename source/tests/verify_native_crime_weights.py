"""Run the supplied EXE's weighted-choice loop with controlled random draws."""
import contextlib,io,pathlib,runpy,sys,struct
from unicorn.x86_const import *
sys.argv=[str(pathlib.Path(__file__).with_name('emulate_dll.py')),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];p32=d['p32'];stub=d['stub']
weights=[0,3,2,.5,3,2,3,3,2,2,4,4,4,4,4]
ids=[1,3,4,5,6,7,8,9,10,11,12,13,14,15,112]
registry=alloc(4*len(ids));indices=alloc(4*len(ids));records=[]
for i,(id,w) in enumerate(zip(ids,weights)):
 rec=alloc(80);records.append(rec);p32(rec,id);u.mem_write(rec+0x38,struct.pack('<f',w));p32(registry+4*i,rec);p32(indices+4*i,i)
p32(0xb48620,registry);p32(0xb48624,registry+4*len(ids))
random_draw=0.0
rng=stub(lambda t,a:random_draw,4,True,fixed=0x913a46)
# Fixed-address float callbacks need the x87-return stub bytes at that address.
result=d['functions'][rng][3];u.mem_write(rng,b'\xd9\x05'+struct.pack('<I',result)+b'\xc2\x10\x00')
def choose(draw,total):
 global random_draw
 random_draw=draw;esp=0x30170000
 u.reg_write(UC_X86_REG_ESP,esp);u.reg_write(UC_X86_REG_EBX,indices);u.reg_write(UC_X86_REG_ESI,indices+4*len(ids))
 u.mem_write(esp+0x10,struct.pack('<f',total));u.reg_write(UC_X86_REG_FPCW,0x37f)
 u.emu_start(0x6a1b43,0x6a1b9b,count=10000)
 assert u.reg_read(UC_X86_REG_ESP)==esp
 rec=u.reg_read(UC_X86_REG_EBP);return d['i32'](rec)
start=0
for id,w in zip(ids,weights):
 if w:assert choose(start+w*.5,sum(weights))==id
 start+=w
assert sum(weights)==40.5
# Disabling only the Speeding record removes it from selection.
u.mem_write(records[-1]+0x38,struct.pack('<f',0))
for n in range(365):assert choose((n+.5)/10,36.5)!=112
print('PASS: original EXE6a1b43..6a1b9b selects all expected weighted intervals; Speeding weight4 equals Graffiti/Pie/TP/Flashing; total40.5.')
print('PASS: Speeding weight0 prevents selection while retaining stock weights. Controlled RNG and prefiltered candidate list are mocked; monthly simulator not run.')
