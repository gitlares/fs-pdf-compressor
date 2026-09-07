# 1.0.14 release validation

Date: 2026-09-07. Application source: `35d048bada24e75aa632b69adeecefc5864771f0` (`v1.0.14`).
The maintainer authorized publication after confirming both Windows and the final macOS candidate.

## Behavior

- Keep original enabled: preserve the original and create a uniquely named compressed copy.
- Keep original disabled: try recycling the old original, then replace with a smaller validated output.
- Recycling is best-effort protection. If it fails, replacement still proceeds and the old original may not be recoverable.
- Failed output installation preserves/restores the original when possible. Temporary recovery snapshots are internal, not a third output mode. Crash-atomic behavior across every operating-system operation is not claimed.

## macOS

- CI run `34161200184` assembled the compatibility candidate.
- Developer ID signing and strict signature verification passed.
- All 108 bundled Mach-O files passed the macOS 14 target audit.
- Apple submission `c0f2b041-13bf-4235-96b8-54e5539d2893`: Accepted.
- DMG stapling and validation passed; Gatekeeper: accepted, Notarized Developer ID.
- Core tests using the final bundled Ghostscript passed all three profiles and both modes, with recovered original bytes verified.
- UI automation could not complete the native selector; the maintainer subsequently tested the final package and explicitly confirmed all requested behavior.
- Final artifacts: `release-1.0.14-final/FS-PDF-Compressor-1.0.14-arm64.dmg` and matching update ZIP.

## Windows

- CI run `34151829834`: 57 tests, 51 passed, 6 platform-specific skips.
- Real Ghostscript: all three profiles and both modes passed; Recycle Bin recovery confirmed.
- Installer and portable ZIP SHA-256 checks passed; bundled source manifest identifies the release source.
- Maintainer installed and confirmed operation in the Windows UTM VM.
- The installer remains unsigned by design; this release does not add automatic Windows updates.

## Linux AppImage

- CI run `34161212444` built the final AppImage on Ubuntu 22.04.
- SHA-256 verified. The exact CI AppImage launched under Xvfb/X11 on Magnolia and compressed a generated PDF from 64,892 to 2,371 bytes.
- Both successful trash recovery and replacement with an unavailable portal passed; output rendered through Ghostscript and no owned temporary files remained.
- Source Qt folder processing, all three profiles and both modes passed on Magnolia.
- Linux regression suite: 57 tests, 52 passed, 5 macOS-only skips.

## Snap

- Isolated build required an explicit directory change inside the LXD container; see `snap/README.md`.
- Initial confined test exposed missing `gs_init.ps`; resource/font/ICC layouts fixed it. Missing Wayland runtime libraries were added.
- The corrected package built successfully and was installed with strict confinement as local revision x2.
- Installed Snap modules passed all three profiles, both modes, and asynchronous Qt folder processing.
- Actual packaged X11 launch and compression passed with the ordinary session bus and with a deliberately unavailable application portal.
- Artifact on Magnolia: `/home/dlares/fs-pdf-1.0.14-test.LGizra/fs-pdf-compressor_1.0.14_amd64.snap`.
- SHA-256: `d8f3e033096bfabfac995cd40987e4cbe8840693a821de157e95a6d7f23e9978`.
- The original Store revision 5 was restored after local testing; the build container was stopped and its project mount detached.

## Limits and follow-up

Magnolia's host Trash portal failed/timed out inside Snap. Replacement fallback passed, but successful Snap-to-host trash recovery was not established. Manual Wayland and removable-media coverage are not claimed. Nonfatal packaging lint warnings remain for unused Qt modules/plugins and GPU packaging. Basic output validation is not a visual-fidelity guarantee for arbitrary PDFs. Generated PDFs only were used by automated tests.

## Reproduce

```sh
python -B -m unittest discover -s tests
python -B -m scripts.verify_platform_safety
python -B -m scripts.verify_platform_safety --qt
xvfb-run -a python -B -m scripts.verify_linux_appimage release-linux/FS-PDF-Compressor-x86_64.AppImage
```

Use `scripts/verify_snap_confined.sh` through `snap run --shell` to exercise the installed Snap modules, and `scripts/verify_linux_appimage.py --snap` for packaged launch tests. Generated originals successfully recycled during smoke tests remain in system trash.
