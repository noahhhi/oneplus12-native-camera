#!/usr/bin/env python3
"""Build a PRIVATE, device-pinned KernelSU helper from locally extracted files.

The output contains proprietary camera data. Never publish the generated ZIP.
Usage: python build_native_hdr_helper.py --stock-dir /private/stock-camera --output /private/helper.zip
Only Python's standard library is required. No device access or installation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile

MODULE_ID = "noah_oneplus_native_hdr"
APK_HASH = "7833a1c3ca932503b77015d5d31493f99b0586580f68eb9ed14b93a2573fdd16"
LIB_HASH = "71a076548a3dc3de8c56b621c8e567ec89252dd4b9625328ec9c388338120c4c"
PATCHED_HASH = "05ccde9eed075c21e75d452c9c0fc3ca66012c1900f45cd80e686ccc33651f43"
CONFIGS = {
    "oplus_camera_aps_config": (
        "bf722f8b03e57a5e3bee39668dc8e092db75c51a94f44133d722eba2417a0640",
        "2174ee1b275061a608b88ab2aac02e74b9822d603849319823bbc980c056eaba"),
    "oplus_camera_algo_switch_config": (
        "01f18ab06f25fad610c581e5cd46de1e374dbfbb04219b8bf5cd61fae9c8564e",
        "7529c0b4abf0af06c4b28528e19252c2e2d7d5c2985cae639870775ff773b1f9"),
    "oplus_camera_preview_decision_config.json": (
        "2f3403eed909ae4733704c48edfda03aba7cc100cc57ad972bd9eb34b4f197e7",
        "571dbdf3c032087b7d2d36e56b57af0d814aad2618e55e284906c66375f1412e"),
}
PATCHES = ((0x1FB02B8, "2a0280d2", "2a1280d2"),
           (0x1FB04FC, "6a0680d2", "6a1680d2"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, expected):
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError(f"Version/hash mismatch: {path.name}")
    return data


def elf_file_offset(data, address, length=4):
    """Resolve a VA through an executable ELF64 little-endian AArch64 PT_LOAD."""
    if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("Expected little-endian ELF64 AArch64")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    entsize, count = struct.unpack_from("<HH", data, 54)
    if entsize < 56 or phoff + entsize * count > len(data):
        raise ValueError("Invalid ELF program header table")
    offsets = []
    for i in range(count):
        kind, flags, offset, va, _, size, _, _ = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + i * entsize)
        if kind == 1 and flags & 1 and va <= address and address + length <= va + size:
            resolved = offset + address - va
            if resolved + length > len(data):
                raise ValueError("Truncated ELF segment")
            offsets.append(resolved)
    if len(offsets) != 1:
        raise ValueError(f"VA {address:#x} has no unique executable file mapping")
    return offsets[0]


# Invoked by wrappers in the global mount namespace. All payload and target paths
# are fixed by this builder; manifest is data, never sourced as shell code.
RUNTIME = r"""#!/system/bin/sh
MODDIR=${0%/*}
MODE=${1:-}
STATE="$MODDIR/mount-state"
BOOT=$(cat /proc/sys/kernel/random/boot_id) || exit 1
file_sha() { sha256sum "$1" | awk '{print $1}'; }
mount_id() { awk -v p="$1" '$5 == p {id=$1} END {print id}' /proc/self/mountinfo; }
log() { echo "Native HDR: $*"; }
rollback() {
  [ -f "$STATE" ] || return 0
  remaining="$STATE.remaining.$$"
  # Build replacement state before removing any mount. Keep the original state
  # if recording a failure or committing the replacement itself fails.
  (umask 077; : > "$remaining") || return 1
  failed=0
  while read -r boot mid target; do
    [ "$boot" = "$BOOT" ] || continue
    if ! current=$(mount_id "$target"); then
      log "Cannot inspect mount ownership: $target"
      printf '%s %s %s\n' "$boot" "$mid" "$target" >> "$remaining" || {
        rm -f "$remaining"; return 1;
      }
      failed=1
      continue
    fi
    # A prior attempt may already have removed this bind. No file-level mount
    # remains, so this record can be discarded without touching anything.
    [ -n "$current" ] || continue
    if [ "$current" != "$mid" ]; then
      log "Refusing to unmount changed/foreign mount: $target"
      printf '%s %s %s\n' "$boot" "$mid" "$target" >> "$remaining" || {
        rm -f "$remaining"; return 1;
      }
      failed=1
      continue
    fi
    if ! umount "$target"; then
      log "Unmount failed; retaining record for retry: $target"
      printf '%s %s %s\n' "$boot" "$mid" "$target" >> "$remaining" || {
        rm -f "$remaining"; return 1;
      }
      failed=1
    fi
  done < "$STATE"
  if [ -s "$remaining" ]; then
    mv -f "$remaining" "$STATE" || { rm -f "$remaining"; return 1; }
  else
    rm -f "$STATE" "$remaining" || return 1
  fi
  return "$failed"
}
fail() { log "$*"; rollback; exit 1; }
case "$MODE" in
  remove)
    # Release mapped camera libraries before unmounting their backing files.
    am force-stop com.oplus.camera || {
      log "Cannot stop camera; mount state retained for retry."
      exit 1
    }
    rollback
    exit $?
    ;;
  apply) ;;
  *) log "Expected apply or remove"; exit 1 ;;
esac
[ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
# Never replace an already-running camera's mappings. Close it, then rerun service.
if pidof com.oplus.camera >/dev/null 2>&1; then
  log "Camera is running; apply deferred. Close it and rerun service.sh."
  exit 1
fi
if [ -f "$STATE" ]; then
  # Stale state from a previous boot is safe to discard; live mounts are not.
  oldboot=$(head -n 1 "$STATE" | awk '{print $1}')
  if [ "$oldboot" != "$BOOT" ]; then rm -f "$STATE"; else
    log "Existing session state; use action.sh to remove before reapplying."
    exit 1
  fi
fi
[ "$(file_sha /product/app/OplusCamera/OplusCamera.apk)" = "@APK_HASH@" ] || fail "Camera APK mismatch"
[ "$(getprop ro.build.version.sdk)" = 36 ] || fail "Android SDK mismatch"
while read -r source target original patched; do
  [ -f "$target" ] && [ ! -L "$MODDIR/$source" ] || fail "Missing target or unsafe payload"
  [ "$(file_sha "$target")" = "$original" ] || fail "Original target hash mismatch: $target"
  [ "$(file_sha "$MODDIR/$source")" = "$patched" ] || fail "Payload hash mismatch: $source"
  # Refuse to stack on an existing file bind, even if its bytes happen to match.
  [ -z "$(mount_id "$target")" ] || fail "Target already mounted: $target"
done < "$MODDIR/payload-manifest"
: > "$STATE" || exit 1
trap 'rollback' EXIT
trap 'exit 1' HUP INT TERM
while read -r source target original patched; do
  label=$(ls -Zd "$target" | awk '{print $1}')
  case "$label" in u:object_r:*:s0) ;; *) fail "Invalid SELinux target label" ;; esac
  chown 0:0 "$MODDIR/$source" || fail "chown failed"
  chmod 0644 "$MODDIR/$source" || fail "chmod failed"
  chcon "$label" "$MODDIR/$source" || fail "chcon failed"
  mount --bind "$MODDIR/$source" "$target" || fail "Bind mount failed"
  mid=$(mount_id "$target")
  if [ -z "$mid" ]; then
    umount "$target"
    fail "Cannot identify newly created mount"
  fi
  # Record ownership immediately. Never remove another task's mounts.
  echo "$BOOT $mid $target" >> "$STATE" || { umount "$target"; fail "Cannot record mount"; }
  [ "$(file_sha "$target")" = "$patched" ] || fail "Mounted payload verification failed"
done < "$MODDIR/payload-manifest"
trap - EXIT HUP INT TERM
log "Applied four verified binds. Original partitions are unchanged."
"""


def wrapper(mode, disable=False):
    prefix = '#!/system/bin/sh\nMODDIR=${0%/*}\n'
    if disable:
        prefix += 'touch "$MODDIR/disable" || exit 1\n'
    # Module paths cannot contain quotes; accepted base directory is fixed.
    prefix += (
        'case "$MODDIR" in /data/adb/modules/noah_oneplus_native_hdr|'
        '/data/adb/modules_update/noah_oneplus_native_hdr) ;; *) exit 1 ;; esac\n'
        f'exec su -M -c "/system/bin/sh $MODDIR/runtime.sh {mode}"\n')
    return prefix


def build(stock, output):
    checked(stock / "OnePlus-Camera-6.070.215.apk", APK_HASH)
    original = checked(stock / "native/libAlgoInterface.so", LIB_HASH)
    patched = bytearray(original)
    patch_report = []
    for va, before, after in PATCHES:
        off = elf_file_offset(original, va)
        if original[off:off + 4] != bytes.fromhex(before):
            raise ValueError(f"Original instruction mismatch at VA {va:#x}")
        patched[off:off + 4] = bytes.fromhex(after)
        patch_report.append({"va": hex(va), "file_offset": hex(off),
                             "original": before, "patched": after})
    if digest(patched) != PATCHED_HASH:
        raise ValueError("Patched library hash mismatch")
    files = {}
    manifest = []
    for name, (oldhash, newhash) in CONFIGS.items():
        checked(stock / "device-config" / name, oldhash)
        data = checked(stock / "native-overlays" / name, newhash)
        json.loads(data)
        source = "payload/" + name
        files[source] = data
        manifest.append(f"{source} /odm/etc/camera/config/{name} {oldhash} {newhash}")
    files["payload/libAlgoInterface.so"] = bytes(patched)
    manifest.append(f"payload/libAlgoInterface.so /odm/lib64/libAlgoInterface.so {LIB_HASH} {PATCHED_HASH}")
    files.update({
        "module.prop": (
            f"id={MODULE_ID}\nname=OnePlus 12 Native Master HDR (private)\n"
            "version=0.2\nversionCode=2\nauthor=noahhhi\n"
            "description=Camera 6.070.215 / Android 16 only. Experimental native HDR for ultra-wide 0.6x, main 1x, tele 3x/6x automatic JPG. Action disables and removes binds. PRIVATE payload; do not distribute.\n"),
        "skip_mount": "",
        "runtime.sh": RUNTIME.replace("@APK_HASH@", APK_HASH),
        "service.sh": wrapper("apply"),
        "uninstall.sh": wrapper("remove"),
        "action.sh": wrapper("remove", disable=True),
        "payload-manifest": "\n".join(manifest) + "\n",
        "customize.sh": (
            '[ "$KSU" = true ] || abort "KernelSU required"\n'
            '[ "$ARCH" = arm64 ] || abort "arm64 required"\n'
            'set_perm_recursive "$MODPATH" 0 0 0755 0644\n'
            'for script in service.sh runtime.sh uninstall.sh action.sh; do\n'
            '  set_perm "$MODPATH/$script" 0 0 0755\n'
            'done\n'
            'ui_print "PRIVATE original-camera payload. Never upload this ZIP."\n'
            'ui_print "Close camera before activation. Action removes binds and disables."\n'),
        "build-manifest.json": json.dumps({
            "private_payload": True, "camera_apk_sha256": APK_HASH,
            "original_library_sha256": LIB_HASH, "patched_library_sha256": PATCHED_HASH,
            "patches": patch_report,
        }, indent=2) + "\n",
        "PRIVATE-DO-NOT-PUBLISH.txt": (
            "Contains proprietary original camera binaries/configuration.\n"
            "Keep this ZIP private. Publish only the builder source.\n"
            "No reboot or installation was performed by the builder.\n"
            "Activation requires camera closed and exact original target hashes.\n"
            "Disable/uninstall without reboot: run action.sh. Ordinary KSU disable\n"
            "does not remove binds already mounted in the current boot.\n"),
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidentally overwriting an existing artifact.
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, (2026, 10, 20, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return patch_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build(args.stock_dir.resolve(), args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "private": True,
                      "sha256": digest(args.output.read_bytes()), "patches": report}, indent=2))


if __name__ == "__main__":
    main()
