"""Linux-only isolated shell tests. PATH has NO real mount/umount/setprop/ADB."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

builder = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/"tools/build_native_xpan_helper.py"
spec = importlib.util.spec_from_file_location("helper", builder)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
MOCK = r'''#!/usr/bin/python3
import hashlib,json,os,pathlib,sys
root=pathlib.Path(os.environ['MOCK_ROOT']).resolve();dbfile=root/'mock.json'
d=json.loads(dbfile.read_text());name=pathlib.Path(sys.argv[0]).name;a=sys.argv[1:]
def local(s):
 p=pathlib.Path(s).resolve();assert p.is_relative_to(root);return p
def save():
 d['events'].append([name]+a);dbfile.write_text(json.dumps(d))
if name=='cat':
 assert a==['/proc/sys/kernel/random/boot_id'];print('boot-test')
elif name=='awk':
 if a[0]=='-v':
  target=a[1].split('=',1)[1];assert a[-1]=='/proc/self/mountinfo'
  print(d['mounts'].get(target,{}).get('id',''))
 else:
  assert a==['{print $1}']
  for line in sys.stdin.read().splitlines():
   if line.split():print(line.split()[0])
elif name=='sha256sum':
 p=a[0]
 if p=='/product/app/OplusCamera/OplusCamera.apk':h=d['apk']
 elif p in d['mounts']:h=d['file_hashes'][d['mounts'][p]['source']]
 else:h=d['file_hashes'][p]
 print(h,p)
elif name=='getprop':print(d.get('sdk','36') if a[0]=='ro.build.version.sdk' else d['property'])
elif name=='setprop':
 assert a[0]=='debug.noah.hdr.xpan_native'
 if a[1]=='1' and d.get('set1fail'):save();sys.exit(1)
 d['property']=a[1];save()
elif name=='pidof':
 if d.get('camera_open'):print('123');sys.exit(0)
 sys.exit(1)
elif name=='am':
 assert a==['force-stop','com.oplus.camera'];save()
 if d.get('amfail'):sys.exit(1)
elif name=='ls':assert a[0]=='-Zd';print('u:object_r:vendor_configs_file:s0',a[1])
elif name in ['chown','chmod','chcon']:save()
elif name=='mount':
 assert a[0]=='--bind';src,target=a[1:]
 if d.get('mountfail')==target:save();sys.exit(1)
 assert target not in d['mounts'];d['next_id']+=1
 d['mounts'][target]={'id':str(d['next_id']),'source':src};save()
elif name=='umount':
 target=a[0]
 if target in d.get('umountfail',[]):save();sys.exit(1)
 assert target in d['mounts'];del d['mounts'][target];save()
elif name=='head':assert a[:2]==['-n','1'];print(local(a[2]).read_text().splitlines()[0])
elif name=='rm':
 assert a[0]=='-f'
 for v in a[1:]:local(v).unlink(missing_ok=True)
elif name=='mv':assert a[0]=='-f';local(a[1]).replace(local(a[2]))
else:raise AssertionError(name)
'''

with tempfile.TemporaryDirectory(prefix="hdr03-mock-") as directory:
    root=Path(directory);binpath=root/'bin';binpath.mkdir();(root/'payload').mkdir();(root/'targets').mkdir()
    for name in ['cat','awk','sha256sum','getprop','setprop','pidof','am','ls','chown','chmod','chcon','mount','umount','head','rm','mv']:
        f=binpath/name;f.write_text(MOCK);f.chmod(0o755)
    (root/'runtime.sh').write_text(helper.RUNTIME)
    targets=[];sources=[];hashes={};lines=[]
    for i in range(5):
        source=root/'payload'/str(i);target=root/'targets'/str(i)
        source.write_text('patched'+str(i));target.write_text('original'+str(i))
        for p in [source,target]:hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f'payload/{i} {target} {hashes[str(target)]} {hashes[str(source)]}')
        targets.append(str(target));sources.append(str(source))
    (root/'payload-manifest').write_text('\n'.join(lines)+'\n')
    env={**os.environ,'PATH':str(binpath),'MOCK_ROOT':str(root)}
    state=root/'mount-state';dbpath=root/'mock.json'

    def setup(active=False,**extra):
        state.unlink(missing_ok=True)
        d={'apk':helper.base.APK_HASH,'sdk':'36','property':'1' if active else '0',
           'events':[],'file_hashes':hashes,'mounts':{},'next_id':100}
        if active:
            for i,t in enumerate(targets):d['mounts'][t]={'id':str(i+11),'source':sources[i]}
            state.write_text(''.join(f'boot-test {i+11} {t}\n' for i,t in enumerate(targets)))
        d.update(extra);dbpath.write_text(json.dumps(d))

    def run(mode):
        r=subprocess.run(['/bin/sh',str(root/'runtime.sh'),mode],env=env,capture_output=True,text=True)
        return r,json.loads(dbpath.read_text())

    setup();r,d=run('apply');assert r.returncode==0,(r.stdout,r.stderr)
    assert len(d['mounts'])==5 and d['property']=='1'
    assert d['events'][-1]==['setprop','debug.noah.hdr.xpan_native','1']
    print('PASS apply: all5 mounts precede property1')
    r,d=run('remove');assert r.returncode==0 and not d['mounts'] and d['property']=='0'
    assert d['events'][-1]==['setprop','debug.noah.hdr.xpan_native','0']
    print('PASS remove: all5 unmounts precede property0')

    setup(set1fail=True);r,d=run('apply');assert r.returncode!=0 and not d['mounts'] and d['property']=='0'
    assert not state.exists()
    print('PASS property1 failure rolls all5 back before property0')

    setup(active=True,umountfail=[targets[2]]);r,d=run('remove')
    assert r.returncode!=0 and set(d['mounts'])=={targets[2]} and d['property']=='1'
    assert state.read_text()==f'boot-test 13 {targets[2]}\n'
    assert not any(e[0]=='setprop' for e in d['events'])
    d['umountfail']=[];d['events']=[];dbpath.write_text(json.dumps(d));r,d=run('remove')
    assert r.returncode==0 and not d['mounts'] and d['property']=='0'
    print('PASS partial rollback retains property1 and remaining state; retry succeeds')

    setup(active=True);d=json.loads(dbpath.read_text());d['mounts'][targets[1]]['id']='999';dbpath.write_text(json.dumps(d))
    r,d=run('remove');assert r.returncode!=0 and d['property']=='1'
    assert d['mounts'][targets[1]]['id']=='999'
    assert not any(e[0]=='umount' and e[1]==targets[1] for e in d['events'])
    print('PASS foreign mount refused; property stays enabled')

    setup(active=True,apk='changed-firmware',sdk='99');r,d=run('remove')
    assert r.returncode==0 and not d['mounts'] and d['property']=='0'
    print('PASS changed firmware does not block owned removal')

    setup(active=True);state.unlink();r,d=run('remove')
    assert r.returncode!=0 and len(d['mounts'])==5 and d['property']=='1'
    assert not any(e[0]=='umount' for e in d['events'])
    print('PASS untracked file mounts prevent property0 without foreign unmount')

    setup(camera_open=True);r,d=run('apply');assert r.returncode!=0 and not d['mounts'] and d['property']=='0'
    print('PASS active camera prevents apply')

print('ALL PASS. PATH contained mocks only; no real mounts, properties, ADB or device access.')
