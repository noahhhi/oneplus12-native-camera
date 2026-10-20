# OnePlus 12 Native Camera

Independent research and version-pinned native camera fixes for OnePlus 12, stock Camera 6.070.215.

See [HDR implementation and validation](hdrprobe/README.md) and [research notes](docs/ultrahdr-research.md). Public files contain original build tools and opt-in, read-only diagnostics. Firmware, private photos, device logs and generated device-specific packages are not distributed.

## Photo status

The 0.2 native HDR helper is enabled and accepted on the test device. Master mode automatic JPEG has been verified at 0.6x ultra-wide, 1x main, 3x telephoto and 6x telephoto: OEM HDR processing, valid Android gainmap decoding and usable images. Physical telephoto selection and 6x crop metadata were checked. The accepted 3x/6x captures ran without Frida.

The stock telephoto IZOOM brightness hysteresis is preserved. The 6x bright-scene branch has not yet been physically validated. Manual exposure, RAW, arbitrary zoom positions and other firmware versions are not covered by this acceptance.

## Video research status

Temporary tests verified real 4K60 Dolby Vision profile 8.4 on the telephoto camera, including physical camera 4 at 13.3 mm and per-frame Dolby RPU metadata. This is a research result, not a deployed video release.

Ultra-wide 4K60 also produces Dolby metadata, but has an unresolved repeated-edge defect: approximately 192 rows in the unrotated frame. A lit SDR ultra-wide control has clean edges. Valid Dolby metadata does not make the defective output acceptable. No permanent video unlock is deployed.

## Packaging and provenance

The diagnostic project was extracted from work on the public OPCameraPro mirror. This is a standalone repository, not a GitHub fork; the legacy application and SDR-to-gainmap generation code are not included. Gradle wrapper files retain their upstream notices; repository license: GPL-3.0.

The private helper uses version-checked systemless mounts. Removal closes the camera before unmounting and preserves failed or foreign mount records for safe retries. Mock tests cover camera-stop failure, partial unmount failure/retry, foreign mount IDs and already-absent mounts.
