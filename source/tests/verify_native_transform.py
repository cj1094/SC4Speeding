"""Exercise original EXE math/transform helpers in Unicorn, not the game loop.
Model callbacks are simulated. Requires the separately supplied reference EXE.
"""
from pathlib import Path
import os, struct
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EAX
root=Path(__file__).resolve().parents[1]
pe=pefile.PE(str(os.environ.get('SC4_TEST_EXE',root.parent/'upload'/'SimCity 4(1).exe')))
u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(0x400000,pe.get_memory_mapped_image())
for p in [0x20000000,0x30000000,0x50000000,0x60000000]:u.mem_map(p,0x10000)
def put(p,*v):u.mem_write(p,struct.pack('<'+'I'*len(v),*v))
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
for direction in [(0,0,1),(1,0,0),(0,0,-1),(-1,0,0)]:
 u.mem_write(0x20000000,struct.pack('<3f',*direction));put(0x30008000,0x60000000,0x20000000,0x20000100);u.reg_write(UC_X86_REG_ESP,0x30008000)
 u.emu_start(0x80b830,0x60000000,count=10000)
 m=struct.unpack('<9f',u.mem_read(0x20000100,36))
 assert max(abs(a-b) for a,b in zip((m[2],m[5],m[8]),direction))<1e-6
 assert (m[1],m[4],m[7])==(0,1,0)
print('PASS: native 0x80B830 produces column-based direction/up matrices for four headings.')
actor,model,vbtable,models,tr=0x20001000,0x20002000,0x20003000,0x20004000,0x20005000
put(actor+0x110,models,models+4);put(models,model);put(model+4,vbtable);put(vbtable+4,0);put(vbtable+0x28,0x50000000)
# cS3DTransform: flags[4], rotation[9], translation[3], scale[1].
raw=struct.pack('<4B13f',2,5,0,0,1,0,0,0,1,0,0,0,1,100,3,118,1)
u.mem_write(tr,raw);u.mem_write(0x50000000,b'\xb8\x01\x00\x00\x00\xc2\x04\x00');seen=[]
def hook(mu,address,size,user):
 if address==0x50000000:
  assert mu.reg_read(UC_X86_REG_ECX)==model+4
  seen.append(bytes(mu.mem_read(word(mu.reg_read(UC_X86_REG_ESP)+4),56)))
u.hook_add(UC_HOOK_CODE,hook)
put(0x30008000,0x60000000,tr);u.reg_write(UC_X86_REG_ESP,0x30008000);u.reg_write(UC_X86_REG_ECX,actor)
u.emu_start(0x509440,0x60000000,count=10000)
assert seen==[raw] and u.reg_read(UC_X86_REG_EAX)&255==1
assert u.reg_read(UC_X86_REG_ESP)==0x30008008
print('PASS: original 0x509440 forwards all 56 transform bytes to a model and cleans its thiscall argument.')
print('Reference EXE helpers only; actual model rendering and the game loop are not tested.')
