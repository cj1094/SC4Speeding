"""Execute the original simulator's animation-time-dilation getter."""
import contextlib,io,pathlib,runpy,sys,struct
sys.argv=[str(pathlib.Path(__file__).with_name('emulate_dll.py')),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];call=d['call'];p32=d['p32'];stub=d['stub'];sim=d['sim'];ns=d['ns']
table=d['i32'](sim)
p32(table+ns.index('GetSimSpeed')*4,0x8265c0)
config=alloc(20);u.mem_write(config,struct.pack('<5f',.125,.75,1.25,2.5,0))
p32(sim+0x108,config)
controller,cvt=d['obj'](20);p32(cvt+13*4,stub(lambda t,a:0));p32(0xb43d44,controller)
out=alloc(4);code=d['THUNK']+0xf0000
# Native thiscall float result is returned in ST(0), not EAX.
u.mem_write(code,b'\xb9'+struct.pack('<I',sim)+b'\xb8'+struct.pack('<I',0x7026f0)+b'\xff\xd0\xd9\x1d'+struct.pack('<I',out)+b'\xc3')
for speed,expected in [(3,.75),(1,1.25),(2,2.5),(3,.75)]:
 p32(sim+0x3c,speed);call(code)
 actual=struct.unpack('<f',u.mem_read(out,4))[0]
 assert actual==expected,(speed,actual)
print('PASS: original EXE 7026f0 selects the configured animation factor at all three speeds.')
print('PASS: switching speed changes the returned factor immediately; no fixed multiplier assumed.')
print('Native getter in emulation; live animation/menu behavior still needs confirmation.')
