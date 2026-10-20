"""Host-only mocked shell lifecycle tests; never invokes ADB or Android services."""
import importlib.util
from pathlib import Path
import subprocess

source = Path(__file__).resolve().parents[1] / 'tools/build_native_video_helper.py'
spec = importlib.util.spec_from_file_location('candidate', source)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
functions = candidate.RUNTIME.split('log() {', 1)[1].split('case "$MODE" in apply|remove|disable)', 1)[0]
functions = 'log() {' + functions
for key in ('NODE', 'CONFIG'):
    functions = functions.replace('@' + key + '@', getattr(candidate, key))

mock = r'''
T=$(mktemp -d) || exit 1
trap 'rm -rf "$T"' EXIT
STATE="$T/state"; PENDING="$T/pending"; LOCK="$T/lock"
NODE=/odm/lib64/camera/components/com.oplus.node.sstabdefer.so
CONFIG=/odm/etc/camera/config/oplus_camera_config
SERVICE=vendor.camera-provider
BOOT=boot123; NEED_RECOVERY=0; PROVIDER_MAY_BE_STOPPED=0
mkdir "$LOCK"
touch "$PENDING" "$T/node" "$T/config"
printf 'running' > "$T/provider"
printf '%s\n' "$BOOT 101 $NODE" "$BOOT 102 $CONFIG" > "$STATE"
idle() { [ "$CASE" != active ]; }
service_identity() { return 0; }
provider_pid() { [ "$(cat "$T/provider")" = running ] && echo 1234; }
pidof() { provider_pid; }
getprop() { cat "$T/provider"; }
sleep() { :; }
am() { echo am >> "$T/events"; return 0; }
setprop() {
  echo "$1" >> "$T/events"
  case "$1" in
    ctl.stop)
      [ "$CASE" != stopfail ] || return 1
      printf stopped > "$T/provider" ;;
    ctl.start)
      [ "$CASE" != startfail ] || return 1
      if [ "$CASE" = transientstart ] && [ ! -f "$T/start-once" ]; then touch "$T/start-once"; return 1; fi
      printf running > "$T/provider" ;;
    *) return 1 ;;
  esac
}
mid() {
  if [ "$1" = "$NODE" ] && [ -f "$T/node" ]; then echo 101; fi
  if [ "$1" = "$CONFIG" ] && [ -f "$T/config" ]; then echo 102; fi
}
umount() {
  echo "umount:$1" >> "$T/events"
  # Simulate the observed kernel behavior: live provider keeps node mount busy.
  if [ "$(cat "$T/provider")" != stopped ]; then echo busy >> "$T/events"; return 1; fi
  if [ "$1" = "$NODE" ]; then
    [ "$CASE" != unmountfail ] || return 1
    rm "$T/node"
  else
    rm "$T/config"
  fi
}
sha() {
  if [ "$1" = "$NODE" ]; then
    if [ -f "$T/node" ]; then echo patched; else echo '@NODE@'; fi
  else
    if [ -f "$T/config" ]; then echo patched; else echo '@CONFIG@'; fi
  fi
}
recover
rc=$?
if [ "$CASE" = transientstart ] && [ "$PROVIDER_MAY_BE_STOPPED" = 1 ]; then start_provider; fi
case "$CASE" in
  success)
    [ "$rc" = 0 ] && [ ! -f "$STATE" ] && [ ! -f "$PENDING" ] || exit 11
    [ "$(cat "$T/provider")" = running ] || exit 12
    [ "$(sed -n '2p' "$T/events")" = ctl.stop ] || exit 13
    [ "$(tail -n 1 "$T/events")" = ctl.start ] || exit 14 ;;
  stopfail)
    [ "$rc" != 0 ] && [ "$(wc -l < "$STATE")" = 2 ] && [ -f "$PENDING" ] || exit 21
    ! grep -q umount "$T/events" || exit 22
    [ "$(cat "$T/provider")" = running ] && grep -q ctl.start "$T/events" || exit 23 ;;
  unmountfail)
    [ "$rc" != 0 ] && [ "$(wc -l < "$STATE")" = 1 ] && [ -f "$PENDING" ] || exit 31
    [ "$(cat "$T/provider")" = running ] && grep -q ctl.start "$T/events" || exit 32 ;;
  startfail)
    [ "$rc" != 0 ] && [ -f "$PENDING" ] && [ "$PROVIDER_MAY_BE_STOPPED" = 1 ] || exit 41
    grep -q ctl.start "$T/events" || exit 42 ;;
  transientstart)
    [ "$rc" != 0 ] && [ -f "$PENDING" ] || exit 51
    [ "$(cat "$T/provider")" = running ] && [ "$PROVIDER_MAY_BE_STOPPED" = 0 ] || exit 52
    [ "$(grep -c ctl.start "$T/events")" = 2 ] || exit 53 ;;
  active)
    [ "$rc" != 0 ] && [ ! -f "$T/events" ] && [ "$(wc -l < "$STATE")" = 2 ] || exit 61 ;;
esac
[ ! -f "$T/events" ] || ! grep -q '^busy$' "$T/events" || exit 70
echo "PASS $CASE"
'''
for key in ('NODE', 'CONFIG'):
    mock = mock.replace('@' + key + '@', getattr(candidate, key))

for case in ('success', 'stopfail', 'unmountfail', 'startfail', 'transientstart', 'active'):
    script = functions + '\nCASE=' + case + '\n' + mock
    result = subprocess.run(['bash'],
                            input=script.encode(), capture_output=True)
    print(result.stdout.decode().strip())
    if result.returncode:
        raise RuntimeError(f'{case}: exit {result.returncode}; {result.stderr}')
print('All six host-only lifecycle cases passed; persistent init start failure remains an explicit recovery error.')
