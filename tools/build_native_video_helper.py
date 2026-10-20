#!/usr/bin/env python3
"""Build a private, firmware-pinned experimental video addon from explicit local inputs.

Original builder source only; no firmware binaries or patch payloads are distributed.
No device access or installation.

Generated ZIP contains proprietary firmware. Motion validation remains pending.
Requires explicit --experimental; independent of the photo helper.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

MODULE = "noah_oneplus_native_video"
APK = "7833a1c3ca932503b77015d5d31493f99b0586580f68eb9ed14b93a2573fdd16"
NODE = "2b7b5bc7163af849a1f4652ba793dc4cb842e55b5c043e3909b52db4eacac056"
PATCHED = "55d3050166fd6f81651acae254642b9125644d3ddccc63743be8d6e42e2ff9c5"
EXTENSION = "cb14f0198ac77bebfd9f21ff2e31f6d01b34d369e3c7e74b2014ec81a4d140e0"
CONFIG = "c4cf905bd56a92d28b727debe0f903ce091ceec0a12386e4e1cab0aa556d6fc1"
SAT_CONFIG = "a484d66788263bbe812e2c08e1e5169804c5e210a2ce3c7019aac050345cba59"

RUNTIME = r'''#!/system/bin/sh
MODDIR=${0%/*}
MODE=${1:-}
case "$MODDIR" in /data/adb/modules/noah_oneplus_native_video|/data/adb/modules_update/noah_oneplus_native_video) ;; *) exit 1 ;; esac
STATE="$MODDIR/mount-state"
PENDING="$MODDIR/provider-restart-pending"
INTENT="$MODDIR/mount-intent"
LOCK="$MODDIR/runtime-lock"
SERVICE=vendor.camera-provider
EXE=/vendor/bin/hw/vendor.qti.camera.provider-service_64
RC=/vendor/etc/init/vendor.qti.camera.provider-service_64.rc
NODE=/odm/lib64/camera/components/com.oplus.node.sstabdefer.so
CONFIG=/odm/etc/camera/config/oplus_camera_config
BOOT=$(cat /proc/sys/kernel/random/boot_id) || exit 1
NEED_RECOVERY=0
PROVIDER_MAY_BE_STOPPED=0
FRESH_ID=
FRESH_TARGET=
log() { echo "Native video EXPERIMENTAL: $*"; }
sha() { sha256sum "$1" | awk '{print $1}'; }
mid() { awk -v p="$1" '$5==p {n++; id=$1} END {if(n>1) exit 1; print id}' /proc/self/mountinfo; }
idle() {
  # Fail closed on unknown format or ANY active client, including stock camera.
  # Stream potentially megabytes of dumpsys output; never pass it as one argv.
  (set -o pipefail || exit 1
  dumpsys media.camera | awk '
    /^Active Camera Clients:/ {if(seen++) exit 1; active=1; next}
    active && /^Allowed user IDs:/ {done=1; active=0; next}
    active {gsub(/[[:space:]]/, ""); block=block $0}
    END {if(seen!=1 || !done || block!="[]") exit 1}') || {
      log "Camera clients active/unknown. Close all camera clients before retrying; none stopped."
      return 1
    }
}
service_identity() {
  [ -f "$RC" ] && [ -x "$EXE" ] || return 1
  awk -v s="$SERVICE" -v x="$EXE" '$1=="service" && $2==s {n++; if(NF!=3 || $3!=x) bad=1} END {exit !(n==1 && !bad)}' "$RC"
}
provider_pid() {
  value=$(pidof vendor.qti.camera.provider-service_64) || return 1
  case "$value" in ''|*[!0-9]*) return 1 ;; esac
  [ -d "/proc/$value" ] || return 1
  [ "$(readlink "/proc/$value/exe")" = "$EXE" ] || return 1
  printf '%s\n' "$value"
}
restart_provider() {
  service_identity || { log "Provider service identity mismatch"; return 1; }
  idle || return 1
  old=$(provider_pid) || {
    # An earlier failed restart may leave the verified init service stopped.
    [ -z "$(pidof vendor.qti.camera.provider-service_64)" ] || return 1
    old=
  }
  setprop ctl.restart "$SERVICE" || return 1
  elapsed=0; stable=0; previous=
  while [ "$elapsed" -lt 30 ]; do
    sleep 1
    elapsed=$((elapsed+1))
    current=$(provider_pid) || current=
    if [ -n "$current" ] && [ "$current" != "$old" ] && [ "$(getprop "init.svc.$SERVICE")" = running ]; then
      if [ "$current" = "$previous" ]; then stable=$((stable+1)); else stable=1; fi
      [ "$stable" -ge 3 ] && return 0
    else
      stable=0
    fi
    previous=$current
  done
  log "Provider did not stabilize within 30 seconds"
  return 1
}
stop_provider() {
  service_identity || return 1
  idle || return 1
  if ! provider_pid >/dev/null; then
    [ -z "$(pidof vendor.qti.camera.provider-service_64)" ] || return 1
  fi
  # Mark before ctl.stop: interruption or timeout still requires ctl.start.
  PROVIDER_MAY_BE_STOPPED=1
  setprop ctl.stop "$SERVICE" || return 1
  stop_elapsed=0
  while [ "$stop_elapsed" -lt 30 ]; do
    if [ "$(getprop "init.svc.$SERVICE")" = stopped ] && [ -z "$(pidof vendor.qti.camera.provider-service_64)" ]; then
      return 0
    fi
    sleep 1
    stop_elapsed=$((stop_elapsed+1))
  done
  log "Provider stop did not complete within 30 seconds; unmount refused"
  return 1
}
start_provider() {
  # No idle gate here: even a rollback error must not deliberately leave it stopped.
  service_identity || { log "Cannot safely start changed provider service"; return 1; }
  setprop ctl.start "$SERVICE" || return 1
  start_elapsed=0; start_stable=0; start_previous=
  while [ "$start_elapsed" -lt 30 ]; do
    sleep 1
    start_elapsed=$((start_elapsed+1))
    start_current=$(provider_pid) || start_current=
    if [ -n "$start_current" ] && [ "$(getprop "init.svc.$SERVICE")" = running ]; then
      if [ "$start_current" = "$start_previous" ]; then start_stable=$((start_stable+1)); else start_stable=1; fi
      if [ "$start_stable" -ge 3 ]; then PROVIDER_MAY_BE_STOPPED=0; return 0; fi
    else
      start_stable=0
    fi
    start_previous=$start_current
  done
  log "Provider start failed to stabilize within 30 seconds; recovery marker retained"
  return 1
}
rollback() {
  [ -f "$STATE" ] || return 0
  remaining="$STATE.remaining.$$"
  (umask 077; : > "$remaining") || return 1
  failed=0
  while read -r boot id target extra; do
    [ "$boot" = "$BOOT" ] || continue
    case "$target" in "$NODE"|"$CONFIG") ;; *) log "Invalid state target; preserving state"; rm -f "$remaining"; return 1 ;; esac
    case "$id" in ''|*[!0-9]*) rm -f "$remaining"; return 1 ;; esac
    [ -z "$extra" ] || { rm -f "$remaining"; return 1; }
    current=$(mid "$target") || current=unknown
    [ -n "$current" ] || continue
    if [ "$current" != "$id" ] || ! umount "$target"; then
      log "Retaining failed/foreign mount record: $target"
      printf '%s %s %s\n' "$boot" "$id" "$target" >> "$remaining" || { rm -f "$remaining"; return 1; }
      failed=1
    fi
  done < "$STATE"
  # Keep even the empty ownership ledger until hashes AND provider startup pass.
  mv -f "$remaining" "$STATE" || { rm -f "$remaining"; return 1; }
  return "$failed"
}
record_owned() {
  next="$STATE.next.$$"
  (umask 077; cat "$STATE" > "$next" && printf '%s %s %s\n' "$BOOT" "$FRESH_ID" "$FRESH_TARGET" >> "$next") || { rm -f "$next"; return 1; }
  mv -f "$next" "$STATE" || { rm -f "$next"; return 1; }
  sync || return 1
}
write_intent() {
  intent_next="$INTENT.next.$$"
  (umask 077; printf '%s %s %s\n' "$BOOT" "$1" "$2" > "$intent_next") || return 1
  mv -f "$intent_next" "$INTENT" || return 1
  sync || return 1
}
rollback_intent() {
  [ -f "$INTENT" ] || return 0
  read -r intent_boot intent_id intent_target intent_extra < "$INTENT" || return 1
  [ -z "$intent_extra" ] || return 1
  case "$intent_target" in "$NODE"|"$CONFIG") ;; *) return 1 ;; esac
  [ "$intent_boot" = "$BOOT" ] || { rm -f "$INTENT"; return $?; }
  intent_current=$(mid "$intent_target") || { log "Cannot inspect unfinished bind; intent retained"; return 1; }
  if [ -z "$intent_current" ]; then
    if [ "$intent_id" = unknown ]; then
      case "$intent_target" in "$NODE") expected='@NODE@' ;; "$CONFIG") expected='@CONFIG@' ;; esac
      [ "$(sha "$intent_target")" = "$expected" ] || {
        log "Unclaimed bind absent from mount inspection but bytes not original; intent retained"; return 1;
      }
    fi
    rm -f "$INTENT"; return $?
  fi
  # An immediate in-memory ID can recover a failed durable ledger write.
  if [ "$intent_id" = unknown ] && [ "$FRESH_TARGET" = "$intent_target" ] && [ -n "$FRESH_ID" ]; then
    intent_id=$FRESH_ID
  fi
  case "$intent_id" in ''|*[!0-9]*) log "Unclaimed bind identity; NEVER unmounting it. Intent retained for manual verification"; return 1 ;; esac
  [ "$intent_current" = "$intent_id" ] || { log "Unfinished bind replaced by foreign mount; intent retained"; return 1; }
  umount "$intent_target" || return 1
  rm -f "$INTENT"
}
originals() {
  [ "$(sha "$NODE")" = '@NODE@' ] && [ "$(sha "$CONFIG")" = '@CONFIG@' ]
}
recover() {
  # Do not disturb a newly opened unrelated client during failure recovery.
  idle || { log "Recovery deferred: close clients, rerun Action; state retained"; return 1; }
  am force-stop com.oplus.camera || return 1
  recovery_failed=0
  if stop_provider; then
    rollback || recovery_failed=1
    rollback_intent || recovery_failed=1
    originals || { log "Original hashes not fully restored; state retained"; recovery_failed=1; }
  else
    log "Stop failed; no unmount attempted"
    recovery_failed=1
  fi
  # Finally-like path: attempt start even after stop/umount/hash failure.
  start_provider || recovery_failed=1
  [ "$recovery_failed" = 0 ] || return 1
  rm -f "$PENDING" "$STATE"
}
finish() {
  status=$?
  trap - EXIT HUP INT TERM
  if [ "$status" -ne 0 ] && [ "$NEED_RECOVERY" = 1 ] && [ -f "$PENDING" ]; then
    recover || log "RECOVERY INCOMPLETE: state preserved; close camera clients and retry Action"
  fi
  if [ "$PROVIDER_MAY_BE_STOPPED" = 1 ]; then
    start_provider || { log "URGENT: verified provider could not be restarted; recovery marker retained"; status=1; }
  fi
  rmdir "$LOCK" 2>/dev/null
  exit "$status"
}
case "$MODE" in apply|remove|disable) ;; *) log "Expected apply/remove/disable"; exit 1 ;; esac
if [ "$MODE" = apply ]; then
  [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
  [ "$(getprop sys.boot_completed)" = 1 ] || { log "Framework not ready; deferred"; exit 1; }
  if pidof com.oplus.camera >/dev/null 2>&1; then log "Stock camera running; close it before activation"; exit 1; fi
fi
# No force-stop, binds, disable marker or restart before checking all clients.
idle || exit 1
service_identity || { log "Service declaration mismatch"; exit 1; }
if ! provider_pid >/dev/null; then
  if [ "$MODE" = apply ] || [ -n "$(pidof vendor.qti.camera.provider-service_64)" ]; then
    log "Provider PID verification failed"; exit 1
  fi
fi
if [ "$MODE" = apply ]; then
  [ "$(sha /product/app/OplusCamera/OplusCamera.apk)" = '@APK@' ] || { log "APK mismatch"; exit 1; }
  [ "$(sha /odm/lib64/libextensionlayer.so)" = '@EXTENSION@' ] || { log "Extension mismatch"; exit 1; }
  [ "$(getprop ro.build.version.sdk)" = 36 ] || { log "SDK mismatch"; exit 1; }
fi
mkdir "$LOCK" 2>/dev/null || { log "Runtime busy; inspect existing lock before retry"; exit 1; }
trap finish EXIT
trap 'exit 1' HUP INT TERM
idle || exit 1
if [ "$MODE" != apply ]; then
  [ "$MODE" != disable ] || touch "$MODDIR/disable" || exit 1
  am force-stop com.oplus.camera || exit 1
  [ -f "$STATE" ] || [ -f "$PENDING" ] || [ -f "$INTENT" ] || exit 0
  printf '%s\n' "$BOOT" > "$PENDING" || exit 1
  recover || exit 1
  log "Owned binds removed; original provider restarted"
  exit 0
fi
if [ -f "$STATE" ]; then
  oldboot=$(head -n 1 "$STATE" | awk '{print $1}')
  [ "$oldboot" != "$BOOT" ] || { log "Existing state; use Action before reapplying"; exit 1; }
  rm -f "$STATE" || exit 1
fi
if [ -f "$PENDING" ]; then
  [ "$(cat "$PENDING")" != "$BOOT" ] || { log "Recovery pending; use Action first"; exit 1; }
  rm -f "$PENDING" || exit 1
fi
if [ -f "$INTENT" ]; then
  intent_boot=$(head -n 1 "$INTENT" | awk '{print $1}')
  [ "$intent_boot" != "$BOOT" ] || { log "Unfinished mount intent; use Action/review ownership first"; exit 1; }
  rm -f "$INTENT" || exit 1
fi
while read -r source target original patched; do
  [ -f "$target" ] && [ ! -L "$MODDIR/$source" ] || exit 1
  [ "$(sha "$target")" = "$original" ] || { log "Original hash mismatch: $target"; exit 1; }
  [ "$(sha "$MODDIR/$source")" = "$patched" ] || { log "Payload hash mismatch"; exit 1; }
  mountid=$(mid "$target") || exit 1
  [ -z "$mountid" ] || { log "Pre-existing target bind; refusing"; exit 1; }
done < "$MODDIR/payload-manifest"
idle || exit 1
(umask 077; : > "$STATE") || exit 1
printf '%s\n' "$BOOT" > "$PENDING" || exit 1
NEED_RECOVERY=1
while read -r source target original patched; do
  label=$(ls -Zd "$target" | awk '{print $1}')
  case "$label" in u:object_r:*:s0) ;; *) exit 1 ;; esac
  chown 0:0 "$MODDIR/$source" && chmod 0644 "$MODDIR/$source" && chcon "$label" "$MODDIR/$source" || exit 1
  FRESH_ID=
  FRESH_TARGET=$target
  write_intent unknown "$target" || exit 1
  mount --bind "$MODDIR/$source" "$target" || exit 1
  FRESH_ID=$(mid "$target") || { FRESH_ID=; log "Unknown new mount identity; durable intent retained"; exit 1; }
  case "$FRESH_ID" in ''|*[!0-9]*) FRESH_ID=; log "Missing new mount identity; durable intent retained"; exit 1 ;; esac
  write_intent "$FRESH_ID" "$target" || exit 1
  record_owned || { log "Ownership ledger write failed; recovering verified fresh mount after provider stop"; exit 1; }
  rm -f "$INTENT" || exit 1
  FRESH_ID=
  FRESH_TARGET=
  [ "$(sha "$target")" = "$patched" ] || exit 1
done < "$MODDIR/payload-manifest"
restart_provider || exit 1
rm -f "$PENDING" || exit 1
log "Experimental video binds active; motion remains unverified"
'''


def checked(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Hash mismatch: " + path.name)
    return data


def wrapper(mode, boot=False):
    text = '#!/system/bin/sh\nMODDIR=${0%/*}\n'
    text += ('case "$MODDIR" in /data/adb/modules/' + MODULE + '|/data/adb/modules_update/' + MODULE + ') ;; *) exit 1 ;; esac\n')
    if boot:
        text += 'n=0\nwhile [ "$(getprop sys.boot_completed)" != 1 ] && [ "$n" -lt 90 ]; do sleep 2; n=$((n+1)); done\n'
        text += '[ "$(getprop sys.boot_completed)" = 1 ] || exit 1\n'
    return text + 'exec su -M -c "/system/bin/sh $MODDIR/runtime.sh ' + mode + '"\n'


def build(camera_apk, original_node, extension_library, original_config,
          patched_node, sat_config, output):
    # Generated firmware must never enter this public checkout, including via symlinks.
    checkout = Path(__file__).resolve().parent.parent
    output = output.expanduser().resolve()
    if output.is_relative_to(checkout):
        raise ValueError('Private firmware output must be outside the public checkout')
    if output.exists():
        raise FileExistsError('Refusing to overwrite existing output')
    checked(camera_apk, APK)
    checked(original_node, NODE)
    checked(extension_library, EXTENSION)
    checked(original_config, CONFIG)
    node = checked(patched_node, PATCHED)
    config = checked(sat_config, SAT_CONFIG)
    parsed = json.loads(config)
    rows = parsed['file_data']
    for key in ('com.oplus.feature.video.dv.sat.support', 'com.oplus.feature.video.dv.60fps.sat.support'):
        matches = [r for r in rows if r.get('VendorTag') == key]
        if len(matches) != 1 or str(matches[0]['Value']) != '1':
            raise ValueError('SAT-only config gate mismatch: ' + key)
    runtime = RUNTIME
    for key, value in dict(APK=APK, NODE=NODE, CONFIG=CONFIG, EXTENSION=EXTENSION).items():
        runtime = runtime.replace('@' + key + '@', value)
    files = {
        'module.prop': 'id=' + MODULE + '\nname=OnePlus 12 Native Video PRIVATE EXPERIMENTAL\nversion=0.1-experimental\nversionCode=1\nauthor=noahhhi\ndescription=PRIVATE candidate; exact firmware only, motion unverified. Separate from photo helper. Action removes owned video binds and restarts verified provider.\n',
        'skip_mount': '',
        'runtime.sh': runtime,
        'service.sh': wrapper('apply', boot=True),
        'action.sh': wrapper('disable'),
        'uninstall.sh': wrapper('remove'),
        'payload/node.so': node,
        'payload/oplus_camera_config': config,
        'payload-manifest': f'payload/node.so /odm/lib64/camera/components/com.oplus.node.sstabdefer.so {NODE} {PATCHED}\npayload/oplus_camera_config /odm/etc/camera/config/oplus_camera_config {CONFIG} {SAT_CONFIG}\n',
        'customize.sh': '[ "$KSU" = true ] || abort "KernelSU required"\n[ "$ARCH" = arm64 ] || abort "arm64 required"\nset_perm_recursive "$MODPATH" 0 0 0755 0644\nfor f in runtime.sh service.sh action.sh uninstall.sh; do set_perm "$MODPATH/$f" 0 0 0755; done\nui_print "PRIVATE experimental video candidate; no installation-time activation."\nui_print "Close all camera clients before Action or activation. Motion unverified."\n',
        'PRIVATE-EXPERIMENTAL.txt': 'PRIVATE firmware payload. Do not publish ZIP. No universal compatibility claim.\nNo device actions performed by builder. Root review and mocked lifecycle tests required before installation.\nThis addon is independent of photo0.2. Motion unverified; rollback can defer if another client becomes active.\nClose all camera clients before activate/Action/uninstall. Action disables and unmounts owned binds and restarts the exact provider.\nDo not uninstall while rollback is blocked; resolve mounts first to retain recovery records.\n',
        'build-manifest.json': json.dumps({'private_payload': True, 'experimental': True, 'motion_verified': False, 'installation_authorized_by_builder': False, 'original_node_sha256': NODE, 'patched_node_sha256': PATCHED, 'extension_sha256': EXTENSION, 'camera_apk_sha256': APK, 'original_config_sha256': CONFIG, 'sat_config_sha256': SAT_CONFIG}, indent=2) + '\n',
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, (2026, 10, 21, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            archive.writestr(info, data.encode() if isinstance(data, str) else data)
    print('PRIVATE candidate built; NOT installed: ' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('camera-apk', 'original-node', 'extension-library', 'original-config', 'patched-node', 'sat-config'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--experimental', action='store_true', required=True)
    args = parser.parse_args()
    build(args.camera_apk, args.original_node, args.extension_library, args.original_config,
          args.patched_node, args.sat_config, args.output)
