# 1.0.15 release validation — in progress

This release is not published. Its two main changes are Ghostscript 10.08.0
and remembering the Keep original selection across app restarts. The source
since 1.0.14 also removes local diagnostic log files.

## Completed

- All 59 automated tests passed, including persistence checks for the shared
  Windows/Linux Qt interface and the macOS preference action.
- The 12 compression-engine tests passed with Ghostscript 10.08.0 selected.
- An ad-hoc macOS arm64 candidate built on macOS 26.7. Its embedded `gs`
  reports 10.08.0, the manifest records app 1.0.15 and Ghostscript 10.08.0,
  and deep code-signature verification passed. The app launched and the
  bundled Ghostscript compressed and rendered a generated PDF with all three
  profiles. This artifact is only for local testing: its Homebrew Tesseract
  library requires macOS 26.6.2, so it is not the macOS 14 release candidate.
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
  commit `0858274bed8a88631e8a92f7f657f9bf59bfd1b2`.
- Package checksums:
  - AppImage: `429b9ddc152ed7648f09ee65c4a6a9888bdb1c1c1b5c9e9f0b18f4c1299acecf`
  - Snap: `ea7e2e5b02f05ad220a5979fa92477a209cf41f26e989223f49e93a3bdb5d175`
  - Windows installer: `267dd13fb553cbbff11520c87ec1e5ff3ad0bbe5e972be010ba7a166cb891af7`
  - Windows portable ZIP: `82c4d73468cf52cbeb8d837df5b056420dc54a7cd6598e662e2a2ae4f0f3fea8`
- The official Ghostscript 10.08.0 source archive matched its pinned SHA-256.
- The sample from issue #9 still rendered incorrectly in macOS PDFKit with
  Ghostscript 10.08.0. The engine upgrade is not a fix for that issue.

## Required before publication

- Build the macOS 14 candidate, audit every Mach-O deployment target, launch
  the app, test all three compression profiles and both Keep original states,
  then sign, notarize, staple, and assess the final DMG.
- Install the Windows candidate on Windows 11 x64 and test Explorer
  integration, Drop Zone, all profiles, both Keep original states, update
  link and Recycle Bin behavior.
- Open the AppImage and Snap in an interactive Linux desktop session and check
  file picker, drag and drop, Wayland, removable media and host-trash recovery.
- On every platform, confirm that Keep original defaults to off on a fresh
  install and that both on and off survive an app restart.
- Keep issue #9 open and describe the visual limitation accurately in the
  release notes.
