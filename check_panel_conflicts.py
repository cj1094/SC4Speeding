r"""Read-only DBPF overlap check for the three Data Views layout resources.
Run: py check_panel_conflicts.py --plugins "C:\path\to\Plugins"
Repeat --plugins for additional installation/user Plugin roots.
"""
import argparse, hashlib, pathlib, struct, sys
TARGETS={(0,0x96a006b0,x) for x in (0xea287193,0x2bc9060f,0x0b72f276)}
# Hash of the unmodified SC4Speeding UI DAT distributed with this release.
OWN_HASH='2ee3d67f780791715e9672afceeb5360865e1556be1adeb3cf12d5d98fd25a08'
def overlaps(path):
    with path.open('rb') as f:
        h=f.read(96)
        if len(h)<96 or h[:4]!=b'DBPF':return set()
        count,index,size=struct.unpack_from('<III',h,36)
        if not count:return set()
        if count>1000000 or size!=count*20:raise ValueError('unsupported DBPF index format')
        if index+size>path.stat().st_size:raise ValueError('index outside file')
        f.seek(index);data=f.read(size)
        return {key for i in range(count) if (key:=struct.unpack_from('<III',data,i*20)) in TARGETS}
def scan(roots):
    conflicts=[];errors=[];seen=set()
    for root in roots:
        root=pathlib.Path(root).expanduser()
        if not root.is_dir():errors.append((str(root),'folder not found'));continue
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in {'.dat','.sc4lot','.sc4desc','.sc4model'}:continue
            name=str(path.resolve()).lower()
            if name in seen:continue
            seen.add(name)
            try:
                keys=overlaps(path)
                if keys and hashlib.sha256(path.read_bytes()).hexdigest()!=OWN_HASH:conflicts.append((str(path),sorted(keys)))
            except (OSError,ValueError,struct.error) as e:errors.append((str(path),str(e)))
    return conflicts,errors
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plugins',action='append',required=True);args=p.parse_args()
    conflicts,errors=scan(args.plugins)
    for path,keys in conflicts:
        print('OVERLAP:',path)
        for t,g,i in keys:print(f'  {t:08x}-{g:08x}-{i:08x}')
    for path,error in errors:print('NOT CHECKED:',path,error)
    if conflicts:print('These files edit the same panel resources. A compatibility patch or choosing one UI replacement is needed.')
    elif not errors:print('No other files overriding these three panel resources were found in the supplied folders.')
    print('Runtime DLL hooks and changes outside these resources are not covered.')
    return 2 if conflicts else (1 if errors else 0)
if __name__=='__main__':sys.exit(main())
