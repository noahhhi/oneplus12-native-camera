"""Offline AArch64 wrapper simulation. Never loads a device or calls ADB.

Original function is replaced by a controlled ABI stub. This tests guards,
source immutability, arguments, stack cleanup and register/return preservation.
Unicorn does NOT establish real Android PAC/BTI enforcement or loader behavior.
"""
import hashlib
import importlib.util
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X5,
                                 UC_ARM64_REG_X29, UC_ARM64_REG_X30,
                                 UC_ARM64_REG_D0, UC_ARM64_REG_SP, UC_ARM64_REG_PC)
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN

spec = importlib.util.spec_from_file_location("builder", ROOT.parent / "tools/native_video_patch.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
SHIM, _ = builder.assemble()
EXPECTED_SHIM_SHA256 = "9e0e3ca66f832f52e4a189d029dfd7cf2ceeaf84a179d30eb068c641c745d58a"
if not __debug__:
    raise RuntimeError("Run these assertion-based tests without Python -O")
assert hashlib.sha256(SHIM).hexdigest() == EXPECTED_SHIM_SHA256, "Public shim changed; review expected bytes before updating this pin"
ks = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)
CODE, STACK, ENGINE, EXT, GRID, OUTPUT = (
    0x10000000, 0x20000000, 0x30000000, 0x30010000, 0x40000000, 0x40010000)
START_SP, STOP = STACK + 0x30000, CODE + 0x78000


def grid(y_delta=-375):
    points = []
    for row in range(25):
        for col in range(33):
            points.extend((col * 125.0, row * 93.75 + y_delta))
    return struct.pack("<1650f", *points)


def run_case(name, accept, *, dv=30, mode=2, width=4000, height=2250,
         window=(3840, 2160), y_delta=-375, bad_float=None, extension=True,
             grid_bytes=None, quiet=False):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for address, length in ((CODE, 0x80000), (STACK, 0x40000),
                            (ENGINE, 0x1000), (EXT, 0x1000),
                            (GRID, 0x2000), (OUTPUT, 0x2000)):
        uc.mem_map(address, length)
    uc.mem_write(CODE + builder.CAVE, SHIM)
    branch = 0x14000000 | (((builder.CAVE - builder.PATCH_SITE) // 4) & 0x3FFFFFF)
    uc.mem_write(CODE + builder.ENTRY, builder.ENTRY_BYTES[:4])
    uc.mem_write(CODE + builder.PATCH_SITE, struct.pack("<I", branch))
    # The wrapper/trampoline still executes its actual assembled code.
    # Trampoline already executed displaced128-byte STP frame. The stub
    # restores it just as the original epilogue would before authenticating LR.
    stub, _ = ks.asm("ldp d11,d10,[sp],#128; mov x0,#0x1234; mov x1,#0x5678; hint #29; ret",
                     addr=CODE + builder.ENTRY + 8, as_bytes=True)
    uc.mem_write(CODE + builder.ENTRY + 8, stub)
    uc.mem_write(ENGINE + 0x240, struct.pack("<I", mode))
    uc.mem_write(ENGINE + 0x2A8, struct.pack("<Q", EXT if extension else 0))
    uc.mem_write(EXT + 0x88, struct.pack("<I", dv))
    source = bytearray(grid(y_delta) if grid_bytes is None else grid_bytes)
    assert len(source) == 6600, "Expected 825 XY pairs"
    if bad_float is not None:
        struct.pack_into("<I", source, 12, bad_float)
    source = bytes(source)
    uc.mem_write(GRID, source)
    args = [ENGINE, width, height, *window, GRID, OUTPUT]
    for i, value in enumerate(args):
        uc.reg_write(UC_ARM64_REG_X0 + i, value)
    preserved = {}
    for n in range(19, 30):
        reg = UC_ARM64_REG_X0 + n if n < 29 else UC_ARM64_REG_X29
        value = 0x71000000 + n * 0x100
        uc.reg_write(reg, value)
        preserved[reg] = value
    for n in range(8, 16):
        # AAPCS64 preserves the LOW64 bits of v8-v15, not their high halves.
        reg, value = UC_ARM64_REG_D0 + n, 0x1122334455667788 + n
        uc.reg_write(reg, value)
        preserved[reg] = value
    uc.reg_write(UC_ARM64_REG_SP, START_SP)
    uc.reg_write(UC_ARM64_REG_X30, STOP)
    reached = []

    def on_code(machine, address, size, _):
        if address == CODE + builder.ENTRY + 8:
            reached.append(address)
            sp = machine.reg_read(UC_ARM64_REG_SP)
            assert sp % 16 == 0, (name, "unaligned stack")
            for i in (0, 1, 2, 3, 4, 6):
                assert machine.reg_read(UC_ARM64_REG_X0 + i) == args[i], (name, "argument", i)
            replacement = machine.reg_read(UC_ARM64_REG_X5)
            assert (replacement != GRID) == accept, (name, "wrong guard decision")
            if accept:
                assert sp == START_SP - 16 - 6608 - 128
                assert replacement == sp + 128
                old = struct.unpack("<1650f", source)
                expected = struct.pack("<1650f", *(v + 375.0 if i % 2 else v
                                                  for i, v in enumerate(old)))
                assert bytes(machine.mem_read(replacement, 6600)) == expected
            else:
                assert sp == START_SP - 128
            assert bytes(machine.mem_read(GRID, 6600)) == source
        elif address == STOP:
            machine.emu_stop()

    uc.hook_add(UC_HOOK_CODE, on_code)
    uc.emu_start(CODE + builder.ENTRY, STOP + 4, count=100000)
    assert len(reached) == 1, (name, "original body call count")
    assert uc.reg_read(UC_ARM64_REG_PC) == STOP
    assert uc.reg_read(UC_ARM64_REG_SP) == START_SP
    assert uc.reg_read(UC_ARM64_REG_X0) == 0x1234
    assert uc.reg_read(UC_ARM64_REG_X1) == 0x5678
    assert uc.reg_read(UC_ARM64_REG_X30) == STOP
    for reg, value in preserved.items():
        assert uc.reg_read(reg) == value, (name, "callee-saved register", reg)
    assert bytes(uc.mem_read(GRID, 6600)) == source
    if not quiet:
        print("PASS", name)


def main():
    run_case("DV mode30 accepted", True)
    run_case("DV mode33 accepted", True, dv=33)
    run_case("non-DV field rejected", False, dv=0)
    run_case("wrong EIS mode rejected", False, mode=6)
    run_case("main sensor domain rejected", False, width=4096, height=2304)
    run_case("1080 window rejected", False, window=(1920, 1080))
    run_case("centered grid rejected", False, y_delta=0)
    run_case("motion inside widened center guard accepted", True, y_delta=-350)
    run_case("motion beyond widened center guard rejected", False, y_delta=-200)
    run_case("NaN rejected", False, bad_float=0x7FC00000)
    run_case("infinity rejected", False, bad_float=0x7F800000)
    run_case("null extension rejected", False, extension=False)
    print("12 ABI cases passed; simulation does not establish real-device PAC/BTI behavior.")


if __name__ == "__main__":
    main()
