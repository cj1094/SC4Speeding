"""Verify the original EXE network altitude ABI and world-coordinate sampling."""
import contextlib,io,runpy,sys,struct
import pathlib
sys.argv=[str(pathlib.Path(__file__).with_name('emulate_dll.py')),'success']
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(sys.argv[0])
u=d['u'];alloc=d['alloc'];call=d['call'];ptr=alloc(512);out=alloc(4);code=alloc(128)
def f(p,v):u.mem_write(p,struct.pack('<f',v))
f(0xb0b384,1.0/16)
f(ptr+0x9c,96);f(ptr+0xa4,96)
for off,h in zip([0xa0,0xb8,0xd0,0xe8],[0,1,2,3]):f(ptr+off,h)
for slope_x,slope_z in [(.05,.08),(-.1,.03),(0,0)]:
 base=3.0
 # Native stored corner order: (0,0),(0,16),(16,16),(16,0).
 for off,(x,z) in zip([0xa0,0xb8,0xd0,0xe8],[(0,0),(0,16),(16,16),(16,0)]):f(ptr+off,base+slope_x*x+slope_z*z)
 for x,z in [(96,96),(112,96),(96,112),(112,112),(100,107),(109,99)]:
  code=alloc(128)
  b=b'\x68'+struct.pack('<f',z)+b'\x68'+struct.pack('<f',x)+b'\xb9'+struct.pack('<I',ptr)+b'\xb8'+struct.pack('<I',0x6197f0)+b'\xff\xd0\xd9\x1d'+struct.pack('<I',out)+b'\xc3'
  u.mem_write(code,b);call(code)
  height=struct.unpack('<f',u.mem_read(out,4))[0]
  assert abs(height-(base+slope_x*(x-96)+slope_z*(z-96)))<.0001,(x,z,height)
print('PASS: supplied EXE6197f0 returns road-piece height at world X/Z using x87 float; three planes, both triangles and nonzero tile origin.')
print('Simulation initialization of native cell-width reciprocal is mocked. Actual renderer/game not run.')
