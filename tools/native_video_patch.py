"""Build an experimental, version-pinned native video patch from local originals.

Generated binaries contain proprietary firmware content and must stay private.
This tool never installs modules, mounts files, restarts services, or uses ADB.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN

NODE_SHA = "2b7b5bc7163af849a1f4652ba793dc4cb842e55b5c043e3909b52db4eacac056"
EXT_SHA = "cb14f0198ac77bebfd9f21ff2e31f6d01b34d369e3c7e74b2014ec81a4d140e0"
ENTRY, CAVE, RX_END, NEXT_SEGMENT = 0x5A9C0, 0x71600, 0x715D8, 0x72000
PATCH_SITE = ENTRY + 4  # Preserve PACIASP / BTI landing at function entry.
ENTRY_BYTES = bytes.fromhex("3f2303d5eb2bb86de923016dfd7b02a9")
GETTER_VA = 0x8A260
GETTER_BYTES = bytes.fromhex("5f2403d5088840b91f85007104195e7ae0179f1ac0035fd6")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def segments(data):
    if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("Expected ELF64 little-endian AArch64")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    if size != 56 or phoff + size * count > len(data):
        raise ValueError("Unexpected program headers")
    result = []
    for i in range(count):
        at = phoff + size * i
        kind, flags, off, va, pa, filesz, memsz, align = struct.unpack_from("<IIQQQQQQ", data, at)
        result.append(dict(header_offset=at, kind=kind, flags=flags, offset=off,
                           va=va, filesz=filesz, memsz=memsz, align=align))
    return result


def offset(data, va, length):
    matches = [s["offset"] + va - s["va"] for s in segments(data)
               if s["kind"] == 1 and s["va"] <= va and va + length <= s["va"] + s["filesz"]]
    if len(matches) != 1 or matches[0] + length > len(data):
        raise ValueError("No unique file-backed VA mapping")
    return matches[0]


def assemble():
    source = (ROOT / "native_video_wrapper.S").read_text()
    # Keystone 0.9.2 accepts architectural HINT aliases and local labels.
    code = "\n".join(line.split("//", 1)[0] for line in source.splitlines())
    code = code.replace("__ORIGINAL_PLUS8__", hex(ENTRY + 8))
    blob, count = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN).asm(code, addr=CAVE, as_bytes=True)
    if not blob or len(blob) % 4 or CAVE + len(blob) > NEXT_SEGMENT:
        raise ValueError("Shim invalid or exceeds reserved RX gap")
    return blob, source


def build(node_path, extension_path, output_prefix):
    original, ext = node_path.read_bytes(), extension_path.read_bytes()
    if sha(original) != NODE_SHA or sha(ext) != EXT_SHA:
        raise ValueError("Exact firmware binary hash mismatch")
    entry_offset = offset(original, ENTRY, len(ENTRY_BYTES))
    if original[entry_offset:entry_offset + len(ENTRY_BYTES)] != ENTRY_BYTES:
        raise ValueError("Original function entry mismatch")
    getter_offset = offset(ext, GETTER_VA, len(GETTER_BYTES))
    if ext[getter_offset:getter_offset + len(GETTER_BYTES)] != GETTER_BYTES:
        raise ValueError("Pinned read-only getter implementation mismatch")
    ss = segments(original)
    rx = next(s for s in ss if s["kind"] == 1 and s["flags"] == 5)
    if (rx["offset"], rx["va"], rx["filesz"], rx["memsz"]) != (
            0x27000, 0x27000, 0x4A5D8, 0x4A5D8):
        raise ValueError("Unexpected executable segment")
    next_load = next(s for s in ss if s["kind"] == 1 and s["va"] == NEXT_SEGMENT)
    if next_load["offset"] != NEXT_SEGMENT or next_load["flags"] != 6:
        raise ValueError("Unexpected next segment boundary")
    if any(original[RX_END:NEXT_SEGMENT]):
        raise ValueError("Whole reserved gap is not zero")
    blob, source = assemble()
    patched = bytearray(original)
    relative = (CAVE - PATCH_SITE) // 4
    if (CAVE - PATCH_SITE) % 4 or not -(1 << 25) <= relative < (1 << 25):
        raise ValueError("Branch out of range")
    branch = struct.pack("<I", 0x14000000 | (relative & 0x3FFFFFF))
    patched[entry_offset + 4:entry_offset + 8] = branch
    patched[CAVE:CAVE + len(blob)] = blob
    # Expand existing RX only, stopping precisely at next RW PT_LOAD.
    new_size = NEXT_SEGMENT - rx["va"]
    header_offset = rx["header_offset"] + 32
    old_header = original[header_offset:header_offset + 16]
    new_header = struct.pack("<QQ", new_size, new_size)
    patched[header_offset:header_offset + 16] = new_header
    manifest = {
        "private_payload": True, "offline_review_only": True, "deployable": False,
        "blockers": [
            "Controlled native DV, SDR transitions and module Action checks passed; automation must release camera clients before force-stop",
            "375 is firmware-specific calibration-domain hypothesis, not live crop metadata",
            "Widened guards passed 360 synthetic cases; actual physical motion and rolling-shutter behavior remain unvalidated",
            "No general firmware compatibility or unwind-through-wrapper guarantee; use only matching original binaries",
        ],
        "original_node_sha256": NODE_SHA, "extension_sha256": EXT_SHA,
        "patched_node_sha256": sha(patched), "shim_sha256": sha(blob),
        "assembly_sha256": sha(source.encode()), "shim_length": len(blob),
        "revision": 3,
        "experimental_guard_ranges": {"center_x": [1900, 2100], "center_y": [650, 850],
                                      "min_y": [-500, -250], "max_y": [1700, 2050]},
        "function_entry_va": hex(ENTRY), "preserved_paciasp_hex": ENTRY_BYTES[:4].hex(),
        "function_va": hex(ENTRY), "patch_va": hex(PATCH_SITE),
        "entry_va": hex(PATCH_SITE), "entry_original_hex": ENTRY_BYTES[4:8].hex(),
        "entry_replacement_hex": branch.hex(), "function_entry_pin_16_hex": ENTRY_BYTES.hex(),
        "entry_pin_16_hex": ENTRY_BYTES.hex(),
        "shim_va": hex(CAVE), "shim_end_va": hex(CAVE + len(blob)),
        "gap_start_va": hex(RX_END), "gap_end_va": hex(NEXT_SEGMENT),
        "shim_original_hex": original[CAVE:CAVE + len(blob)].hex(),
        "shim_replacement_hex": blob.hex(),
        "getter_va": hex(GETTER_VA), "getter_original_hex": GETTER_BYTES.hex(),
        "segment_header_change": {"file_offset": hex(header_offset),
                                  "original_hex": old_header.hex(),
                                  "replacement_hex": new_header.hex()},
        "temporary_stack_grid_bytes": 6600, "temporary_stack_allocation_bytes": 6608,
        "wrapper_saved_frame_bytes": 16,
        "source_input_untouched": True,
    }
    # Keep proprietary build artifacts outside this source checkout.
    prefix = output_prefix.resolve()
    if prefix.is_relative_to(ROOT.parent):
        raise ValueError("Output must be outside the source checkout")
    artifacts = {
        prefix.with_suffix(".so"): bytes(patched),
        prefix.with_suffix(".shim.bin"): blob,
        prefix.with_suffix(".manifest.json"): (json.dumps(manifest, indent=2) + "\n").encode(),
    }
    if any(p.exists() for p in artifacts):
        raise FileExistsError("Refusing to overwrite review artifacts")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    for path, data in artifacts.items():
        with path.open("xb") as stream:
            stream.write(data)
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node", type=Path, required=True, help="Local original com.oplus.node.sstabdefer.so")
    p.add_argument("--extension", type=Path, required=True, help="Local original libextensionlayer.so")
    p.add_argument("--output-prefix", type=Path, required=True)
    p.add_argument("--experimental", action="store_true", required=True,
                   help="Acknowledge experimental status; no installation is performed")
    a = p.parse_args()
    print("PRIVATE OUTPUT: generated binaries contain original firmware; do not publish them.", file=sys.stderr)
    m = build(a.node, a.extension, a.output_prefix)
    print(json.dumps({k: m[k] for k in ("deployable", "shim_length", "entry_va",
                                      "shim_va", "shim_end_va", "patched_node_sha256")}, indent=2))
