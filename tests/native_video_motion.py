"""Fixture-free synthetic motion tests against the exact public native shim.

No device, original firmware, encoded video, calibration dump or manifest is read.
Synthetic coverage is not physical handheld-motion validation.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location(
    "abi", Path(__file__).resolve().with_name("native_video_abi.py"))
abi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abi)


def points(angle, tx, ty, origin, optical_error):
    c, s = math.cos(angle), math.sin(angle)
    values = []
    for row in range(25):
        for col in range(33):
            x, y = col * 125 - 2000, row * 93.75 - 1125
            # Bounded synthetic radial perturbation, not measured calibration.
            ex = optical_error * (x / 2000) ** 3
            ey = optical_error * (y / 1125) ** 3
            values.extend((2000 + c*x - s*y + tx + ex,
                           1125 + s*x + c*y + ty + origin + ey))
    return struct.pack("<1650f", *values)


def main():
    counts = {"legal_shifted_accepted": 0, "legal_centered_rejected": 0,
              "independent_axis_shifted_accepted": 0,
              "independent_axis_centered_rejected": 0}
    for degrees in (-0.5, -0.25, 0, 0.25, 0.5):
        angle = math.radians(degrees)
        c, s = math.cos(angle), abs(math.sin(angle))
        # Rotation consumes part of the 80x45 axis-aligned FOV margin.
        margins = (2000 - (1920*c + 1080*s),
                   1125 - (1080*c + 1920*s))
        for family, (mx, my) in (("legal", margins),
                                ("independent_axis", (80, 45))):
            for tx in (-mx, 0, mx):
                for ty in (-my, 0, my):
                    for optical_error in (0, 12):
                        for origin in (-375, 0):
                            data = points(angle, tx, ty, origin, optical_error)
                            accept = origin == -375
                            abi.run_case(
                                f"{family}:{degrees}:{tx}:{ty}:{optical_error}:{origin}",
                                accept, grid_bytes=data, quiet=True)
                            key = family + ("_shifted_accepted" if accept
                                            else "_centered_rejected")
                            counts[key] += 1
    assert sum(counts.values()) == 360
    assert hashlib.sha256(abi.SHIM).hexdigest() == abi.EXPECTED_SHIM_SHA256
    print(json.dumps({"passed": 360, "cases": counts,
                      "public_shim_sha256": abi.EXPECTED_SHIM_SHA256,
                      "physical_motion_validated": False}, indent=2))


if __name__ == "__main__":
    main()
