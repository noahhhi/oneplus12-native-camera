# Experimental native video patch builder

**Stability regression, 2026-10-21:** recording crashes were reported after installation of video addon 0.1. Short static validation did not cover this failure. The cause is unconfirmed, and the addon must not be described as stable. The next device session should preserve crash logs/tombstones first, identify whether the app, provider or codec failed, then compare stationary recording, movement and lens switching with controlled SDR/30fps cases. The independent photo helper is outside this video rollback scope.

This original-source tool builds a version-pinned OnePlus 12 native video test artifact from files you extract locally. It targets a source-grid origin mismatch observed in ultrawide Dolby Vision 4K60 recordings. The repository supplies no original camera binaries, calibration dumps, or ready-to-install payload.

The guarded native v3 file-backed patch passed main 4K60, physical telephoto 4K60, ultra-wide 4K60/4K30 Dolby regressions and an SDR control, without Frida. Dolby clips retained genuine profile 8.4/RPU and clean edges; the SDR control remained 8bit BT.709 with no RPU. Real handheld motion has not been validated.

The independent 0.1 experimental video addon is installed alongside photo helper 0.2. On-device activation, Action rollback and reactivation passed. Action restored the original video node/configuration hashes and left the photo helper unchanged. Final post-install ultra-wide capture passed on physical camera 3 at 2.62 mm: 352 frames, 352 RPU, Dolby Vision 8.4 at approximately 59.10 fps, clean edges and no ffprobe warnings. Actual motion and long-duration recording remain unverified; this is not a general firmware fix.

For repeatable DV-to-SDR tests, recording is stopped normally, then the app returns Home and waits for camera clients to release before force-stop. Abrupt termination had made the next launch's HDR UI state unreliable; graceful closure fixed the baseline and patched test sequence without adding a preference workaround.

Use Python 3.9 or newer and Keystone 0.9.2:

```sh
python -m pip install keystone-engine==0.9.2
python tools/native_video_patch.py \
  --node /local-camera-files/com.oplus.node.sstabdefer.so \
  --extension /local-camera-files/libextensionlayer.so \
  --output-prefix /local-camera-output/video-test \
  --experimental
```

The two inputs must be unmodified originals matching the exact SHA-256 pins in the builder. It also checks the AArch64 ELF layout, original instructions, read-only Dolby predicate, and reserved zero padding. Other versions are rejected. The assembly is loaded relative to the tool, so the command can run from another working directory when the script path is adjusted.

The output prefix creates `.so`, `.shim.bin`, and `.manifest.json` files. Output must be outside the source checkout; existing artifacts are not overwritten. **Generated binaries contain proprietary firmware content. Keep all generated artifacts private and do not attach them to releases or issues.** The tool does not install, mount, restart services, or connect to a device.

The wrapper preserves the original PAC/BTI entry and uses a temporary copy of the coordinate grid. Its gates include the native Dolby predicate, SAT60 mode, the verified ultrawide/output dimensions, finite coordinates, and bounded source-origin checks. Other calls take the original function path. The 375-pixel domain adjustment is specific to this tested firmware; it is not derived from live crop metadata.

Validation includes 12 offline ABI/guard cases and 360 synthetic translation/rotation cases. Synthetic coverage does not establish real motion behavior: thresholds can still reject larger motion or rolling-shutter deformation. The extra native wrapper frame has no added unwind metadata. The generated manifest retains experimental limitations and marks the artifact as not ready for general deployment.

## Offline tests

These tests assemble the public wrapper and emulate it against a mock original function. They require no phone, root access, firmware files, calibration dumps, videos, or private fixtures. From the repository root on Linux:

```sh
python3 -m pip install keystone-engine==0.9.2 unicorn==2.1.4
python3 -B tests/native_video_abi.py
python3 -B tests/native_video_motion.py
```

The 12 ABI cases check guard decisions, original-grid immutability, exact copied coordinates, argument and return preservation, stack alignment/restoration, and callee-saved registers. The 360 motion cases exercise translations, rotations through 0.5 degrees, synthetic optical slack, and rejection of centered source grids. Each suite verifies the exact public shim SHA-256 before reporting success; run without Python's `-O` option.

The independent-axis motion envelope deliberately includes combinations beyond the remaining field-of-view margin after rotation. It is a conservative guard test, not a claim that every transform is physically valid. Emulation also does not establish real Android PAC/BTI enforcement, loader behavior, unwind behavior, or handheld recording quality.

The video helper streams camera-client inspection through a pipefail-protected pipeline. Its 15 complete-runtime mock cases include a 2 MiB dumpsys response and an external-printf negative control reproducing the former argument-size failure. Six separate recovery cases cover stop/unmount/start failures. The diagnostic APK 1.3 returns before APK hashing when both debug switches are off; diagnostics are currently off on the test device.
