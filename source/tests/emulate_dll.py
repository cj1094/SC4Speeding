"""Execute the actual x86 DLL against simulated Win32/SC4 interfaces.
This is an ABI/integration smoke test, not a test in the real game.
Requires unicorn and pefile. Never executes or modifies the uploaded EXE.
"""
import pathlib,struct,json,sys,os
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
MODE=sys.argv[1] if len(sys.argv)>1 else 'success'
if MODE=='camera-refocus':MODE='hotkey-restart'
restart_pressed=False
overlap_paused=False
MONTHLY_EVENTS=MODE=='monthly-events' or MODE.startswith('monthly-overlap-')
LHD=MODE in ('shoulder-left','officer-left')
ROOT=pathlib.Path(__file__).resolve().parents[1]
u=Uc(UC_ARCH_X86,UC_MODE_32)
STOP=0x60000000;STACK=0x30000000;HEAP=0x20000000;THUNK=0x50000000
for a,n in [(STACK,0x200000),(HEAP,0x1000000),(THUNK,0x100000),(STOP,0x1000)]:u.mem_map(a,n)
heap=HEAP;thunk=THUNK;functions={};clock=1000;logs=[];notices=[];actors={};removed=[];controls=[];counts={};tick_target=hook_target=message_target=0

def p32(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def i32(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def alloc(n):
 global heap
 a=heap;heap=(heap+n+15)&~15;return a

def cstring(a):
 if not a:return ''
 r=bytearray()
 while (b:=u.mem_read(a+len(r),1))!=b'\0':r+=b
 return r.decode('ascii')
def string(s):a=alloc(len(s)+1);u.mem_write(a,s.encode()+b'\0');return a

def stub(callback,nargs=0,floatret=False,fixed=None):
 global thunk
 a=fixed if fixed else thunk
 if not fixed:thunk+=32
 result=alloc(4)
 code=(b'\xd9\x05'+struct.pack('<I',result)+b'\xc2'+struct.pack('<H',nargs*4)) if floatret else b'\xc3'
 
 if not fixed:u.mem_write(a,code)
 functions[a]=(callback,nargs,floatret,result);return a

def on_code(mu,address,size,data):
 if address==STOP:mu.emu_stop();return
 if address not in functions:return
 cb,n,fp,out=functions[address];esp=mu.reg_read(UC_X86_REG_ESP);args=[i32(esp+4+4*j) for j in range(n)];this=mu.reg_read(UC_X86_REG_ECX)
 value=cb(this,args)
 if fp:u.mem_write(out,struct.pack('<f',float(value)));return
 mu.reg_write(UC_X86_REG_EAX,int(value or 0)&0xffffffff);mu.reg_write(UC_X86_REG_ESP,esp+4+(0 if address in (0x90cf63,0x5e55e0,0x5e5620) else n*4));mu.reg_write(UC_X86_REG_EIP,i32(esp))
u.hook_add(UC_HOOK_CODE,on_code)

def load_pe(path):
 pe=pefile.PE(str(path));a=pe.OPTIONAL_HEADER.ImageBase;n=(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095
 u.mem_map(a,n);u.mem_write(a,pe.get_memory_mapped_image());return pe,a
exe,exe_base=load_pe(pathlib.Path(os.environ.get('SC4_TEST_EXE',str(ROOT.parent/'upload'/'SimCity 4(1).exe'))))
dll,base=load_pe(pathlib.Path(os.environ.get('SC4_TEST_DLL',str(ROOT/'build'/'SC4Speeding.dll'))))

def win(name,args):
 global clock
 if name=='DisableThreadLibraryCalls':return 1
 if name=='GetModuleHandleA':return exe_base
 if name=='GetModuleFileNameA':s=b'C:\\Plugins\\SC4Speeding.dll\0';u.mem_write(args[1],s);return len(s)-1
 if name=='GetTickCount':return clock
 if name=='GetCurrentThreadId':return 1
 if name=='GetPrivateProfileIntA':
  key=cstring(args[1])
  if key=='LeftHandDrive' and LHD:return 1
  if key=='ShoulderOffsetCentimeters' and MODE=='shoulder-custom':return 150
  return args[2]
 if name=='GetAsyncKeyState':
  pressed=MODE.startswith('camera-') and (((4500<=clock<4750) if MODE=='camera-ordinance-repeal' else (1500<=clock<1750)) or (MODE=='camera-refocus' and 2500<=clock<2750))
  if MODE=='hotkey-restart' or MODE=='monthly-overlap-hotkey':pressed=restart_pressed
  return 0x8000 if pressed and args[0] in (0x11,0x10,0x79) else 0
 if name=='CreateFileA':return 100
 if name=='CloseHandle':return 1
 if name=='WriteFile':
  text=bytes(u.mem_read(args[1],args[2])).decode();logs.append(text);p32(args[3],args[2]);return 1
 if name.startswith('waveOut'):
  if name=='waveOutOpen':p32(args[0],123)
  counts[name]=counts.get(name,0)+1;return 0
 raise AssertionError(name)
arity={'DisableThreadLibraryCalls':1,'GetModuleHandleA':1,'GetModuleFileNameA':3,'GetTickCount':0,'GetCurrentThreadId':0,'GetPrivateProfileIntA':4,'GetAsyncKeyState':1,'CreateFileA':7,'CloseHandle':1,'WriteFile':5,'waveOutOpen':6,'waveOutClose':1,'waveOutReset':1,'waveOutPrepareHeader':3,'waveOutUnprepareHeader':3,'waveOutWrite':3}
for desc in dll.DIRECTORY_ENTRY_IMPORT:
 for item in desc.imports:
  name=item.name.decode();p32(item.address,stub(lambda t,a,name=name:win(name,a),arity[name]))

def call(address,this=0,args=()):
 esp=STACK+0x180000;u.reg_write(UC_X86_REG_ESP,esp);u.reg_write(UC_X86_REG_ECX,this)
 u.mem_write(esp,struct.pack('<'+'I'*(1+len(args)),STOP,*args));u.reg_write(UC_X86_REG_FPCW,0x37f)
 try:u.emu_start(address,STOP+1,count=10000000)
 except Exception:
  print("EMU failure",hex(u.reg_read(UC_X86_REG_EIP)),"ECX",hex(u.reg_read(UC_X86_REG_ECX)),"stack",[hex(i32(u.reg_read(UC_X86_REG_ESP)+i*4)) for i in range(8)])
  print("Actors",actors,"logs",logs,"frame",globals().get('frame'))
  raise
 assert u.reg_read(UC_X86_REG_EIP)==STOP,(hex(address),hex(u.reg_read(UC_X86_REG_EIP)))
 assert u.reg_read(UC_X86_REG_ESP)==esp+4+4*len(args),(hex(address),'stack imbalance',hex(u.reg_read(UC_X86_REG_ESP)))
 return u.reg_read(UC_X86_REG_EAX)

def method(obj,index,*args):return call(i32(i32(obj)+index*4),obj,args)
def obj(slots=128,size=256):
 a=alloc(size);v=alloc(slots*4);p32(a,v);return a,v
def setmethod(o,index,fn,n=0,fp=False,fixed=None):
 a=stub(fn,n,fp,fixed);p32(i32(o)+index*4,a);return a

def refs(o):
 setmethod(o,1,lambda t,a:2);setmethod(o,2,lambda t,a:1)
framework,fv=obj();app,av=obj();city,cv=obj();sim,sv=obj();manager,mv=obj(size=0xb00);ped,pev=obj();crimes,crv=obj();allocator,alv=obj();messages,msgv=obj();controllers,ctv=obj()

def getservice(t,a):
 services={(83526747,1696765127):messages,(988069539,988069547):allocator}
 assert tuple(a[:2]) in services, ('Invalid service/interface IDs',a[:2])
 missing=(MODE=='missing-message' and a[0]==83526747) or (MODE=='missing-allocator' and a[0]==988069539)
 p32(a[2],0 if missing else services[tuple(a[:2])]);return 0 if missing else 1
def getapp(t,a):p32(a[1],app);return 1
def addhook(t,a):
 global hook_target
 hook_target=a[0];return 1
def addtick(t,a):
 global tick_target
 tick_target=a[0];return 1
def notification(t,a):
 global message_target
 message_target=a[0];notices.append(a[1]);return 1
setmethod(framework,5,getservice,3);setmethod(framework,7,addhook,1);setmethod(framework,9,addtick,1);setmethod(framework,10,lambda t,a:1,1);setmethod(framework,37,lambda t,a:app)
setmethod(app,0,getapp,2);setmethod(app,37,lambda t,a:city);refs(app)
setmethod(messages,5,notification,2);setmethod(messages,6,lambda t,a:1,2);refs(messages)
setmethod(allocator,3,lambda t,a:alloc(a[0]),1);setmethod(allocator,4,lambda t,a:1,1);refs(allocator)
setmethod(sim,18,lambda t,a:0) # IsAnyPaused: corrected from SDK enumeration below
for index,value in [(43,manager),(44,ped),(47,controllers),(50,sim),(55,crimes)]:setmethod(city,index,lambda t,a,value=value:value)
for index,value in [(28,0.0),(89,1024.0),(90,1024.0)]:setmethod(city,index,lambda t,a,value=value:value,0,True)
def cell(t,a):
 x,z=struct.unpack('<ff',struct.pack('<II',a[0],a[1]));p32(a[2],int(x/16));p32(a[3],int(z/16));return 1
setmethod(city,95,cell,4)
# Derive the pause index from the SDK; no guessed vtable position in the test.
import re
s=(ROOT/'sdk/cISC4Simulator.h').read_text();ns=['QI','AddRef','Release']+re.findall(r'virtual\s+[^;]*?\b(\w+)\([^;]*?= 0;',s)
def user_pause():return MODE=='paused' and clock<11000
def modal_pause():return overlap_paused or MODE=='quit-menu' and (12500<=clock<15500 or 24000<=clock<27000)
def speed_scale():
 if MODE=='speed-switch':return 1 if clock<13000 else (3 if clock<17000 else 2)
 return {'speed-1':1,'speed-2':2,'speed-3':3}.get(MODE,1)
def hidden_pause():return MODE=='hidden-pauses' and 12500<=clock<18000 and (clock//500)%2==0
setmethod(sim,ns.index('IsPaused'),lambda t,a:int(user_pause()))
setmethod(sim,ns.index('IsEmergencyPaused'),lambda t,a:0)
setmethod(sim,ns.index('IsHiddenPaused'),lambda t,a:int(hidden_pause()))
setmethod(sim,ns.index('GetAnimationTimeDilation'),lambda t,a:speed_scale(),0,True)
setmethod(sim,ns.index('IsAnyPaused'),lambda t,a:int(user_pause() or hidden_pause()))
# Native ordinance service: persistent on/off is owned by the game.
ordinances,ordvt=obj();ordinance,ordobjvt=obj();ordinance_queries=[];ordinance_changes=[];ordinance_available=MODE not in ('ordinance-unavailable','ordinance-delayed')
def ordinance_on():
 if MODE in ('ordinance-on','camera-ordinance-active'):return True
 if MODE=='ordinance-enact':return clock>=13000
 if MODE=='camera-ordinance-repeal':return clock<4000
 return False
ordns=['QI','AddRef','Release']+re.findall(r'virtual\s+[^;]*?\b(\w+)\([^;]*?= 0;',(ROOT/'sdk/cISC4OrdinanceSimulator.h').read_text())
def ord_query(t,a):
 assert a[0]==0xf5ee0200,'Must query only the new ordinance'
 ordinance_queries.append(a[0]);return int(ordinance_on())
def ord_available(t,a):
 global ordinance_available
 assert a==[0xf5ee0200,1];ordinance_changes.append(tuple(a));ordinance_available=True;return 1
setmethod(ordinances,ordns.index('IsOrdinanceOn'),ord_query,1)
setmethod(ordinances,ordns.index('GetOrdinanceByID'),lambda t,a:ordinance if a[0]==0xf5ee0200 and MODE!='ordinance-missing' and (MODE!='ordinance-delayed' or clock>=7000) else 0,1)
setmethod(ordinances,ordns.index('SetOrdinanceAvailable'),ord_available,2)
setmethod(ordinances,ordns.index('IsOrdinanceAvailable'),lambda t,a:int(clock>=7000 if MODE=='ordinance-becomes-available' else clock<13000 if MODE=='ordinance-availability-lost' else ordinance_available),1)
# SDK method names and compiler-reversed overload order for network queries.
def names(header):return ['QI','AddRef','Release']+re.findall(r'virtual\s+[^;]*?\b(\w+)\([^;]*?= 0;',(ROOT/'sdk'/header).read_text())
occupants,omv=obj();network,nv=obj();occupant,ov=obj()
cn=names('cISC4City.h');setmethod(city,cn.index('GetOrdinanceSimulator'),lambda t,a:ordinances)
on=names('cISC4OccupantManager.h');nn=names('cISC4NetworkOccupant.h')
setmethod(city,cn.index('GetOccupantManager'),lambda t,a:occupants)
lot_manager,lmv=obj();test_lot,ltv=obj();lot_queries=[]
# Arbitrary exemplar IDs deliberately differ from census/developer categories.
p32(test_lot+0x3c,0x81234567)
building,bvt=obj();building_developer,bdvt=obj();building_profile=alloc(128)
purpose,wealth={'lot-cs':(2,1),'lot-r-medium':(1,2),'lot-cs-medium':(2,2),'lot-office':(3,1),'lot-industry':(6,1),'lot-empty':(0,0)}.get(MODE,(1,1))
p32(building_profile,purpose);p32(building_profile+4,wealth)
p32(building+0x38,0x81234567)
# Native building profile getter459250 forwards exemplar ID to developer slot39.
p32(bvt+11*4,0x459250);p32(0xb43d68,building_developer)
def get_profile(t,a):
 assert a==[0x81234567];return building_profile
setmethod(building_developer,39,get_profile,1)
setmethod(test_lot,48,lambda t,a:0 if MODE=='lot-empty' else building)
def wrong_lot_type(t,a):raise AssertionError('Do not classify exemplar IDs as developer categories')
setmethod(test_lot,46,wrong_lot_type,1)
def get_lot(t,a):
 x,y,z=struct.unpack('<3f',u.mem_read(a[0],12));cx,cz=int(x/16),int(z/16)
 hx,_,hz=last_road_heading
 start=(5 if hx<0 else 6,5 if hz<0 else 6)
 # Later intersection-retry anchor is z164 rather than100.
 if MODE=='intersection-retry' and road_candidates>1:start=(6,10)
 assert abs(cx-start[0])+abs(cz-start[1])==1,(MODE,(cx,cz),start)
 lot_queries.append((cx,cz))
 if MODE in ('lot-none','lot-diagonal','lot-later-tile','diag-lot'):return 0
 if MODE=='lot-right-only' and (cx,cz)!=(7,6):return 0
 return test_lot
setmethod(lot_manager,5,get_lot,1)
setmethod(city,cn.index('GetLotManager'),lambda t,a:0 if MODE=='lot-manager-missing' else lot_manager)

query_point=(0,0);query_count=0
def query_network(t,a):
 global query_point,query_count
 query_count+=1
 x,z=struct.unpack('<ff',struct.pack('<II',a[1],a[2]));query_point=(x,z)
 assert a[3], 'Must pass a road filter'
 exists=MODE!='missing-road' and not (MODE=='road-end' and z<92)
 p32(a[0],occupant if exists else 0);return int(exists)
# The filter overload is first in the MSVC pair.
setmethod(occupants,on.index('GetFirstOccupantByPosition'),query_network,4)
def network_qi(t,a):
 assert a[0]==0xa821ef94;p32(a[1],network);return 1
setmethod(occupant,0,network_qi,2);refs(network)
setmethod(network,nn.index('IsOfType'),lambda t,a:int(a[0]==0),1)
def intersection(t,a):
 return int((MODE=='overflow-intersection' and query_point[1]>110) or (MODE=='after-intersection' and query_point[1]<89) or (MODE=='no-padding-intersection' and query_point[1]<83) or MODE in ('intersection-only','diag-anchor') or (MODE=='intersection-retry' and query_point[1]<120))
setmethod(network,nn.index('IsIntersection'),intersection)
def active_edges(t,a):
 assert a[0]==0 # Road
 if MODE=='unflagged-junction':return 7
 if MODE=='inside-curve':return 3
 if MODE=='overflow-curve' and query_point[1]>110:return 3
 if MODE=='after-curve' and query_point[1]<89:return 3
 if MODE=='no-padding-curve' and query_point[1]<83:return 3
 if MODE=='bend-ahead' and query_point[1]>124:return 3
 if MODE=='crossing-ahead' and query_point[1]>124:return 15
 if MODE=='axis-change' and query_point[1]>124:return 10
 return 5
setmethod(network,nn.index('GetActiveEdgesForType'),active_edges,1)
setmethod(network,nn.index('GetActiveEdges'),lambda t,a:7 if MODE=='mixed-junction' else active_edges(t,[0]))

# Terrain sampling is independent of the scene motion: planar and invalid
# surfaces exercise height following, normal alignment and graceful failure.
terrain_obj,tv=obj();tn=names('cISTETerrainMap.h')
setmethod(city,cn.index('GetTerrain'),lambda t,a:0 if MODE=='terrain-missing' else terrain_obj)
def terrain_height(x,z):
 if MODE in ('terrain-slope','camera-slope'):return .05*(x-100)+.08*(z-100)
 if MODE=='terrain-crest':return .005*(z-110)*(z-110)-.5
 return 0.0
def terrain_normal(x,z):
 import math
 gx,gz=(.05,.08) if MODE in ('terrain-slope','camera-slope') else ((0,.01*(z-110)) if MODE=='terrain-crest' else (0,0))
 v=(-gx,1,-gz);n=math.sqrt(sum(a*a for a in v));return tuple(a/n for a in v)
def road_height(x,z):
 if MODE=='road-raised-surface':return 30+.08*(z-100)
 if MODE=='road-slope':return .05*(x-100)+.08*(z-100)
 if MODE=='road-crest':return .005*(z-110)*(z-110)-.5
 if MODE=='road-pieces':return .08*(z-100) if z<112 else .96-.04*(z-112)
 return terrain_height(x,z)
def network_altitude(t,a):
 x,z=struct.unpack('<ff',struct.pack('<II',*a));return float('nan') if MODE in ('terrain-invalid','diag-surface') else road_height(x,z)
setmethod(network,nn.index('GetAltitude'),network_altitude,2,True)
def terrain_alt(t,a):
 x,z=struct.unpack('<ff',struct.pack('<II',*a));return float('nan') if MODE=='terrain-invalid' else terrain_height(x,z)
def terrain_up(t,a):
 x,z=struct.unpack('<ff',struct.pack('<II',*a[:2]));u.mem_write(a[2],struct.pack('<fff',*terrain_normal(x,z)));return 0
setmethod(terrain_obj,tn.index('LocationIsInBounds'),lambda t,a:1,2)
# MSVC reverses the altitude overloads: the float pair is the second slot.
setmethod(terrain_obj,tn.index('GetAltitude')+1,terrain_alt,2,True)
setmethod(terrain_obj,tn.index('GetLerpedNormal'),terrain_up,3)
# Native camera renderer/control route, with original zoom/rotation sentinels.
renderer,rv=obj();camera,camv=obj(size=0x200);camera_pans=[]
p32(0xb43dd0,0 if MODE=='camera-no-renderer' else renderer)
setmethod(renderer,16,lambda t,a:camera)
u.mem_write(camera+0x108,b'ZOOMROTA')
def camera_pan(t,a):
 assert t==camera
 target=struct.unpack('<fff',u.mem_read(a[0],12));camera_pans.append(target)
 u.mem_write(camera+0x44,struct.pack('<fff',*target));return 1
stub(camera_pan,1,fixed=0x7cd810)
# Native registry stores ID + native string at offset 4.
def native_string(text):
 a,v=obj(8);chars=string(text);setmethod(a,5,lambda t,x:chars);return a
category=alloc(80);name=native_string('Speeding');u.mem_write(category+4,bytes(u.mem_read(name,20)));p32(category,112);u.mem_write(category+0x38,struct.pack('<f',4.0));u.mem_write(category+0x18,struct.pack('<4I',0xffffffff,1,3,0xffffffff))
if MODE=='crime-empty-filter':p32(category+0x24,0)
registry=alloc(4);p32(registry,category);p32(0xb48620,registry);p32(0xb48624,registry+4)
# Native category/model records, including the real tExemplarData layout.
exemplar=alloc(108);u.mem_write(exemplar+16,struct.pack('<III',0x5ad0e817,0xbadb57f1,0x106c0000));ename=native_string('Vehicle_Truck' if MODE=='diag-filter' else 'Vehicle_SedanCheap2_normal');u.mem_write(exemplar+28,bytes(u.mem_read(ename,20)))
setmethod(manager,25,lambda t,a:0 if MODE=='diag-exemplar' else exemplar,4,fixed=0x50be90);p32(pev+25*4,0x50be90)

road_candidates=0
last_road_heading={'diag-heading':(0,0,0),'diag-axis':(.6,0,.8),'steering-tail-east':(1,0,0),'steering-tail-west':(-1,0,0),'tile-east':(1,0,0),'tile-west':(-1,0,0),'tile-south':(0,0,-1),'curve-east':(1,0,0),'curve-west':(-1,0,0),'curve-reverse':(0,0,-1)}.get(MODE,(0,0,1))
def randompoint(t,a):
 global road_candidates
 assert a[0]==0x4002,'Only one road anchor may be searched; patrol position is derived'
 assert a[6]==0
 road_candidates+=1
 if MODE=='diag-no-point':return 0
 if MONTHLY_EVENTS and not restart_pressed:
  assert struct.unpack('<3f',u.mem_read(a[1],12))==(104.,0.,104.)
  assert struct.unpack('<f',struct.pack('<I',a[3]))[0]==48
 p=(100.0,0.0,164.0) if MODE=='intersection-retry' and road_candidates>1 else (100.0,0.0,100.0)
 u.mem_write(a[4],struct.pack('<fff',*p));return 1
setmethod(manager,16,randompoint,7,fixed=0x553080)

def actor_method(t,a,index):
 state=actors[t]
 if index==9:state['visible']=bool(a[0]);return 0
 if index==14:state['heading']=struct.unpack('<fff',u.mem_read(a[0],12));return 0
 if index==12:
  tr=struct.pack('<4B13f',2,5,0,0,1,0,0,0,1,0,0,0,1,*state['pos'],1)
  u.mem_write(a[0],tr);return 1
 if index==15:u.mem_write(a[0],struct.pack('<fff',*state['heading']));return 0
 if index==7:u.mem_write(a[0],struct.pack('<fff',*state['pos']));return 0
 if index==33:state['opacity']=struct.unpack('<f',struct.pack('<I',a[0]))[0];return 0
 if index==36:state['requested_speed']=struct.unpack('<f',struct.pack('<I',a[0]))[0];return 0
 if index==8:state['pos']=struct.unpack('<fff',u.mem_read(a[0],12));return 0
 if index in [5,6]:return t
 if index==30:
  flag,value=a
  if flag==8 and not value:
   cars=[v for v in actors.values() if v.get('group') in (0x4002,0x4228) and not v['removed'] and v['created_at']==state['created_at']]
   assert len(cars)==2
   hx,_,hz=last_road_heading;rx,rz=(-hz,hx) if not LHD else (hz,-hx)
   expected=1.5 if MODE=='shoulder-custom' else 2
   for car in cars:
    side=(car['pos'][0]-100)*rx+(car['pos'][2]-100)*rz
    assert abs(side-expected)<.001,'Traffic released before both cars reached shoulder'
   state['traffic_released_at']=clock
  state['flags']=(state.get('flags',8)|flag) if value else (state.get('flags',8)&~flag)
  return 0
 if index==31:return state['removed'] if a[0]==1 else int(bool(state.get('flags',8)&a[0]))
 if index==13:state['removed']=True;removed.append(t);return 0
 if index in [51,52]:
  state['state']=a[0]
  if a[0]==7:
   state['auto_motion']=False
   if state.get('group')==0x410d and MODE in ('officer-placement','officer-left'):
    x,y,z=state['pos'];state['pos']=(x+4,y,z) # native setup relocates ped
  return 1
 if index==57:return 1 if state['state']==a[0] else 0 # actual index is set below
 return 1
actor_source=(ROOT/'sdk/cISC4Automaton.h').read_text();anames=['QI','AddRef','Release']+re.findall(r'virtual\s+[^;]*?\b(\w+)\([^;]*?= 0;',actor_source)

def set_transform(t,a):
 import math
 raw=u.mem_read(a[0],56);matrix=struct.unpack('<9f',raw[4:40]);p=struct.unpack('<3f',raw[40:52])
 expected=terrain_normal(p[0],p[2]);up=(matrix[1],matrix[4],matrix[7])
 if MODE=='road-raised-surface':
  n=math.sqrt(1+.08**2);expected=(0,1/n,-.08/n)
 if MODE=='road-slope':
  n=math.sqrt(1+.05**2+.08**2);expected=(-.05/n,1/n,-.08/n)
 if MODE not in ('road-pieces','road-crest'):
  assert max(abs(x-y) for x,y in zip(up,expected))<.001,(up,expected)
 height_error=p[1]-road_height(p[0],p[2])-.05
 assert abs(height_error)<(.08 if MODE in ('terrain-crest','road-crest','road-pieces') else .001),(p,height_error)
 actors[t].setdefault('body_samples',[]).append((p,matrix))
 cols=[(matrix[i],matrix[i+3],matrix[i+6]) for i in range(3)]
 assert all(abs(sum(x*x for x in v)-1)<.001 for v in cols)
 assert all(abs(sum(x*y for x,y in zip(cols[i],cols[j])))<.001 for i,j in [(0,1),(1,2),(0,2)])
 assert tuple(raw[:2])==(2,5)
 actors[t]['matrix']=matrix;actors[t]['pos']=p;return 1
def create(t,a):
 if MODE=='diag-lead-create' and a[0]==0x4002:return 0
 if MODE=='diag-police-create' and a[0]==0x4228:return 0
 actor,v=obj(220,size=0x400);actors[actor]={'pos':struct.unpack('<fff',u.mem_read(a[1],12)),'state':0,'removed':False,'created_at':clock,'group':a[0],'traffic_effect':False,'heading':last_road_heading,'flags':8}
 if a[0]==0x4002 and MODE in ('spawn-height-above','spawn-height-below'):
  x,y,z=actors[actor]['pos'];actors[actor]['pos']=(x,y+(25 if MODE=='spawn-height-above' else -25),z)
 if a[0]==0x410d and MODE in ('officer-placement','officer-left'):
  x,y,z=actors[actor]['pos'];actors[actor]['pos']=(x-4,y,z)
 refs(actor)
 setmethod(actor,75,set_transform,1,fixed=0x509440)
 for index,n in [(5,0),(6,0),(7,1),(8,1),(9,1),(12,1),(13,1),(14,1),(15,1),(30,2),(31,1),(33,2),(36,2),(39,1),(95,1),(51,7),(52,7),(64,1)]:setmethod(actor,index,lambda t,a,index=index:actor_method(t,a,index),n)
 for i,n in enumerate(anames):
  if n=='FindState':setmethod(actor,i,lambda t,a:1 if actors[t]['state']==a[0] else 0,1)
  if n=='PlayAnim':setmethod(actor,i,lambda t,a:1,1)
 setmethod(actor,17,lambda t,a:1.0,0,True) # GetRadius
 setmethod(actor,34,lambda t,a:35.0,0,True)
 setmethod(actor,35,lambda t,a:35.0,0,True)
 if a[0]==0x4228:
  setmethod(actor,99,lights_visual,2,fixed=0x50eb20)
  # Real primary police table identity is required by the isolation guard.
  u.mem_write(0xa9a0c0,bytes(u.mem_read(v,201*4)));p32(0xa9a0c0+194*4,0x530af0)
  p32(actor,0xa9a0c0)
  if MODE=='police-conflict':p32(0xa9a0c0+194*4,stub(lambda t,a:0,1))
 return actor
setmethod(manager,15,create,7,fixed=0x505370);p32(pev+15*4,0x505370)
native_reclaim_calls=0
if MODE.startswith('native-create-'):
 def count_reclaim(mu,address,size,user):
  global native_reclaim_calls
  if address==0x50a740:native_reclaim_calls+=1
 u.hook_add(UC_HOOK_CODE,count_reclaim)
if MODE.startswith('native-create-'):
 p32(mv+46*4,0x510690);p32(mv+47*4,0x50a740)
 p32(manager+0x3c,100);p32(manager+0x40,200);p32(manager+0x48,0)
 u.mem_write(manager+0x4c,bytes([0 if MODE in ('native-create-inactive','native-create-boost-factory') else 1,0]))
 if MODE=='native-create-hard-cap':p32(manager+0x48,200)
 if MODE=='native-create-soft-cap':p32(manager+0x48,101)
 if MODE=='native-create-at-251':p32(manager+0x48,251);p32(manager+0x3c,250);p32(manager+0x40,0)
 registry_object,regvt=obj();factory,factoryvt=obj();factory_group=0x4002;registry_calls=0
 p32(manager+0xa80,registry_object);p32(manager+0xa44,0x4002);p32(manager+0xa48,0x12345678)
 def registry_lookup(t,a):
  global factory_group,registry_calls
  registry_calls+=1
  if registry_calls%2:factory_group=a[0]
  return 0
 setmethod(registry_object,6,registry_lookup,1)
 setmethod(manager,44,lambda t,a:0,1);setmethod(manager,7,lambda t,a:1,1)
 stub(lambda t,a:factory,0,fixed=0x90ddf1)
 def factory_create(t,a):
  assert a[:2]==[0x12345678,0xa9b40f05]
  result=0
  if MODE in ('native-create-success','native-create-hard-cap','native-create-soft-cap','native-create-at-251'):
   initial=alloc(12);u.mem_write(initial,struct.pack('<3f',100,0,100))
   result=create(manager,[factory_group,initial,0,exemplar+16,0,0,0])
  p32(a[2],result);return int(bool(result))
 setmethod(factory,3,factory_create,3)
 # Original model-initialization subroutine is outside these gate tests.
 stub(lambda t,a:0,1,fixed=0x510360)
 p32(0xb43cec,0)
 if MODE=='native-create-boost-factory':
  situation,svt=obj();setmethod(city,49,lambda t,a:situation)
  setmethod(situation,19,lambda t,a:1,1);setmethod(situation,27,lambda t,a:2);setmethod(situation,28,lambda t,a:0)
  p32(0xb43cec,city)

# MSVC reverses the two overloaded ChaseAutomaton declarations: two-actor call is slot 22.
def lights_visual(t,a):
 assert a[0]==2 and a[1]==t+0x2d0
 if MODE=='lights-unavailable':p32(a[1],0);return 0
 p32(a[1],alloc(16));actors[t]['lights']=True;return 1
def emergency_effect(t,a):
 actors[t]['traffic_effect']=bool(a[0])
 if not a[0]:actors[t]['lights']=False;p32(t+0x2d0,0)
 return 0
stub(emergency_effect,1,fixed=0x530af0)
def chase(t,a):
 police,offender=a
 pp,op=actors[police]['pos'],actors[offender]['pos']
 hx,hy,hz=last_road_heading
 assert abs((op[0]-pp[0])*hx+(op[2]-pp[2])*hz-10)<.001
 assert abs((op[0]-pp[0])*hz-(op[2]-pp[2])*hx)<.001
 assert actors[police]['heading']==last_road_heading
 assert actors[police]['requested_speed']<=actors[offender]['requested_speed']
 actors[police]['auto_motion']=True;actors[offender]['auto_motion']=True
 assert i32(a[0])!=0xa9a0c0,'Scene patrol must use a private table before pursuit'
 for slot in range(201):
  if slot!=194:assert i32(i32(a[0])+slot*4)==i32(0xa9a0c0+slot*4),slot
 assert i32(i32(a[0])-4)==i32(0xa9a0c0-4)
 return 1
setmethod(manager,22,chase,2)
def refresh_followers(t,a):
 assert t==manager and a[0] in actors
 cars=[v for v in actors.values() if v.get('group') in (0x4002,0x4228) and not v['removed'] and v['created_at']==actors[a[0]]['created_at']]
 assert len(cars)==2 and all(not v['flags']&8 for v in cars),'Refresh before both cars leave lane'
 actors[a[0]]['followers_refreshed_at']=clock
 return 0
setmethod(manager,69,refresh_followers,1,fixed=0x54fbc0)


def ctor_name(t,a):
 chars=string(cstring(a[0]));u.mem_write(t,struct.pack('<5I',0xa80810,chars,chars+len(cstring(chars)),chars+len(cstring(chars))+1,0));return t
stub(ctor_name,1,fixed=0x408480);stub(lambda t,a:0,1,fixed=0x90cf63)
def addcontroller(t,a):
 c,v=obj(40);refs(c);setmethod(c,18,lambda t,a:controls.append(bool(a[0])),1,fixed=None);p32(v+18*4,0x516aa0);return c
stub(lambda t,a:controls.append(bool(a[0])),1,fixed=0x516aa0)
setmethod(controllers,5,addcontroller,3)
# MSVC overload order for RemoveController places the one-argument call at slot 7.
setmethod(controllers,7,lambda t,a:1,1)

synthetic_native_records=[]
def native_incidents(t,a):
 if MONTHLY_EVENTS and synthetic_native_records:
  size=28*len(synthetic_native_records);start=i32(a[0]);cap=i32(a[0]+8)
  if cap-start<size:start=alloc(size+28);p32(a[0],start);p32(a[0]+8,start+size+28)
  u.mem_write(start,b''.join(synthetic_native_records));p32(a[0]+4,start+size);return 1
 start=i32(a[0]);p32(a[0]+4,start);return 0
# Simulated native UI window ABI; exercises runtime layout after docking resets.
ui_main,_=obj(80);ui_panel,_=obj(80);ui_radio1,_=obj(80);ui_radio2,_=obj(80);ui_tag,_=obj(80);ui_expanded,_=obj(80);ui_backing,_=obj(80)
stock_visible=True;stock_visibility_changes=[]
def stock_flag(t,a):
 global stock_visible
 stock_visible=bool(a[1]);stock_visibility_changes.append((clock,stock_visible));return 0
setmethod(ui_backing,67,lambda t,a:int(stock_visible),1)
setmethod(ui_backing,68,stock_flag,2)
ui_cover,_=obj(80);cover_visible=False;cover_changes=[]
def cover_flag(t,a):
 global cover_visible
 cover_visible=bool(a[1]);cover_changes.append((clock,cover_visible));return 0
setmethod(ui_cover,67,lambda t,a:int(cover_visible),1)
setmethod(ui_cover,68,cover_flag,2)
def forbidden_instance_setter(t,a):raise AssertionError('Visibility code called SetInstanceID instead of GetFlag')
setmethod(ui_cover,66,forbidden_instance_setter,1)
ui_manager,_=obj(64)
setmethod(ui_main,6,lambda t,a:ui_manager)
setmethod(ui_manager,42,lambda t,a:int(modal_pause()))
ui_areas={};ui_changes=[]
for w,rect in [(ui_panel,(461,253,1007,681)),(ui_radio1,(0,298,546,428)),(ui_radio2,(0,346,546,476)),(ui_expanded,(0,0,546,428)),(ui_backing,(0,0,546,428))]:
 area=alloc(16);u.mem_write(area,struct.pack('<4i',*rect));ui_areas[w]=area
 setmethod(w,48,lambda t,a:i32(0) if False else ui_areas[t])
 def setarea(t,a):
  value=bytes(u.mem_read(a[0],16));u.mem_write(ui_areas[t],value);ui_changes.append((t,struct.unpack('<4i',value)));return 0 if MODE=='ui-area-false' else 1
 setmethod(w,54,setarea,1)
ui_crime_button,_=obj(80);ui_crime_interface,_=obj(16);ui_legend,_=obj(80)
def crime_selected_now():
 if MODE=='ui-off':return False
 if MODE in ('ui-switch','ui-frame-switch'):return 6000<=clock<16000
 return True
def crime_qi(t,a):
 if a[0]!=0x8810:return 0
 p32(a[1],ui_crime_interface);return 1
setmethod(ui_crime_button,0,crime_qi,2)
setmethod(ui_crime_interface,10,lambda t,a:int(crime_selected_now()))
setmethod(ui_crime_interface,2,lambda t,a:1)
setmethod(ui_legend,67,lambda t,a:int(crime_selected_now()),1)
if MODE=='ui-conflict':u.mem_write(ui_areas[ui_radio1],struct.pack('<4i',0,300,546,430))
setmethod(ui_main,35,lambda t,a:ui_tag if a[0]==0xf5ee0170 else 0,1)
setmethod(ui_tag,34,lambda t,a:0,1)
setmethod(ui_tag,11,lambda t,a:ui_panel)
setmethod(ui_panel,34,lambda t,a:ui_radio2 if a[0]==0x8a2871b2 else 0,1)
setmethod(ui_panel,35,lambda t,a:{0x5003:ui_crime_button,0x8a2871c4:ui_legend,0xf5ee0170:ui_tag,0x8a2871b1:ui_radio1,0x8a2871b2:ui_radio2,0xaa32bcd4:ui_expanded}.get(a[0],0),1)
setmethod(ui_expanded,35,lambda t,a:{0x6a2871bc:ui_backing,0xf5ee0180:ui_cover}.get(a[0],0),1)
if MODE in ('ui-frame','ui-frame-switch'):
 ui_frame,_=obj(80);ui_frame_stock,_=obj(80);ui_frame_cover,_=obj(80)
 frame_visible=False;frame_stock_visible=True
 area=alloc(16);u.mem_write(area,struct.pack('<4i',108,33,504,321));ui_areas[ui_frame]=area
 setmethod(ui_frame,48,lambda t,a:ui_areas[t])
 def set_frame_area(t,a):
  r=struct.unpack('<4i',u.mem_read(a[0],16));u.mem_write(ui_areas[t],struct.pack('<4i',*r));ui_changes.append((t,r));return 1
 setmethod(ui_frame,54,set_frame_area,1)
 def frame_flag(t,a):
  global frame_visible,frame_stock_visible
  if t==ui_frame:raise AssertionError('Frame parent/title must remain visible')
  if t==ui_frame_cover:frame_visible=bool(a[1])
  else:frame_stock_visible=bool(a[1])
  return 1
 setmethod(ui_frame_cover,67,lambda t,a:int(frame_visible),1)
 setmethod(ui_frame_stock,67,lambda t,a:int(frame_stock_visible),1)
 setmethod(ui_frame_cover,68,frame_flag,2);setmethod(ui_frame_stock,68,frame_flag,2)
 setmethod(ui_frame,35,lambda t,a:{0x6a2871bc:ui_frame_stock,0xf5ee0180:ui_frame_cover}.get(a[0],0),1)
 setmethod(ui_panel,35,lambda t,a:{0x5003:ui_crime_button,0x8a2871c4:ui_legend,0xf5ee0170:ui_tag,0x8a2871b1:ui_radio1,0x8a2871b2:ui_radio2,0xaa32bcd4:ui_expanded,0xf5ee0183:ui_frame}.get(a[0],0),1)
if MODE in ('ui-stock-compact','ui-stock-unknown','ui-compact-root'):
 stock_ui=(ROOT.parent/'analysis/ui/00000000-96a006b0-2bc9060f.bin').read_bytes()
 assert b'id=0x6a2871bc area=(1,0,517,428)' in stock_ui
 assert b'id=0x8a2871c3 area=(4,-1,550,427)' in stock_ui
 # Actual stock 2bc9060f dimensions; the compact background is narrower
 # than its parent, and the crime panel starts at (4,-1).
 ui_compact,_=obj(80);ui_compact_bg,_=obj(80);ui_crime_panel,_=obj(80)
 for w,rect in [(ui_compact,(0,0,546,428)),(ui_compact_bg,(1,0,516 if MODE=='ui-stock-unknown' else 517,428)),(ui_crime_panel,(4,-1,550,427))]:
  area=alloc(16);u.mem_write(area,struct.pack('<4i',*rect));ui_areas[w]=area
  setmethod(w,48,lambda t,a:ui_areas[t])
  def setextra(t,a):
   r=struct.unpack('<4i',u.mem_read(a[0],16));u.mem_write(ui_areas[t],struct.pack('<4i',*r));ui_changes.append((t,r));return 1
  setmethod(w,54,setextra,1)
 if MODE=='ui-compact-root':u.mem_write(ui_areas[ui_panel],struct.pack('<4i',461,253,977,681))
 setmethod(ui_compact,35,lambda t,a:ui_compact_bg if a[0]==0x6a2871bc else 0,1)
 setmethod(ui_crime_panel,35,lambda t,a:0,1)
 setmethod(ui_panel,35,lambda t,a:{0x5003:ui_crime_button,0x8a2871c4:ui_legend,0xf5ee0170:ui_tag,0x8a2871b1:ui_radio1,0x8a2871b2:ui_radio2,0xaa32bcd4:ui_expanded,0xaa32bcd5:ui_compact,0x8a2871c3:ui_crime_panel}.get(a[0],0),1)

setmethod(app,26,lambda t,a:ui_main)
setmethod(crimes,11,native_incidents,1,fixed=0x6a1960)
for i in range(64):
 if i!=11:p32(crv+4*i,stub(lambda t,a:0))

if MODE=='unsupported':u.mem_write(0x505370,b'\x90')
if MODE=='conflict':p32(crv+44,stub(lambda t,a:0,1))

exports={x.name.decode():base+x.address for x in dll.DIRECTORY_ENTRY_EXPORT.symbols}
assert call(base+dll.OPTIONAL_HEADER.AddressOfEntryPoint,args=(base,1,0))==1
# The C export is cdecl, so it has no stack arguments.
assert set(exports)=={'GZDllGetGZCOMDirector'}, exports
director=call(exports['GZDllGetGZCOMDirector']);assert director
assert not logs if os.environ.get('SC4_TEST_QUIET')=='1' else 'game requested plugin director' in ''.join(logs)
com,comv=obj();setmethod(com,4,lambda t,a:framework)
# InitializeCOM's library-path reference is unused.
assert (method(director,3,com,0)&255)==1
assert (method(director,4,com)&255)==1 and hook_target
assert (method(hook_target,5)&255)==1
if MODE in ('missing-message','missing-allocator'):
 assert not tick_target and not notices
 assert ('Disabled: message service unavailable.' if MODE=='missing-message' else 'Disabled: allocator service unavailable.') in ''.join(logs)
 print('PASS: missing required service disables integration before subscriptions/ticks');sys.exit(0)
if MODE=='unsupported':
 assert not tick_target and 'Disabled: executable' in ''.join(logs)
 print('PASS: unsupported executable disables integration without city/game changes');sys.exit(0)
assert tick_target and set(notices)=={0xea8ae29a,0x26d31ec2,0x0a159d95,0x88ea4dff},(tick_target,notices,logs)
message,messv=obj();kind=0xea8ae29a;setmethod(message,4,lambda t,a:kind)
assert (method(message_target,3,message)&255)==1
if MODE=='crime-empty-filter':
 assert i32(crimes)==crv and 'Speeding native lot filter is empty' in ''.join(logs)
 method(hook_target,6);print('PASS: zero native filter mask disables with explicit DAT replacement message');sys.exit(0)
if MODE in ('native-create-hard-cap','native-create-soft-cap','native-create-at-251'):
 assert call(0x510690,manager,[0x4002,0,exemplar+16,0,0])==0,'Original capped request should be rejected'
 assert not actors
 limits_before=bytes(u.mem_read(manager+0x3c,8))
if MODE=='conflict':
 assert i32(crimes)==crv and not actors and 'another mod already hooks' in ''.join(logs)
 method(hook_target,6);print('PASS: conflicting incident hook preserved; plugin disabled for city');sys.exit(0)
assert i32(crimes)!=crv,'map hook not installed: '+''.join(logs)
native_message,native_message_v=obj();native_id=112
setmethod(native_message,4,lambda t,a:0x0a159d95)
setmethod(native_message,9,lambda t,a:native_id)
setmethod(native_message,32,lambda t,a:test_lot)
def lot_qi(t,a):
 assert a[0]==0xe818fced;p32(a[1],test_lot);return 1
setmethod(test_lot,0,lot_qi,2);refs(test_lot)
u.mem_write(test_lot+0x20,bytes([6,6,6,6]));p32(ltv+15*4,0x6bf560)
native_sent=False
reclaim_baseline=native_reclaim_calls
if MODE.startswith('native-create-') and MODE not in ('native-create-success','native-create-hard-cap','native-create-soft-cap','native-create-at-251'):
 # Confirm the original uninstrumented core also rejects this same setup.
 assert call(0x510690,manager,[0x4002,0,exemplar+16,0,0])==0
 assert not actors

# The stock patrol table must still enable its effect for unrelated vehicles.
probe,probev=obj(220);actors[probe]={'traffic_effect':False}
p32(probe,0xa9a0c0)
probe_state=actors.pop(probe)
# At this point the real table has not been replaced with test callbacks yet.
# Verify the stock callback separately once a scene patrol has been created.
def finish_crime_selection():
 global kind
 previous=kind;kind=0x88ea4dff;method(message_target,3,message);kind=previous
stock_tested=False
if MODE in ('monthly-none','monthly-other') or MONTHLY_EVENTS:
 def monthly_tick():
  global clock
  clock+=250;method(tick_target,10,0)
 for _ in range(500):monthly_tick()
 assert not actors,'Elapsed time must not start any scene'
 assert not camera_pans
 if MODE=='monthly-other':
  native_id=4;method(message_target,3,native_message);finish_crime_selection()
  for _ in range(20):monthly_tick()
  assert not actors,'Other crime notification started Speeding'
 if MONTHLY_EVENTS:
  stock_a=struct.pack('<3IB3x3I',6,6,3,1,0x7ab50e44,0x1abe787d,123)
  speeding_native=struct.pack('<3IB3x3I',6,6,112,0,0x7ab50e44,0x1abe787d,0xf5ee0070)
  stock_b=struct.pack('<3IB3x3I',7,6,4,1,0x7ab50e44,0x1abe787d,456)
  synthetic_native_records=[stock_a,speeding_native,stock_b]
  native_id=112;method(message_target,3,native_message);finish_crime_selection();monthly_tick()
  assert len(actors)==2 and all(v['created_at']==clock for v in actors.values())
  sample_vector=alloc(12);method(crimes,11,sample_vector);data=i32(sample_vector)
  assert (i32(sample_vector+4)-data)//28==3
  assert bytes(u.mem_read(data,56))==stock_a+stock_b,'Other native icons changed'
  assert i32(data+56+8)==112,'Active Speeding marker missing' 
  # A second selected incident starts while the old visual remains active.
  first_actors=set(actors)
  method(message_target,3,native_message)
  monthly_tick();assert set(actors)==first_actors,'Queued scene overlapped active animation'
  finish_crime_selection()
  method(crimes,11,sample_vector);data=i32(sample_vector)
  assert i32(sample_vector+4)-data==56,'Previous batch marker survived next selection'
  assert all(not actors[a]['removed'] for a in first_actors),'New batch cancelled active animation'
  old_positions={a:actors[a]['pos'] for a in first_actors}
  monthly_tick()
  assert len(actors)==4,'Re-selected Speeding waited for the old sequence'
  new_cars=set(actors)-first_actors
  assert all(not actors[a]['removed'] for a in first_actors|new_cars)
  assert all(actors[a]['pos']!=old_positions[a] for a in first_actors),'Old cars stopped advancing'
  assert all(actors[a]['created_at']==clock for a in new_cars),'New scene was delayed'
  method(crimes,11,sample_vector);data=i32(sample_vector)
  assert i32(sample_vector+4)-data==84,'Old marker reappeared during overlapping animation'
  if MODE=='monthly-overlap-pause':
   snapshot={a:(v['pos'],v.get('opacity'),v['removed']) for a,v in actors.items()}
   overlap_paused=True
   for _ in range(8):monthly_tick()
   overlap_paused=False;monthly_tick()
   assert snapshot=={a:(v['pos'],v.get('opacity'),v['removed']) for a,v in actors.items()},'Modal pause advanced an overlapping scene'
   monthly_tick()
   assert all(actors[a]['pos']!=snapshot[a][0] for a in first_actors|new_cars),'One scene failed to resume'
  if MODE in ('monthly-overlap-shutdown','monthly-overlap-hotkey'):
   if MODE=='monthly-overlap-shutdown':
    kind=0x26d31ec2;method(message_target,3,message)
    assert i32(crimes)==crv,'Shared hook was not restored'
   else:
    restart_pressed=True;monthly_tick();restart_pressed=False
    assert len(actors)==6 and len(camera_pans)==1,'Hotkey did not replace overlapping scenes'
   assert all(actors[a]['removed'] for a in first_actors|new_cars)
   assert all(not actors[a].get('lights') for a in first_actors|new_cars)
   assert len(removed)==len(set(removed)),'Double removal during overlap cleanup'
   method(hook_target,6)
   assert all(v['removed'] for v in actors.values())
   print('PASS: overlapping scenes clean up independently on '+MODE)
   sys.exit(0)
  for _ in range(200):monthly_tick()
  assert len(actors)==6 and all(v['removed'] for v in actors.values()),(actors,logs)
  assert ''.join(logs).count('Traffic stop completed')==2
  method(crimes,11,sample_vector);data=i32(sample_vector)
  assert i32(sample_vector+4)-data==84,'Finished sequence did not retain marker'
  assert bytes(u.mem_read(data,56))==stock_a+stock_b,'Other icons changed'
  # A later batch with no Speeding clears the retained marker, without actors.
  native_id=4;method(message_target,3,native_message);finish_crime_selection()
  method(crimes,11,sample_vector);data=i32(sample_vector)
  assert i32(sample_vector+4)-data==56 and bytes(u.mem_read(data,56))==stock_a+stock_b
  # Empty batches must retire it too (no per-incident event).
  native_id=112;method(message_target,3,native_message);finish_crime_selection()
  for _ in range(120):monthly_tick()
  method(crimes,11,sample_vector);data=i32(sample_vector)
  assert i32(sample_vector+4)-data==84
  finish_crime_selection()
  method(crimes,11,sample_vector);data=i32(sample_vector)
  assert i32(sample_vector+4)-data==56,'Empty batch failed to clear retained marker'  
 method(hook_target,6)
 assert struct.unpack('<f',u.mem_read(category+0x38,4))[0]==4
 print('PASS: markers persist after actor removal; next ordinary/empty batch clears them; Speeding re-selection immediately starts a second independent scene while the first advances; other icons unchanged')
 sys.exit(0)
if MODE=='hotkey-restart':
 def tick_restart(pressed):
  global clock,restart_pressed
  restart_pressed=pressed;clock+=250;method(tick_target,10,0)
 def alive_scene():return {a for a,v in actors.items() if not v['removed']}
 tick_restart(True);first=alive_scene();assert len(first)==2
 tick_restart(True);assert alive_scene()==first,'Held shortcut restarted repeatedly'
 tick_restart(False)
 tick_restart(True);second=alive_scene();assert len(second)==2 and not first&second
 assert all(actors[a]['removed'] for a in first)
 assert all(not actors[a].get('lights') for a in first)
 assert all(actors[a]['created_at']==clock for a in second),'Restart was delayed to next tick'
 tick_restart(False)
 for _ in range(160):
  tick_restart(False)
  if any(v['group']==0x410d and not v['removed'] for v in actors.values()):break
 old=alive_scene();assert len(old)==3,'Did not reach officer phase'
 tick_restart(True);third=alive_scene();assert len(third)==2 and not old&third
 assert all(actors[a]['removed'] for a in old),'Restart leaked previous officer or vehicles'
 assert all(not actors[a].get('lights') for a in old)
 assert all(actors[a]['created_at']==clock for a in third)
 v=alloc(12);method(crimes,11,v)
 assert (i32(v+4)-i32(v))//28==1,'Old incident remained after restart'
 assert len(camera_pans)==3,'Camera did not focus each new sequence'
 for _ in range(4):tick_restart(True)
 assert alive_scene()==third,'Holding shortcut retriggered scene'
 kind=0x26d31ec2;method(message_target,3,message);method(hook_target,6)
 assert not alive_scene() and len(removed)==len(set(removed)),'Cleanup leaked or removed actors twice'
 assert ''.join(logs).count('Hotkey restart:')==2
 print('PASS: same-tick hotkey restart during vehicle fade and officer phase; all old actors/lights/marker cleaned; held-key debounce; camera follows new scene')
 sys.exit(0)
vec=alloc(12);seen_marker=False;stop_drift_injected=False;verified_stop=False
curve_start=None;curve_samples=[];fade_samples=[];drive_positions=[]
pose_history={};outward_start={};vehicle_fades=[];officer_samples=[];officer_facing_samples=[];officer_turn_positions=[]
modal_frames=0;last_modal=False;scene_started_at=None;scene_finished_at=None
speed_mode=MODE.startswith('speed-')
for frame in range(600 if MODE.startswith('steering-tail') else 220):
 clock+=(100 if MODE.startswith('steering-tail') else 750 if MODE=='delayed-ticks' and frame%8==7 else 250)
 if MODE=='idle-clock':
  method(tick_target,11,0) # Idle immediately before active update must not starve dt.
 for state in actors.values():
  if state.get('auto_motion') and not state['removed'] and not (MODE=='paused' and clock<11000):
   x,y,z=state['pos'];dx,dy,dz=state['heading'];state['pos']=(x+dx*.5,y,z+dz*.5)
 if MODE=='drive-correction' and len(actors)==2 and not removed:
  for actor,state in actors.items():
   if state.get('group')==0x4228:state['pos']=(100,0,103)
 if MODE=='stop-alignment' and 'Moving fade-in started' in ''.join(logs) and not stop_drift_injected:
  for actor,state in actors.items():
   if state.get('group')==0x4228:
    offender=next(v for v in actors.values() if v.get('group')==0x4002);state['pos']=(104,0,offender['pos'][2]-16)
  stop_drift_injected=True
 if MODE=='officer-idle-drift' and 'Officer walking to driver' not in ''.join(logs):
  for state in actors.values():
   if state.get('group')==0x410d and not state['removed']:
    x,y,z=state['pos'];state['pos']=(x+4,y,z)
 was_walking='Officer walking to driver' in ''.join(logs) and 'Officer reached door' not in ''.join(logs)
 before_officer=next((v['pos'] for v in actors.values() if v.get('group')==0x410d and not v['removed']),None)
 frozen={k:(v['pos'],v.get('heading'),v.get('opacity'),v['removed']) for k,v in actors.items()}
 log_count=len(logs)
 if not native_sent and clock>=11000 and not actors and MODE not in ('monthly-none','monthly-other'):
  method(message_target,3,native_message);finish_crime_selection();native_sent=True
 method(tick_target,10,0)
 actual_weight=struct.unpack('<f',u.mem_read(category+0x38,4))[0]
 available=(clock>=7000 if MODE=='ordinance-becomes-available' else clock<13000 if MODE=='ordinance-availability-lost' else ordinance_available) and MODE!='ordinance-missing'
 assert actual_weight==(4 if available and not ordinance_on() else 0),(MODE,clock,actual_weight)
 if MODE=='ui-switch':
  expected=(461,233,1007,681) if crime_selected_now() else (461,253,1007,681)
  assert struct.unpack('<4i',u.mem_read(ui_areas[ui_panel],16))==expected,'Panel shifted outside Crime selection'
  assert cover_visible==crime_selected_now(),'Shared backing visible outside Crime'
  assert stock_visible!=cover_visible,'Stock and expanded frame are both visible or both hidden'
 if MODE=='ui-mid-conflict' and frame==30:
  u.mem_write(ui_areas[ui_radio1],struct.pack('<4i',0,321,546,451))
 if scene_started_at is None and 'Moving fade-in started' in ''.join(logs):
  scene_started_at=clock
  police=next(v for v in actors.values() if v['group']==0x4228)
  hx,_,hz=last_road_heading
  axis=0 if abs(hx)>.5 else 2;direction=hx if axis==0 else hz
  # The first tick has already moved by 0.25*6 metres.
  initial_rear=police['pos'][axis]-direction*(1+(.6 if MODE.startswith('steering-tail') else 1.5)*speed_scale())
  assert abs(initial_rear/16-round(initial_rear/16))<.0001,(MODE,initial_rear)

 if scene_finished_at is None and 'Traffic stop completed' in ''.join(logs):scene_finished_at=clock
 if MODE=='quit-menu':
  if modal_pause() or last_modal:
   assert frozen=={k:(v['pos'],v.get('heading'),v.get('opacity'),v['removed']) for k,v in actors.items()},'Animation advanced in menu or caught up on resume'
   assert len(logs)==log_count,'Scene stage advanced while blocked'
   modal_frames+=int(modal_pause());last_modal=modal_pause();continue
  last_modal=False
 if speed_mode and scene_finished_at:break
 if MODE=='hidden-pauses'  and hidden_pause() and was_walking and before_officer:
  after_officer=next(v['pos'] for v in actors.values() if v.get('group')==0x410d and not v['removed'])
  assert sum((a-b)**2 for a,b in zip(before_officer,after_officer))>.0001,'Officer froze during a hidden pause'
 for state in actors.values():
  if state.get('group') in (0x4002,0x4228) and not state['removed']:
   parked='Staggered shoulder stop complete' in ''.join(logs)
   assert bool(state.get('flags',8)&8)!=parked,'Collision flag switched at wrong scene phase'
 if MODE in ('terrain-missing','terrain-invalid') and 'terrain height unavailable' in ''.join(logs):
  assert len(removed)==len(actors) and not counts.get('waveOutOpen')
  print('PASS: unavailable/invalid terrain aborts before showing or moving the scene');sys.exit(0)
 if len(actors)==3:
  offender=next(v for v in actors.values() if v['group']==0x4002)
  patrol=next(v for v in actors.values() if v['group']==0x4228)
  hx,hy,hz=last_road_heading
  rx,rz=(-hz,hx) if not LHD else (hz,-hx)
  dx,dz=offender['pos'][0]-patrol['pos'][0],offender['pos'][2]-patrol['pos'][2]
  assert abs(dx*hz-dz*hx)<.001
  shift=1.5 if MODE=='shoulder-custom' else 2
  assert abs((offender['pos'][0]-100)*rx+(offender['pos'][2]-100)*rz-shift)<.001,'Shoulder shift wrong or applied more than once'
  assert abs(dx*hx+dz*hz-8)<.001
  assert abs(offender['heading'][0]*patrol['heading'][2]-offender['heading'][2]*patrol['heading'][0])<.001
  verified_stop=True
 active=[v for v in actors.values() if v.get('group')==0x4002 and not v['removed']]
 if active:
  lead=active[0]
  if 'Curved pull-over started' not in ''.join(logs):
   fade_samples.append(lead.get('opacity',0));drive_positions.append(lead['pos'])
  else:
   if curve_start is None:curve_start=(clock,lead['pos'])
   if not verified_stop:curve_samples.append((clock,lead['pos'],lead['heading']))
 if active:
  hx,hy,hz=last_road_heading;rx,rz=(-hz,hx) if not LHD else (hz,-hx)
  for aid,car in actors.items():
   if car.get('group') not in (0x4002,0x4228) or car['removed']:continue
   pose_history.setdefault(aid,[]).append((clock,car['pos'],car['heading'],car.get('opacity',0)))
   side_offset=(car['pos'][0]-100)*rx+(car['pos'][2]-100)*rz
   if side_offset>.001 and car['group'] not in outward_start:outward_start[car['group']]=clock
  if len(actors)==3:
   officer=next(v for v in actors.values() if v['group']==0x410d)
   if not officer['removed']:
    lead=active[0];near=-((officer['pos'][0]-lead['pos'][0])*rx+(officer['pos'][2]-lead['pos'][2])*rz)
    expected=(1.5 if MODE=='shoulder-custom' else 2)*.5+.45
    assert abs(near-expected)<.001,(near,expected)
    assert abs(officer['pos'][1]-road_height(*[officer['pos'][i] for i in (0,2)])-.02)<.001
    officer_samples.append(officer['pos'])
    officer_facing_samples.append((officer['pos'],officer['heading'],lead['pos']))
    if 'Officer reached door; turning' in ''.join(logs):officer_turn_positions.append(officer['pos'])
   if officer['removed']:vehicle_fades.append(active[0].get('opacity',0))
 if MODE in ('native-create-inactive','native-create-factory','native-create-boost-factory') and 'Scene deferred: no suitable road/lot candidate found.' in ''.join(logs):
  assert not actors
  assert 'Native creation detail:' not in ''.join(logs)
  method(hook_target,6);print('PASS: activation/factory rejection retained; detailed diagnostics removed');sys.exit(0)
 if MODE in ('intersection-only','missing-road','road-end','unflagged-junction','mixed-junction','inside-curve','bend-ahead','crossing-ahead','axis-change','overflow-intersection','overflow-curve') and 'Scene deferred: no suitable road/lot candidate found.' in ''.join(logs):
  assert all(state['removed'] for state in actors.values()) and road_candidates==32
  assert not controls and not counts.get('waveOutOpen')
  if MODE=='intersection-only':assert not actors
  print('PASS: junction-only/missing/ending road rejected without showing a scene');sys.exit(0)
 if MODE=='lights-unavailable' and actors:
  assert len(actors)==2 and len(removed)==2 and not counts.get('waveOutOpen')
  assert 'flashing-light effect unavailable' in ''.join(logs)
  print('PASS: unavailable light effect cancels scene without opening audio');sys.exit(0)
 if MODE=='police-conflict' and actors:
  assert len(actors)==2 and len(removed)==2 and not controls
  assert 'police interface differs' in ''.join(logs)
  assert not counts.get('waveOutOpen')
  kind=0x26d31ec2;method(message_target,3,message);method(hook_target,6)
  print('PASS: differing police interface cancels scene without replacing its table or starting siren');sys.exit(0)
 for actor,state in list(actors.items()):
  if state.get('group')==0x4228 and not state['removed']:
   method(actor,194,1);assert not state['traffic_effect']
   assert state.get('lights'),'Visual lights should remain active independently of emergency traffic switch'
   assert i32(actor)!=0xa9a0c0
   for slot in range(201):
    if slot!=194:assert i32(i32(actor)+slot*4)==i32(0xa9a0c0+slot*4)
   if not stock_tested:
    actors[probe]=probe_state
    method(probe,194,1);assert actors[probe]['traffic_effect'] and i32(probe)==0xa9a0c0
    stock_tested=True
    del actors[probe]
 if MODE=='cancel-fade' and any(0<a<1 for a in vehicle_fades):
  kind=0x26d31ec2;method(message_target,3,message)
  assert i32(crimes)==crv and len(removed)==3
  assert all(not v.get('lights') for v in actors.values())
  assert len(removed)==len(set(removed))
  method(hook_target,6)
  print('PASS: city shutdown during vehicle fade releases each actor once and restores hook/lights');sys.exit(0)
 if MODE=='cancel' and 'Curved pull-over started' in ''.join(logs):
  kind=0x26d31ec2;method(message_target,3,message)
  assert i32(crimes)==crv and len(removed)==2 and not counts.get('waveOutOpen')
  assert all(not v.get('lights') for v in actors.values())
  assert all(i32(a)==0xa9a0c0 for a,v in actors.items() if v.get('group')==0x4228)
  method(hook_target,6);print('PASS: mid-stop city shutdown removes owned actors, disables flashing lights and restores native hook');sys.exit(0)
 if len(actors)>=2 and len(removed)<3:
  method(crimes,11,vec)
  if i32(vec+4)>i32(vec):
   assert i32(i32(vec)+8)==112
   assert struct.unpack('<III',u.mem_read(i32(vec)+16,12))==(0x7ab50e44,0x1abe787d,0xf5ee0070),'Wrong FSH gauge key'
   seen_marker=True
if MODE=='ordinance-availability-lost':
 assert len(actors)==2 and len(removed)==2 and not any(v.get('lights') for v in actors.values())
 method(hook_target,6);print('PASS: losing menu availability cancels active sequence and cleans lights/actors');sys.exit(0)
if MODE in ('ordinance-unavailable','ordinance-delayed','ordinance-missing') or MODE.startswith('lot-') and MODE not in ('lot-cs','lot-right-only'):
 assert 'Moving fade-in started' not in ''.join(logs)
 assert all(v['removed'] for v in actors.values()) and not camera_pans
 if MODE.startswith('ordinance-'):assert not actors and not ordinance_changes
 else:assert len(actors)==64 and len(removed)==64
 method(hook_target,6)
 print('PASS: unavailable/missing ordinance or non-adjacent/non-R$/CS$ lot blocks scenes without visible actors/marker')
 sys.exit(0)
if MODE in ('ordinance-on','camera-ordinance-active','ordinance-enact'):
 assert ordinance_queries and ordinance_changes==[]
 if MODE=='ordinance-enact':
  assert len(actors)==2 and len(removed)==2 and not any(v.get('lights') for v in actors.values())
 else:assert not actors and not removed
 assert 'Speed Traps active: speeding scenes suppressed.' in ''.join(logs)
 assert not camera_pans
 method(hook_target,6)
 print('PASS: Speed Traps blocks automatic/hotkey scenes, or cancels active cars/lights cleanly; native checkbox is only read.')
 sys.exit(0)
assert len(actors)>=3 and len(removed)==len(actors),(actors,removed,''.join(logs))
assert controls==[], 'Curved path must not create native broad pull-over controllers'
for actor,state in actors.items():
 if state['group']==0x4228:
  assert not state['traffic_effect']
  assert state.get('traffic_released_at') and not state['flags']&8,'Parked car remains a traffic obstacle'
  assert state.get('followers_refreshed_at')==state['traffic_released_at'],'Cached followers not refreshed at parking'
  assert i32(actor)==0xa9a0c0,'Private police table not restored on cleanup' 
assert seen_marker and verified_stop
if MODE in ('ordinance-unavailable','ordinance-delayed'):
 assert not ordinance_changes and not ordinance_available,'DLL bypassed host eligibility conditions'
 assert 'host controls eligibility requirements' in ''.join(logs)
elif MODE=='ordinance-missing':
 assert 'Speed Traps NOT REGISTERED' in ''.join(logs) and not ordinance_changes
else:assert not ordinance_changes,'Already available ordinance should not be changed' 
if MODE=='quit-menu':assert modal_frames>=20
if speed_mode:print('TIMING:',MODE,'scene duration ms',scene_finished_at-scene_started_at)
if MODE=='hidden-pauses':assert 'continuing active scene through a hidden' in ''.join(logs)
if MODE=='delayed-ticks':assert 'game update gap exceeded 500 ms' in ''.join(logs)
if MODE in ('ui-frame','ui-frame-switch'):
 expected=(108,33,504,341) if MODE=='ui-frame' else (108,33,504,321)
 assert struct.unpack('<4i',u.mem_read(ui_areas[ui_frame],16))==expected
 assert frame_visible==(MODE=='ui-frame') and frame_stock_visible!=(MODE=='ui-frame')
 assert len(ui_changes)==(6 if MODE=='ui-frame' else 12),ui_changes
 print('PASS: Crime frame grows20px to match light panel, original frame hidden; normal frame/geometry restored on switch')
 method(hook_target,6);sys.exit(0)
if MODE in ('ui-stock-compact','ui-stock-unknown','ui-compact-root'):
 if MODE in ('ui-stock-compact','ui-compact-root'):
  assert struct.unpack('<4i',u.mem_read(ui_areas[ui_panel],16))==(461,233,977 if MODE=='ui-compact-root' else 1007,681)
  assert struct.unpack('<4i',u.mem_read(ui_areas[ui_compact_bg],16))==(1,0,517,448)
  assert struct.unpack('<4i',u.mem_read(ui_areas[ui_crime_panel],16))==(4,-1,550,447)
  assert len(ui_changes)==8 and cover_visible
 else:assert not ui_changes and not cover_visible
 print('PASS:',MODE,'original stock compact shape supported; unknown near-match rejected')
 method(hook_target,6);sys.exit(0)
if MODE in ('ui-off','ui-switch','ui-conflict','ui-mid-conflict'):
 if MODE in ('ui-off','ui-switch'):assert not cover_visible and stock_visible
 if MODE=='ui-mid-conflict':
  assert struct.unpack('<4i',u.mem_read(ui_areas[ui_radio1],16))==(0,321,546,451),'Overwrote another mod update'
  assert 'panel layout conflict detected' in ''.join(logs)
 else:
  assert struct.unpack('<4i',u.mem_read(ui_areas[ui_panel],16))==(461,253,1007,681)
  if MODE in ('ui-off','ui-conflict'):assert not ui_changes,'Modified unselected or conflicting layout'
  if MODE=='ui-switch':
   assert len(ui_changes)==10,(len(ui_changes),ui_changes)
   assert 'original panel layout restored' in ''.join(logs)
 print('PASS:',MODE,'Crime-only movement, restoration and cooperative layout checks')
 method(hook_target,6);sys.exit(0)
assert struct.unpack('<4i',u.mem_read(ui_areas[ui_panel],16))==(461,233,1007,681)
assert len(ui_changes)==5,'UI layout repeatedly drifted or did not apply'
assert cover_visible and not stock_visible,'Duplicate original backing still rendered during Crime'
for w in (ui_expanded,ui_backing):assert struct.unpack('<4i',u.mem_read(ui_areas[w],16))==(0,0,546,448)
for w in (ui_radio1,ui_radio2):assert struct.unpack('<4i',u.mem_read(ui_areas[w],16))==(0,318,546,448)
assert not any(x.dll.upper()==b'WINMM.DLL' for x in dll.DIRECTORY_ENTRY_IMPORT)
assert u.mem_read(camera+0x108,8)==b'ZOOMROTA'
if MODE.startswith('camera-'):
 if MODE=='camera-no-renderer':assert not camera_pans and 'renderer missing' in ''.join(logs)
 else:
  assert len(camera_pans)==(2 if MODE=='camera-refocus' else 1)
  offender=next(v for v in actors.values() if v['group']==0x4002)
  hx,hy,hz=last_road_heading
  cx,cz=offender['pos'][0]-hx*4,offender['pos'][2]-hz*4
  expected=(cx,terrain_height(cx,cz)+.05,cz)
  assert all(abs(a-b)<.01 for a,b in zip(camera_pans[-1],expected)),(camera_pans,expected)
else:assert not camera_pans,'Automatic scenes must not move camera'

assert any(0<a<1 for a in fade_samples) and max(fade_samples)==1,fade_samples
for i in range(1,len(drive_positions)):
 hx,hy,hz=last_road_heading
 assert (drive_positions[i][0]-drive_positions[i-1][0])*hx+(drive_positions[i][2]-drive_positions[i-1][2])*hz>0,'Stationary frame during fade/drive'

hx,hy,hz=last_road_heading
assert (drive_positions[-1][0]-drive_positions[0][0])*hx+(drive_positions[-1][2]-drive_positions[0][2])*hz>0,'Cars must drive during fade-in'
assert curve_start and len(curve_samples)>=(3 if speed_mode else 10)
start_pos=curve_start[1];rx,rz=(-hz,hx) if not LHD else (hz,-hx)
progress=[rx*(sample[1][0]-start_pos[0])+rz*(sample[1][2]-start_pos[2]) for sample in curve_samples]
assert all(progress[i+1]>=progress[i]-1e-5 for i in range(len(progress)-1)),progress
assert (curve_samples[-1][1][0]-start_pos[0])*hx+(curve_samples[-1][1][2]-start_pos[2])*hz>0,'Curve must include forward movement'
assert any(rx*sample[2][0]+rz*sample[2][2]>.01 for sample in curve_samples),'Car must turn toward shoulder'
assert 'Staggered shoulder stop complete' in ''.join(logs)
assert (0.1 if speed_mode else .5)<=(outward_start[0x4228]-outward_start[0x4002])*.001<=1.0,outward_start
assert vehicle_fades and any(0<a<1 for a in vehicle_fades),vehicle_fades
assert all(v.get('opacity')==0 for v in actors.values() if v.get('group') in (0x4002,0x4228))
assert officer_samples and officer_turn_positions

for p0,p1 in zip(officer_samples,officer_samples[1:]):
 assert ((p1[0]-p0[0])**2+(p1[2]-p0[2])**2)**.5<=(1.0501 if MODE=='delayed-ticks' or speed_mode else .3501),'Officer teleported during fade/walk'
last_pos,last_face,last_car=officer_facing_samples[-1]
fx,fz=last_car[0]-last_pos[0],last_car[2]-last_pos[2];norm=(fx*fx+fz*fz)**.5
assert (last_face[0]*fx+last_face[2]*fz)/norm>.999,'Officer must face parked car at the door'
assert max(abs(a-b) for p in officer_turn_positions for a,b in zip(p,officer_turn_positions[0]))<.0001,'Officer should remain at the door while turning'
# A yaw change must always accompany forward motion; bank/pitch changes on
# a slope are checked separately through the full rotation matrix above.
import math
for history in pose_history.values():
 for prev,nxt in zip(history,history[1:]):
  p0,p1=prev[1],nxt[1];f0,f1=prev[2],nxt[2]
  turn=abs(math.atan2(f1[0],f1[2])-math.atan2(f0[0],f0[2]))
  if turn>.001:
   assert (p1[0]-p0[0])*hx+(p1[2]-p0[2])*hz>1e-5,(prev,nxt)


if MODE.startswith('steering-tail'):
 for history in pose_history.values():
  for prev,nxt in zip(history,history[1:]):
   yaw_change=abs(math.atan2(nxt[2][0],nxt[2][2])-math.atan2(prev[2][0],prev[2][2]))
   assert yaw_change<.3,(MODE,prev,nxt)
 print('PASS: small-tick east/west final braking has no yaw snap')
if MODE in ('road-slope','road-crest','road-pieces','road-raised-surface'):
 for car in actors.values():
  if car.get('group') not in (0x4002,0x4228):continue
  samples=car['body_samples'];pitches=[math.asin(max(-1,min(1,m[5]))) for p,m in samples]
  assert max(abs(p) for p in pitches)>.01,'Road pitch ignored'
  if MODE in ('road-crest','road-pieces'):assert max(pitches)-min(pitches)>.03,'Pitch did not follow changing road pieces'
  assert all(abs(b-a)<.2 for a,b in zip(pitches,pitches[1:])),'Pitch snapped across road piece'
 print('PASS: both cars pitch with road surface independently of underlying flat terrain')
if MODE=='intersection-retry':assert road_candidates>=2
assert not counts.get('waveOutOpen') and not counts.get('waveOutClose'),counts
assert all(not v.get('lights') for v in actors.values()),'Flashing effect leaked after cleanup'
assert 'Traffic stop completed' in ''.join(logs),logs
kind=0x26d31ec2;method(message_target,3,message);assert i32(crimes)==crv
method(hook_target,6) # PreAppShutdown
if MODE in ('native-create-hard-cap','native-create-soft-cap','native-create-at-251'):
 assert bytes(u.mem_read(manager+0x3c,8))==limits_before,'Shared population maxima changed'
 assert native_reclaim_calls==reclaim_baseline,'Owned creation reclaimed unrelated traffic'
 assert len([v for v in actors.values() if v['group'] in (0x4002,0x4228)])==2
 assert call(0x510690,manager,[0x4002,0,exemplar+16,0,0])==0,'Original traffic creation must remain capped after the scene'
 print('PASS: original capped call rejected; owned speeder and police created, scene completed; maxima untouched and no native reclaim calls')
assert all(k not in ''.join(logs) for k in ['Spawn search #','Native creation detail:','First rejection','Search attempts:','Failure native'])
print('PASS: x86 DLL entry/export, MSVC COM callbacks, lifecycle subscription, moving fade, silent lights, camera pan, curve, marker and cleanup')
print('Simulated Win32 and game interfaces only; actual SimCity 4 behavior NOT tested.')
print(''.join(logs))
