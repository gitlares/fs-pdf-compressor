# FS PDF Compressor roadmap

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
