# OnePlus 12 Native Camera

Independent research and version-pinned native camera fixes for OnePlus 12, stock Camera 6.070.215.

See [HDR implementation and validation](hdrprobe/README.md) and [research notes](docs/ultrahdr-research.md). Public files contain original build tools, a gated SDK control and read-only observers. Firmware, private photos, device logs and generated device-specific packages are not distributed.

Planned follow-up work: [4K Live HDR Photo, Master Live Photo and Xpan Ultra HDR](docs/roadmap.md).

Offline reference work: [verified PMX110 firmware and initial camera/SDK comparison](docs/findx10-reference.md).

## Photo status

Photo helper 0.3 is now installed. It preserves the 0.2 Master-mode configuration, previously verified for automatic JPEG at 0.6x, 1x, 3x and 6x, and adds verified XPan HDR for the main camera at 1x with automatic ISO/shutter and JPEG output. XPan remains native mode 29: five RAW frames → TurboHDR(65) → MaskRefine(72) → gainmap → JPEG. Its 7872×2912 output (or rotated equivalent) has a half-resolution gainmap. Post-install capture without Frida verified 2912×7872 with a 1456×3936 gainmap.

XPan requires companion APK version code 17 or newer, enabled in LSPosed for the stock camera. Its gated control overrides only the SDK's `com.oplus.xpan.multi.frame` Boolean; it is no longer an entirely read-only module. Run the photo helper's Action before disabling its LSPosed scope. The five photo mounts exclude `oplus_camera_config`, leaving the separate video configuration alone.

The current Master regression used manual ISO 320 and correctly remained SDR; it is not a new automatic-Master HDR test. The final post-install normal-mode regression was interrupted before the shutter and is not counted as passed. Other XPan lenses, black-and-white rendering and watermarks have not been validated.

The stock telephoto IZOOM brightness hysteresis is preserved. The 6x bright-scene branch has not yet been physically validated. Manual exposure, RAW, arbitrary zoom positions and other firmware versions are not covered by this acceptance.

## Video research status

**Open regression: recording crashes were reported during manual use on 2026-10-21. Version 0.1 is not accepted as stable.** The earlier short-clip results below remain limited observations. Crash logs and provider tombstones are needed to identify the failing process and path before attempting a fix; no cause or resolution is confirmed.

The separate 0.1 experimental video addon is unchanged by photo helper 0.3. Its instability remains a separate task. Earlier activation, Action rollback and reactivation passed on-device: rollback restored the original video node/configuration hashes without changing the photo helper.

The ultra-wide 4K60 repeated-edge defect has been isolated to a coordinate-origin issue. A temporary native correction removed the approximately 192-row extension and aligned framing with the SDR control in one fixed scene. All 347 frames had valid Dolby RPU metadata; the clip retained 10bit Dolby Vision 8.4 at approximately 59.10 fps, with zero L5 crop offsets.

The guarded file-backed patch passed main 4K60, physical telephoto 4K60 (camera 4, 13.3 mm), ultra-wide 4K60 and ultra-wide 4K30 Dolby regressions, plus a clean SDR control with zero RPU. Dolby clips retained genuine profile 8.4 metadata and clean edges. These tests ran without Frida. Final post-install ultra-wide capture also passed: physical camera 3 at 2.62 mm, 352 frames and 352 RPU, Dolby Vision 8.4 at approximately 59.10 fps, clean edges and no ffprobe warnings. Actual motion and long-duration recording remain unverified. This is a firmware-specific experimental addon, not a general release.

Automation stops recording normally, returns Home and waits for camera clients to release before force-stopping the app. Abrupt force-stop had left the next launch's HDR UI state unreliable; the graceful lifecycle allowed the test to explicitly select SDR correctly. See [native video details](docs/native-video.md) and [host-only lifecycle tests](tests/README.md).

## Packaging and provenance

The diagnostic project was extracted from work on the public OPCameraPro mirror. This is a standalone repository, not a GitHub fork; the legacy application and SDR-to-gainmap generation code are not included. Gradle wrapper files retain their upstream notices; repository license: GPL-3.0.

The private helpers use version-checked systemless mounts. Video rollback requires no active camera clients, stops the verified provider before unmounting owned binds, and attempts provider startup even after rollback errors. Failed or foreign mount records are retained for recovery. The public test suites use mocks and no firmware fixtures.
