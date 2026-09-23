# 1.0.15 release validation

This release was published on 2026-09-23. Its two main changes are Ghostscript 10.08.0
and remembering the Keep original selection across app restarts. The source
since 1.0.14 also removes local diagnostic log files.

## Completed

- All 59 automated tests passed, including persistence checks for the shared
  Windows/Linux Qt interface and the macOS preference action.
- The 12 compression-engine tests passed with Ghostscript 10.08.0 selected.
- The final macOS arm64 application was assembled on macOS 14.8.9. Its 87
  Mach-O files passed the macOS 14 compatibility audit. The embedded `gs`
  reports 10.08.0 and compressed and rendered a generated PDF with all three
  profiles. The app and DMG passed Developer ID verification; Apple accepted
  notarization submission `0afe95fe-4848-4075-b2e7-25866d53da58`, stapling
  succeeded, and Gatekeeper accepted the DMG as Notarized Developer ID.
- The Linux AppImage and strictly confined Snap were built on the Magnolia
  Ubuntu 24.04 x86_64 host. Both bundle Ghostscript 10.08.0.
- The AppImage launched under Xvfb and compressed and rendered a generated PDF
  with the desktop trash portal both available and deliberately unavailable.
- The installed local Snap passed all three profiles and both Keep original
  states using its packaged modules. It also launched under Xvfb and produced
  a PDF that Ghostscript rendered successfully. The remote session could not
  confirm host-trash recovery because its desktop portal was unavailable.
- The Windows Server 2022 candidate workflow passed its regression and
  compression smoke tests, built the per-user installer and portable ZIP, and
  verified their packaged compliance files. The manifest records app 1.0.15,
  Ghostscript 10.08.0, Python 3.12.10, PySide6 6.8.3 and the exact source
  commit `1f9f8f9b317714624403c93e751df58c5545a9d3`.
- The Windows installer was tested on Windows and confirmed functional before
  publication.
- Package checksums:
  - macOS DMG: `34673f8700878be88d4584d00ab394152cfc500925046f03fb7eb045dfc90a89`
  - macOS update ZIP: `2cce92a02543defeb787d8cba26ab6f90e36193480131c0ec5ed2a0555179446`
  - AppImage: `4574edf231cb8cb378aed55370637e8f00e05f40de3881c4a781aff1c35e4272`
  - Snap: `1ce900d31f9c613f31e34bcc0d93cbc8f66fe3b7f6050e64d34f72d3956b0fe0`
  - Windows installer: `d3eea9c30c374e5ca29eac7420e5a4cdd01b31a75579ffb9cc6aa16a7dbfd7e0`
  - Windows portable ZIP: `b68746b73be9f5c670deaabc0d684f6d9e001441b857617de1ba51dd85e56896`
- The official Ghostscript 10.08.0 source archive matched its pinned SHA-256.
- The sample from issue #9 still rendered incorrectly in macOS PDFKit with
  Ghostscript 10.08.0. The engine upgrade is not a fix for that issue.

## Known validation limits

- Open the AppImage and Snap in an interactive Linux desktop session and check
  file picker, drag and drop, Wayland, removable media and host-trash recovery.
- On every platform, confirm that Keep original defaults to off on a fresh
  install and that both on and off survive an app restart.
- Keep issue #9 open and describe the visual limitation accurately in the
  release notes.
