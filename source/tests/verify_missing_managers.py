"""Execute DLL service-loss paths after successful binding; never launch SC4.
--expect-crash with SC4_TEST_DLL pointing to 0.56 verifies the old regression.
"""
from pathlib import Path
import sys,contextlib,io
from unicorn import UcError,UC_HOOK_MEM_READ_UNMAPPED
expect_crash='--expect-crash' in sys.argv
source=Path(__file__).with_name('emulate_dll.py')
setup=source.read_text().split('stock_tested=False')[0]
for scenario,slot,service in [('vehicle',43,'manager'),('pedestrian',44,'ped')]:
 sys.argv=[str(source),'success'];d={'__file__':str(source)}
 with contextlib.redirect_stdout(io.StringIO()):exec(compile(setup,str(source),'exec'),d)
 if scenario=='vehicle':d['setmethod'](d['city'],slot,lambda t,a:0)
 d['clock']=11000;d['method'](d['message_target'],3,d['native_message']);d['finish_crime_selection']()
 faults=[]
 d['u'].hook_add(UC_HOOK_MEM_READ_UNMAPPED,lambda mu,access,address,size,value,user:faults.append(address) or False)
 def tick():
  d['clock']+=250;d['method'](d['tick_target'],10,0)
 try:
  with contextlib.redirect_stdout(io.StringIO()):
   tick()
   if scenario=='pedestrian':d['setmethod'](d['city'],slot,lambda t,a:0)
   for _ in range(60):tick()
 except UcError:
  assert expect_crash and faults and faults[-1]==0,(scenario,faults)
  print('CONFIRMED old DLL null dereference:',scenario,'manager missing after bind');continue
 assert not expect_crash,'Old crash oracle unexpectedly survived'
 assert not faults
 assert all(v['removed'] for v in d['actors'].values()),'Owned actors leaked'
 assert all(not v.get('lights') for v in d['actors'].values()),'Lights leaked'
 assert len(d['removed'])==len(set(d['removed'])),'Actor removed twice'
 vec=d['alloc'](12);d['method'](d['crimes'],11,vec)
 assert d['i32'](vec)==d['i32'](vec+4),'Failed scene retained marker'
 assert len(d['actors'])==(0 if scenario=='vehicle' else 2)
 original_count=len(d['actors'])
 d['setmethod'](d['city'],slot,lambda t,a:d[service])
 d['method'](d['message_target'],3,d['native_message']);d['finish_crime_selection']();tick()
 assert len(d['actors'])==original_count+2,'Scene did not recover'
 for _ in range(120):tick()
 assert len(d['actors'])==original_count+3 and all(v['removed'] for v in d['actors'].values())
 assert len(d['removed'])==len(set(d['removed']))
 d['method'](d['hook_target'],6)
 assert d['i32'](d['crimes'])==d['crv'],'Hook not restored'
 print('PASS:',scenario,'manager loss safely cleans up; no marker/lights/double removal; next scene recovers')
print('Emulated DLL with mocked services only; no live-game test.')
