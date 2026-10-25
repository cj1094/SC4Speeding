"""Execute original EXE flag methods to verify slots and x86 stack cleanup."""
import pathlib,struct
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX
root=pathlib.Path(__file__).resolve().parents[2]
p=pefile.PE(str(root/'upload/SimCity 4(1).exe'));u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,0x7c8000);u.mem_write(0x400000,p.get_memory_mapped_image())
u.mem_map(0x20000000,0x10000);window=0x20000000;stack=0x20008000;stop=0x2000f000
u.mem_write(window,struct.pack('<I',0xab7ee0))
def read(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def invoke(slot,args):
 addr=read(0xab7ee0+4*slot)
 u.mem_write(stack,struct.pack('<'+'I'*(1+len(args)),stop,*args))
 u.reg_write(UC_X86_REG_ESP,stack);u.reg_write(UC_X86_REG_ECX,window)
 u.emu_start(addr,stop,count=10000)
 return u.reg_read(UC_X86_REG_EAX),u.reg_read(UC_X86_REG_ESP)
assert read(0xab7ee0+67*4)==0x99bdbb
assert read(0xab7ee0+68*4)==0x99db6b
u.mem_write(window+0xcc,struct.pack('<I',0x12345678))
u.mem_write(window+0xc8,struct.pack('<I',1))
assert invoke(67,(1,))==(1,stack+8)
assert read(window+0xcc)==0x12345678
# Flag8 has no visibility/layout callbacks: run the complete native setter,
# verify its two-argument cleanup and the correct flag field in both states.
assert invoke(68,(8,1))==(9,stack+12)
assert invoke(68,(8,0))==(1,stack+12)
assert read(window+0xcc)==0x12345678
# Reproduce the two defects in 0.29 without running the game.
invoke(66,(1,));assert read(window+0xcc)==1
_,esp=invoke(67,(1,0));assert esp==stack+8 and esp!=stack+12
print('PASS: native GetFlag67 and SetFlag68 preserve instance ID and clean 1/2 arguments correctly.')
print('CONFIRMED: old slot66 writes instance data; old setter via slot67 leaves one stack argument behind.')
print('Native ABI emulation only; city-load crash recovery still requires in-game verification.')
