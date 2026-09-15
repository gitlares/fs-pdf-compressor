# FS PDF Compressor roadmap

## Current direction

- Keep macOS, Windows, AppImage, and Snap on one shared compression engine and
  version line.
- Preserve the focused local-only workflow and three quality profiles.
- Add Windows code signing when a sustainable signing process is available.
- Continue improving release verification on all three operating systems.

## Completed in 1.0.14 — Platform alignment

- Aligned original-file safety, document locks, PDF validation, background
  work, and embedded versions across macOS, Windows, AppImage, and Snap.
- Published and verified macOS 14+ Apple Silicon, Windows 11 x64, Linux
  AppImage, and Snap Store packages from the shared source.
- Added platform-specific download pages for Mac, Windows, and Linux with
  visitor operating-system detection on the GitHub Pages homepage.

## Completed in 1.0.13 — Windows edition and memory efficiency

- Added the Windows 11 x64 installer and portable ZIP with SHA-256 checksums.
- Added Explorer integration, a single-instance Drop Zone, and Recycle Bin
  preservation when replacing an original PDF.
- Reduced idle memory use and deferred unnecessary update initialization.

## Completed in 1.0.7 — Drop Zone

- Added an optional, movable Drop Zone on macOS and Linux.
- Compressed dropped PDFs through the existing shared engine without opening a
  second process or polling the filesystem.
- Remembered whether Drop Zone is enabled and where the user placed it.
- Made Drop Zone available in every macOS Space.
- Kept the normal application window and all three quality profiles unchanged.
- Treated Linux desktop placement as compositor-dependent: X11 desktops can
  honor the bottom-window hint, while some Wayland compositors may present the
  target as a normal floating utility.
- Separated platform views and workers into focused modules and added tests for
  the shared non-UI behavior.

## Completed in 1.0.6 — Linux AppImage edition

- Added an x86_64 Linux AppImage with a native Qt interface and the same shared
  compression engine as macOS.
- Bundled Ghostscript, AppImage `zsync` metadata, checksum verification, and a
  user-initiated in-app update path.

## Completed in 1.0.5 — Apple Silicon macOS 14+ compatibility

- Built the unsigned base application on GitHub's `macos-14` Apple Silicon
  runner, then audit every bundled Mach-O deployment target.
- Finalized, Developer ID signed, notarized, and published the resulting candidate
  locally so signing and update keys never leave the Mac.
- The distribution remains `arm64` only. Intel support is deliberately out of
  scope for this release.

## Later — maintainability and reliability

- Add a timeout and clearer recovery path for a Ghostscript process that does
  not finish.
- Move directory expansion off the main UI thread so large folders remain
  responsive.
- Add automated tests for output naming, size calculations, quality profiles,
  Ghostscript failures, and update-feed generation.
- Refactor the build script into named build, bundle, sign, and package phases.
- Require an explicit release output directory before deleting build artifacts.

These are engineering improvements. They must preserve the small native UI,
local-only processing, and the existing signed-update key.
