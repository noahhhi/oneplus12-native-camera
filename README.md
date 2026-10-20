# OnePlus 12 Native Camera

Independent research and version-pinned native camera fixes for OnePlus 12.

See [HDR implementation and validation](hdrprobe/README.md). The repository contains only original research tools and a read-only diagnostic module. Device firmware, private photos and generated device-specific packages are not distributed.

Current validated scope: main camera 1x automatic JPEG native HDR in Master mode. Ultra-wide, telephoto and 6x support are under development. Dolby Vision 4K60 recording research follows the photo work.

The diagnostic project was extracted from our work on the public OPCameraPro mirror. This is a standalone repository, not a GitHub fork; the legacy OPCameraPro application is not included. Gradle wrapper files retain their upstream notices; repository license: GPL-3.0.

## Multi-lens candidate status

The 0.2 helper is a candidate, not the currently accepted device release. Native TurboHDR and Android gainmap decoding passed on the ultra-wide, 3x telephoto and 6x telephoto paths. Physical telephoto selection and 6x crop metadata were checked. Telephoto scene-quality acceptance remains pending usable camera input; a valid gainmap alone is not the final acceptance criterion.

The candidate also preserves the stock telephoto IZOOM brightness hysteresis for 6x; its bright-scene path has not yet been physically validated. Dolby Vision 4K60 work follows completion of photo acceptance.

Removal now closes the camera before unmounting and preserves only failed/foreign mount records for safe retries. Mock tests cover camera-stop failure, partial unmount failure/retry, foreign mount IDs and already-absent mounts.
