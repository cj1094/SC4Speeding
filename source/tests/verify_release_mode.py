"""Verify quiet release behavior using the compiled x86 DLL and mocked game."""
import os,sys,io,contextlib
from pathlib import Path
os.environ['SC4_TEST_QUIET']='1'
source=Path(__file__).with_name('emulate_dll.py');sys.argv=[str(source),'hotkey-restart']
d={'__file__':str(source)}
with contextlib.redirect_stdout(io.StringIO()):exec(compile(source.read_text().split('stock_tested=False')[0],str(source),'exec'),d)
imports={i.name.decode() for desc in d['dll'].DIRECTORY_ENTRY_IMPORT for i in desc.imports}
assert not imports.intersection({'GetAsyncKeyState','CreateFileA','WriteFile','CloseHandle'}),imports
# Holding the old hotkey cannot start or restart a scene.
d['restart_pressed']=True
for _ in range(24):d['clock']+=250;d['method'](d['tick_target'],10,0)
assert not d['actors'] and not d['logs']
d['method'](d['message_target'],3,d['native_message']);d['finish_crime_selection']()
d['clock']+=250;d['method'](d['tick_target'],10,0)
assert len(d['actors'])==2
for _ in range(120):d['clock']+=250;d['method'](d['tick_target'],10,0)
assert len(d['actors'])==3 and all(v['removed'] for v in d['actors'].values())
assert not d['camera_pans'],'Debug hotkey moved camera in release'
assert not d['logs']
d['method'](d['hook_target'],6);assert not d['logs']
print('PASS: release has no logging/file-I/O or hotkey polling imports; held shortcut is ignored.')
print('PASS: native monthly selection still completes a full scene silently; shutdown stays silent.')
print('Emulated Win32/game services only; no live-game test.')
