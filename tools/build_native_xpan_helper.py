#!/usr/bin/env python3
"""Build experimental photo helper0.3 from local firmware/configuration inputs.

Keeps the master-only0.2 builder unchanged. Generated ZIP contains proprietary
files: keep it private. Requires the companion APK17+ enabled for the camera in
LSPosed. Does not install, connect to a device, or alter the video helper.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("master_helper", ROOT / "build_native_hdr_helper.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

PATCHED_HASH = "ec6820cefb3c0aaeb8b9a4d3fab534c868e8f7e0affb8253e62c1af6bba17b3c"
CONFIG_PINS = {
    "oplus_camera_aps_config": "9cdb968a403f9bb81d105cf9833180e42822ba5a2afe5c95b3109f1e1a241f68",
    "oplus_camera_algo_switch_config": "ff62cd81eaad7d06df34a2a71cee58a4fdfb923d1d362376ba9bd2808a780a9d",
    "oplus_camera_preview_decision_config.json": "91f94844a9c5453e29f914c28f5e39f8cc04a6948734f57240f5c461ce30bd9c",
}
UNIT_ORIGINAL_HASH = "d1536ef374145a06330abb9053f9eea1687ccc81df879aa35e44ffd9d4bb89ef"
UNIT_PATCHED_HASH = "eb8b133ff3a38db2bbc2b5a37689e5095394b4c34d06729b7450ec56a64666d8"
XPAN_PATCHES = ((0x1FB02C0, "0a10a0f2", "0a10a4f2"),
                (0x1FB0504, "0a10a0f2", "0a10a4f2"))


def runtime_script():
    script = base.RUNTIME
    assert script.count("rollback() {") == 1
    script = script.replace("rollback() {", "rollback_mounts() {", 1)
    cleanup = r'''rollback() {
  # Keep the RAW-usecase gate until every photo binding is actually gone.
  rollback_mounts || return 1
  while read -r source target original patched; do
    current=$(mount_id "$target") || return 1
    if [ -n "$current" ]; then
      log "Photo target still mounted; retaining XPAN property. Keep camera closed: $target"
      return 1
    fi
  done < "$MODDIR/payload-manifest"
  setprop debug.noah.hdr.xpan_native 0 || {
    log "Photo mounts removed, property cleanup failed; keep camera closed and retry remove."
    return 1
  }
  [ "$(getprop debug.noah.hdr.xpan_native)" = 0 ] || return 1
}
'''
    assert script.count('fail() { log "$*"; rollback; exit 1; }') == 1
    script = script.replace('fail() { log "$*"; rollback; exit 1; }',
                            cleanup + '\nfail() { log "$*"; rollback; exit 1; }', 1)
    assert script.count("trap - EXIT HUP INT TERM") == 1
    script = script.replace("trap - EXIT HUP INT TERM", '''setprop debug.noah.hdr.xpan_native 1 || fail "Cannot enable XPAN SDK gate"
[ "$(getprop debug.noah.hdr.xpan_native)" = 1 ] || fail "XPAN SDK gate readback failed"
trap - EXIT HUP INT TERM''', 1)
    script = script.replace("Applied four verified binds. Original partitions are unchanged.",
                            "Applied five verified photo binds and XPAN gate. LSPosed camera scope is required.")
    return script.replace("@APK_HASH@", base.APK_HASH)


RUNTIME = runtime_script()


def build(stock, xpan_configs, unit_config, output):
    base.checked(stock / "OnePlus-Camera-6.070.215.apk", base.APK_HASH)
    original = base.checked(stock / "native/libAlgoInterface.so", base.LIB_HASH)
    patched = bytearray(original)
    patch_report = []
    for va, before, after in (*base.PATCHES, *XPAN_PATCHES):
        off = base.elf_file_offset(original, va)
        if original[off:off+4] != bytes.fromhex(before):
            raise ValueError(f"Original instruction mismatch at {va:#x}")
        patched[off:off+4] = bytes.fromhex(after)
        patch_report.append({"va": hex(va), "file_offset": hex(off),
                             "original": before, "patched": after})
    if base.digest(patched) != PATCHED_HASH:
        raise ValueError("Master+XPAN patched library hash mismatch")
    files, manifest = {}, []
    for name, pin in CONFIG_PINS.items():
        original_hash = base.CONFIGS[name][0]
        base.checked(stock / "device-config" / name, original_hash)
        data = base.checked(xpan_configs / name, pin)
        json.loads(data)
        source = "payload/" + name
        files[source] = data
        manifest.append(f"{source} /odm/etc/camera/config/{name} {original_hash} {pin}")
    base.checked(stock / "device-config/camera_unit_config", UNIT_ORIGINAL_HASH)
    unit = base.checked(unit_config, UNIT_PATCHED_HASH)
    graph = json.loads(unit)["usecase_info"]["xpan_case"]
    if graph != [{"preview": "var_camera"}, {"capture": "var_camera"},
                 {"raw16_output": "var_camera"}, {"raw_output": "var_camera"}]:
        raise ValueError("Unexpected XPAN RAW16 graph")
    files["payload/camera_unit_config"] = unit
    manifest.append(f"payload/camera_unit_config /odm/etc/camera/config/camera_unit_config {UNIT_ORIGINAL_HASH} {UNIT_PATCHED_HASH}")
    files["payload/libAlgoInterface.so"] = bytes(patched)
    manifest.append(f"payload/libAlgoInterface.so /odm/lib64/libAlgoInterface.so {base.LIB_HASH} {PATCHED_HASH}")
    assert len(manifest) == 5 and not any("/oplus_camera_config " in r for r in manifest)
    files.update({
        "module.prop": f"id={base.MODULE_ID}\nname=OnePlus 12 Native Master + XPAN HDR (private)\n"
            "version=0.3\nversionCode=3\nauthor=noahhhi\n"
            "description=Camera6.070.215 only. Keeps master0.2; XPAN native HDR main1x autoJPG only. Requires companion APK17+ in LSPosed camera scope. Action removes photo binds. PRIVATE payload.\n",
        "skip_mount": "", "runtime.sh": RUNTIME,
        "service.sh": base.wrapper("apply"), "uninstall.sh": base.wrapper("remove"),
        "action.sh": base.wrapper("remove", disable=True),
        "payload-manifest": "\n".join(manifest) + "\n",
        "customize.sh": '[ "$KSU" = true ] || abort "KernelSU required"\n'
            '[ "$ARCH" = arm64 ] || abort "arm64 required"\n'
            'set_perm_recursive "$MODPATH" 0 0 0755 0644\n'
            'for script in service.sh runtime.sh uninstall.sh action.sh; do\n'
            '  set_perm "$MODPATH/$script" 0 0 0755\ndone\n'
            'ui_print "Requires companion APK17+ enabled in LSPosed for com.oplus.camera."\n'
            'ui_print "Close camera and remove old photo binds before upgrade; keep0.2 rollback backup."\n'
            'ui_print "PRIVATE firmware payload. Do not publish this ZIP."\n',
        "build-manifest.json": json.dumps({"private_payload": True, "version": "0.3",
            "camera_apk_sha256": base.APK_HASH, "original_library_sha256": base.LIB_HASH,
            "patched_library_sha256": PATCHED_HASH, "patches": patch_report,
            "required_lsp_package": "io.github.noahhhi.camera.hdrprobe", "minimum_version_code": 17,
            "required_lsp_scope": "com.oplus.camera", "xpan_verified_scope": "main1x automaticJPG",
            "global_application_config_overlay": False,
            "property": "debug.noah.hdr.xpan_native", "payloads": manifest}, indent=2)+"\n",
        "PRIVATE-DO-NOT-PUBLISH.txt": "Generated ZIP contains proprietary camera files. Keep private.\n"
            "Requires companion APK17+ enabled in LSPosed camera scope BEFORE activation.\n"
            "This builder does not verify runtime scope or install anything.\n"
            "Retain0.2 rollback files and undo old photo mounts before replacing module files.\n"
            "Application config belongs to the independent video helper and is not mounted here.\n"
            "On incomplete rollback the XPAN property is retained. Keep camera closed and recover\n"
            "all photo binds before disabling the gate. Do not disable only the LSPosed component\n"
            "while the XPAN native recipe remains mounted.\n",
    })
    output = output.resolve()
    if output.is_relative_to(ROOT.parent):
        raise ValueError("Private ZIP output must be outside the source checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, (2026, 10, 21, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return {"output": str(output), "sha256": base.digest(output.read_bytes()),
            "version": "0.3", "owned_targets": len(manifest), "private": True}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stock-dir", type=Path, required=True)
    p.add_argument("--xpan-config-dir", type=Path, required=True)
    p.add_argument("--unit-config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--experimental", action="store_true", required=True)
    a = p.parse_args()
    print(json.dumps(build(a.stock_dir, a.xpan_config_dir, a.unit_config, a.output), indent=2))
