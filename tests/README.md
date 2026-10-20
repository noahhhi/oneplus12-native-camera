# Host-only video helper tests

Run on a Linux host (including a Linux shell in WSL), with Python 3.9+, Bash, awk and coreutils:

```sh
python3 tests/test_video_recovery.py
python3 tests/test_video_runtime.py
```

No phone, ADB, root access or firmware fixtures are required. Android commands, service transitions, mounts, and device metadata are mocked. The complete-runtime suite uses disposable host files and substitutes all device target paths. It does not mount files or restart real services.

The six recovery cases cover busy mounts, stop failure, partial unmount failure, persistent/transient start failure and active-client refusal. The fifteen complete-runtime cases additionally cover activation, unknown mount IDs, failed ledger/intent writes, removal after firmware changes, foreign mounts, and fail-closed client inspection. A 2 MiB dumpsys fixture with external printf reproduces the former argument-size failure; a negative control confirms the old implementation fails.

These tests verify the helper lifecycle, not native image quality, actual motion handling or firmware compatibility.
