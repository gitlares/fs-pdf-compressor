# 1.0.14 local validation — not released

Date: 2026-09-07. Working branch: `codex/1.0.14-platform-alignment`.
No release, store upload, remote push, or main merge was performed.

## Required behavior

- **Keep original enabled:** preserve the original and create a uniquely named compressed copy.
- **Keep original disabled:** try moving the original to the operating system's trash, then replace with a smaller validated output.
- If recycling fails, still replace, as requested. Trash is best-effort protection and the old original may not be recoverable. Do not introduce an adjacent backup mode. If installing the compressed output fails, preserve/restore the original.
- Recovery snapshots are internal temporary files, not a new user setting.

## Completed checks

- Local macOS unittest discovery after the Snap packaging regression tests: 57 tests, 52 passed, 5 Qt-only tests skipped.
- Magnolia Linux unittest discovery: 57 tests, 52 passed, 5 macOS-only tests skipped; complementary Qt coverage passed.
- Real Ghostscript: all three profiles, with both existing output modes, on local macOS and Magnolia. Generated PDFs only. Recycled originals were checked byte-for-byte.
- Source UI smoke tests: asynchronous AppKit processing on macOS and Qt folder discovery/batch processing on Magnolia; Qt event-loop responsiveness and thread cleanup checked.
- Local ad-hoc macOS application assembled and signature verification passed. This is not a notarized release candidate.
- AppImage rebuilt on Magnolia after the best-effort trash change; SHA-256 verification passed. The actual AppImage was launched under Xvfb/X11 in default Balanced/replace mode. Both native trash recovery and replacement with a deliberately unavailable portal passed: generated input 64,892 bytes, output 2,373 bytes. Original bytes were verified in the trash for the successful recycling case; the failure case produced the compressed file without a recycled original. Output rendering through Ghostscript passed, the app remained alive, and owned temporary files were cleaned up. This is not a manual GNOME/KDE desktop review or older-distribution compatibility certification.
- Windows recycling policy tests use mocked COM callbacks. They do not replace a real Windows test.

Reproduce the automated checks from the repository with an appropriate platform environment:

```sh
python -B -m unittest discover -s tests
python -B -m scripts.verify_platform_safety
# Linux with PySide6:
python -B -m scripts.verify_platform_safety --qt
# Linux packaged application, isolated X11 display:
xvfb-run -a python -B -m scripts.verify_linux_appimage release-linux/FS-PDF-Compressor-x86_64.AppImage
```

The opt-in smoke script creates its own PDFs. Originals from successful replacement tests remain in the system trash, identified by `fs-pdf-test-` names.

## Release gates still open

1. **Snap — local functional tests passed:** resolved the isolated build working-directory failure by explicitly changing directory inside the container (see `snap/README.md`). The first installed candidate exposed a real Ghostscript failure: `Can't find initialization file gs_init.ps`. Added confined layouts for Ghostscript resources, fonts, and ICC data, plus missing Wayland libraries. Rebuilt successfully and installed locally as revision `x2`, `confinement: strict`. The installed `/snap/fs-pdf-compressor/x2/opt/fs-pdf-compressor/fs_pdf_compressor/core.py` passed all three profiles and both modes, with asynchronous Qt folder processing. Actual application launch under Xvfb/X11 and output rendering passed with both the regular session bus and a deliberately unavailable application portal (64,892 -> 2,373 bytes). Magnolia's host-trash portal still fails/times out; fallback replacement passed but trash recovery was not established. Manual Wayland/removable-media testing remains outside this check. Nonfatal lint warnings remain for unused Qt plugins/libraries and GPU packaging. No Store upload or publication occurred.
2. **Windows:** build the updated installer with pywin32, inspect bundled license material, and exercise installation, recycling, recovery, context menu, drop zone, and single-instance behavior in the UTM VM. The VM was stopped; no runtime approval is claimed.
3. **macOS compatibility:** the locally bundled Homebrew Python/libraries include deployment targets newer than macOS 14. The macOS 14 Mach-O audit failed. Do not distribute this local build or claim macOS 14 compatibility; rebuild in the supported release environment, audit every Mach-O, then sign/notarize/staple and run Gatekeeper checks.
4. **Packaged desktop tests:** exercise the final rebuilt application artifacts, not only source entry points, on each supported desktop. Verify all profiles and both output modes on representative documents before publication.
5. **Trash failure review:** include delayed portal replies/disconnection, cross-volume files, unavailable recycle bins, disk-full conditions, and forced process termination in the remaining safety review. Current automated rollback tests do not prove crash-atomic behavior across every OS operation.

Public release links and announcements must remain unchanged until these gates are resolved and publication is authorized.

## Snap artifact and cleanup

- Tested artifact on Magnolia: `/home/dlares/fs-pdf-1.0.14-test.LGizra/fs-pdf-compressor_1.0.14_amd64.snap`.
- SHA-256: `d8f3e033096bfabfac995cd40987e4cbe8840693a821de157e95a6d7f23e9978`.
- After testing, restored the Store's exact original 1.0.13 revision 5 using `snap refresh --amend --revision=5`; tracking remains `latest/candidate` (the Store reports that channel closed and forwards to stable).
- Stopped the isolated build container and detached its project mount. Build caches and the tested artifact remain available; no user PDFs were modified.
