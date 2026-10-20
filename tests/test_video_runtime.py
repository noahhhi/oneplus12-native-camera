"""Run the COMPLETE candidate shell runtime in disposable host sandboxes.

Android commands, mounts, PID lookup, and /proc mount lookup are mocked.
No Android device/ADB access. Only temporary host files are changed.
"""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location('candidate', Path(__file__).resolve().parents[1] / 'tools/build_native_video_helper.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
def digest(b): return hashlib.sha256(b).hexdigest()
def linux(p): return str(p.resolve())

MOCK = r'''
T="$MODDIR/test"
events="$T/events"
boot=$(cat "$T/boot")
BOOT=$boot
pidof() {
  [ "$1" = vendor.qti.camera.provider-service_64 ] || return 1
  [ "$(cat "$T/status")" = running ] || return 1
  cat "$T/pid"
}
readlink() { echo "$EXE"; }
getprop() {
  case "$1" in
    sys.boot_completed) echo 1 ;;
    ro.build.version.sdk) if [ "$CASE" = ota_remove ] || [ "$CASE" = ota_stock ]; then echo 37; else echo 36; fi ;;
    init.svc.*) cat "$T/status" ;;
  esac
}
dumpsys() {
  printf 'Active Camera Clients:\n'
  if [ "$CASE" = active ]; then printf '[foreign-client]\n'; else printf '[]\n'; fi
  printf 'Allowed user IDs: 0\n'
  if [ "$CASE" = huge ] || [ "$CASE" = huge_legacy ]; then
    head -c 2097152 /dev/zero | tr '\000' x
    printf '\n'
  fi
  [ "$CASE" != dumpsysfail ] || return 1
}
# Reproduce Android's external printf/exec argv size limit, not bash's builtin.
printf() { /usr/bin/printf "$@"; }
setprop() {
  echo "$1" >> "$events"
  case "$1" in
    ctl.stop) [ "$CASE" != stopfail ] || return 1; echo stopped > "$T/status" ;;
    ctl.start) [ "$CASE" != startfail ] || return 1; echo running > "$T/status" ;;
    ctl.restart) echo "$PPID" > "$T/pid"; echo running > "$T/status" ;;
    *) return 1 ;;
  esac
}
sleep() { :; }
sync() { :; }
am() { echo am >> "$events"; }
chown() { :; }
chmod() { :; }
chcon() { :; }
ls() { if [ "$1" = -Zd ]; then echo 'u:object_r:vendor_file:s0'; else command ls "$@"; fi; }
mid() {
  case "$1" in "$NODE") record="$T/node.mid" ;; "$CONFIG") record="$T/config.mid" ;; *) return 1 ;; esac
  if [ -f "$record" ] && [ "$1" = "$NODE" ]; then
    [ "$CASE" != midfail ] || return 1
    [ "$CASE" != midempty ] || return 0
  fi
  [ ! -f "$record" ] || cat "$record"
}
mount() {
  echo "mount:$3" >> "$events"
  [ -f "$INTENT" ] || { echo 'NO_DURABLE_INTENT' >> "$events"; return 1; }
  command cp "$2" "$3" || return 1
  if [ "$3" = "$NODE" ]; then echo 101 > "$T/node.mid"; else echo 102 > "$T/config.mid"; fi
}
umount() {
  echo "umount:$1" >> "$events"
  [ "$(cat "$T/status")" = stopped ] || { echo 'UNSAFE_LIVE_UNMOUNT' >> "$events"; return 1; }
  if [ "$1" = "$NODE" ]; then
    [ "$CASE" != unmountfail ] || return 1
    command cp "$T/original-node" "$NODE" && command rm "$T/node.mid"
  else
    command cp "$T/original-config" "$CONFIG" && command rm "$T/config.mid"
  fi
}
mv() {
  if [ "$CASE" = statewritefail ] && [ "$3" = "$STATE" ] && [ -f "$T/node.mid" ]; then
    case "$2" in *.next.*) return 1 ;; esac
  fi
  if [ "$CASE" = intentwritefail ] && [ "$3" = "$INTENT" ] && [ -f "$T/node.mid" ]; then return 1; fi
  command mv "$@"
}
echo $$ > "$T/pid"
'''

CASES = ('apply', 'midfail', 'midempty', 'statewritefail', 'intentwritefail',
         'ota_remove', 'ota_stock', 'foreign', 'stopfail', 'unmountfail', 'startfail', 'active',
         'huge', 'huge_legacy', 'dumpsysfail')
for case in CASES:
    with tempfile.TemporaryDirectory(prefix='video-runtime-test-') as tmp:
        root = Path(tmp); module = root/'module'; test=module/'test'; payload=module/'payload'
        test.mkdir(parents=True); payload.mkdir()
        stock=root/'stock'; stock.mkdir()
        values={'NODE':b'original-node', 'CONFIG':b'original-config', 'APK':b'original-apk', 'EXTENSION':b'original-extension'}
        paths={key:stock/key.lower() for key in values}
        for key,data in values.items(): paths[key].write_bytes(data)
        (test/'original-node').write_bytes(values['NODE'])
        (test/'original-config').write_bytes(values['CONFIG'])
        (payload/'node.so').write_bytes(b'patched-node'); (payload/'oplus_camera_config').write_bytes(b'patched-config')
        (test/'boot').write_text('testboot\n'); (test/'status').write_text('running\n')
        exe=stock/'provider'; exe.write_text('mock executable')
        exe.chmod(0o755)
        rc=stock/'provider.rc'; rc.write_text('service vendor.camera-provider '+linux(exe)+'\n')
        (module/'payload-manifest').write_text(
            f"payload/node.so {linux(paths['NODE'])} {digest(values['NODE'])} {digest(b'patched-node')}\n"
            f"payload/oplus_camera_config {linux(paths['CONFIG'])} {digest(values['CONFIG'])} {digest(b'patched-config')}\n")
        mode='apply'
        if case in ('ota_remove','ota_stock','foreign','stopfail','unmountfail','startfail'):
            mode='disable'
            paths['NODE'].write_bytes(b'patched-node'); paths['CONFIG'].write_bytes(b'patched-config')
            (test/'node.mid').write_text('999\n' if case=='foreign' else '101\n')
            (test/'config.mid').write_text('102\n')
            (module/'mount-state').write_text(f"testboot 101 {linux(paths['NODE'])}\ntestboot 102 {linux(paths['CONFIG'])}\n")
            if case in ('ota_remove','ota_stock'):
                paths['APK'].write_bytes(b'changed-apk'); paths['EXTENSION'].write_bytes(b'changed-extension')
            if case=='ota_stock': (test/'original-node').write_bytes(b'changed-stock-node')
        runtime=c.RUNTIME
        if case=='huge_legacy':
            # Negative control: the previous implementation must fail this harness.
            runtime=runtime.replace('(set -o pipefail || exit 1\n  dumpsys media.camera | awk',
                'dump=$(dumpsys media.camera) || return 1\n  printf \'%s\\n\' "$dump" | awk',1)
            runtime=runtime.replace('block!="[]") exit 1}\') || {', 'block!="[]") exit 1}\' || {',1)
        substitutions={
            '/data/adb/modules/noah_oneplus_native_video':linux(module),
            '/data/adb/modules_update/noah_oneplus_native_video':linux(root/'update'),
            '/odm/lib64/camera/components/com.oplus.node.sstabdefer.so':linux(paths['NODE']),
            '/odm/etc/camera/config/oplus_camera_config':linux(paths['CONFIG']),
            '/product/app/OplusCamera/OplusCamera.apk':linux(paths['APK']),
            '/odm/lib64/libextensionlayer.so':linux(paths['EXTENSION']),
            '/vendor/etc/init/vendor.qti.camera.provider-service_64.rc':linux(rc),
            '/vendor/bin/hw/vendor.qti.camera.provider-service_64':linux(exe),
            '/proc/sys/kernel/random/boot_id':linux(test/'boot'),
        }
        for before,after in substitutions.items(): runtime=runtime.replace(before,after)
        for key,data in values.items(): runtime=runtime.replace('@'+key+'@',digest(data))
        marker='case "$MODE" in apply|remove|disable)'
        runtime=runtime.replace(marker, '\nCASE='+case+'\n'+MOCK+'\n'+marker,1)
        script=module/'runtime.sh'; script.write_bytes(runtime.encode())
        for file in root.rglob('*'):
            if file.is_file(): file.write_bytes(file.read_bytes().replace(b'\r\n',b'\n'))
        result=subprocess.run(['bash',linux(script),mode],capture_output=True)
        out=result.stdout.decode(); err=result.stderr.decode()
        event=(test/'events').read_text() if (test/'events').exists() else ''
        assert 'UNSAFE_LIVE_UNMOUNT' not in event and 'NO_DURABLE_INTENT' not in event, (case,event)
        state=module/'mount-state'; pending=module/'provider-restart-pending'; intent=module/'mount-intent'
        def check(ok):
            if not ok: raise AssertionError((case,result.returncode,out,err,event,list(module.iterdir())))
        if case in ('apply','huge'): check(result.returncode==0 and state.exists() and len(state.read_text().splitlines())==2 and not pending.exists() and not intent.exists())
        elif case in ('midfail','midempty'):
            check(result.returncode!=0 and pending.exists() and intent.exists() and (test/'node.mid').exists() and 'umount:' not in event)
        elif case in ('statewritefail','intentwritefail'):
            check(result.returncode!=0 and not pending.exists() and not intent.exists() and not (test/'node.mid').exists())
            check('ctl.stop' in event and 'umount:' in event and 'ctl.start' in event)
        elif case=='ota_remove': check(result.returncode==0 and not state.exists() and not pending.exists() and not (test/'node.mid').exists())
        elif case=='ota_stock': check(result.returncode!=0 and state.exists() and pending.exists() and not (test/'node.mid').exists() and 'ctl.start' in event)
        elif case=='foreign': check(result.returncode!=0 and state.exists() and len(state.read_text().splitlines())==1 and (test/'node.mid').read_text().strip()=='999' and not (test/'config.mid').exists())
        elif case=='stopfail': check(result.returncode!=0 and 'umount:' not in event and 'ctl.start' in event and state.exists())
        elif case=='unmountfail': check(result.returncode!=0 and len(state.read_text().splitlines())==1 and 'ctl.start' in event)
        elif case=='startfail': check(result.returncode!=0 and pending.exists() and state.exists() and event.count('ctl.start')>=2)
        elif case=='active': check(result.returncode!=0 and not event and not (module/'runtime-lock').exists())
        elif case=='huge_legacy': check(result.returncode!=0 and not event and 'Argument list too long' in err)
        elif case=='dumpsysfail': check(result.returncode!=0 and not event and not (module/'runtime-lock').exists())
        if case!='startfail': check((test/'status').read_text().strip()=='running')
        print('PASS full-runtime',case)
print('15 complete runtime mocks passed, including 2MiB external-printf regression control and dumpsys failure; no device access.')
