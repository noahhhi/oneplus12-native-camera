# OnePlus 12 Native Camera

Independent research and version-pinned native camera fixes for OnePlus 12, stock Camera 6.070.215.

See [HDR implementation and validation](hdrprobe/README.md) and [research notes](docs/ultrahdr-research.md). Public files contain original build tools and opt-in, read-only diagnostics. Firmware, private photos, device logs and generated device-specific packages are not distributed.

Planned follow-up work: [4K Live HDR Photo, Master Live Photo and Xpan Ultra HDR](docs/roadmap.md).

## Photo status

The 0.2 native HDR helper is enabled and accepted on the test device. Master mode automatic JPEG has been verified at 0.6x ultra-wide, 1x main, 3x telephoto and 6x telephoto: OEM HDR processing, valid Android gainmap decoding and usable images. Physical telephoto selection and 6x crop metadata were checked. The accepted 3x/6x captures ran without Frida.

The stock telephoto IZOOM brightness hysteresis is preserved. The 6x bright-scene branch has not yet been physically validated. Manual exposure, RAW, arbitrary zoom positions and other firmware versions are not covered by this acceptance.

## Video research status

The separate 0.1 experimental video addon is now installed on the test device alongside the accepted 0.2 photo helper. Activation, module Action rollback and reactivation passed on-device: rollback restored the original video node/configuration hashes without changing the photo helper.

The ultra-wide 4K60 repeated-edge defect has been isolated to a coordinate-origin issue. A temporary native correction removed the approximately 192-row extension and aligned framing with the SDR control in one fixed scene. All 347 frames had valid Dolby RPU metadata; the clip retained 10bit Dolby Vision 8.4 at approximately 59.10 fps, with zero L5 crop offsets.

The guarded file-backed patch passed main 4K60, physical telephoto 4K60 (camera 4, 13.3 mm), ultra-wide 4K60 and ultra-wide 4K30 Dolby regressions, plus a clean SDR control with zero RPU. Dolby clips retained genuine profile 8.4 metadata and clean edges. These tests ran without Frida. Final post-install ultra-wide capture also passed: physical camera 3 at 2.62 mm, 352 frames and 352 RPU, Dolby Vision 8.4 at approximately 59.10 fps, clean edges and no ffprobe warnings. Actual motion and long-duration recording remain unverified. This is a firmware-specific experimental addon, not a general release.

Automation stops recording normally, returns Home and waits for camera clients to release before force-stopping the app. Abrupt force-stop had left the next launch's HDR UI state unreliable; the graceful lifecycle allowed the test to explicitly select SDR correctly. See [native video details](docs/native-video.md) and [host-only lifecycle tests](tests/README.md).

## Packaging and provenance

The diagnostic project was extracted from work on the public OPCameraPro mirror. This is a standalone repository, not a GitHub fork; the legacy application and SDR-to-gainmap generation code are not included. Gradle wrapper files retain their upstream notices; repository license: GPL-3.0.

The private helpers use version-checked systemless mounts. Video rollback requires no active camera clients, stops the verified provider before unmounting owned binds, and attempts provider startup even after rollback errors. Failed or foreign mount records are retained for recovery. The public test suites use mocks and no firmware fixtures.
